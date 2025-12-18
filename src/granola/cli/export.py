"""Combined export command with folder structure."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from granola.api.auth import AuthError, get_access_token
from granola.api.client import APIError, GranolaClient
from granola.api.models import Document
from granola.api.models import ProseMirrorDoc
from granola.cache.reader import SharedDocument, get_default_cache_path, read_cache
from granola.formatters.combined import format_combined, format_transcript
from granola.prosemirror.converter import to_markdown
from granola.sync_config import (
    SyncConfig,
    get_effective_exclusions,
    load_sync_config,
    save_sync_config,
)
from granola.webhooks import WebhookDispatcher, WebhookPayload
from granola.writers.sync_writer import ExportDoc, SyncResult, SyncStats, SyncWriter

console = Console()


@dataclass
class ExportResult:
    """Result of a programmatic export operation."""

    success: bool
    added: int = 0
    updated: int = 0
    moved: int = 0
    deleted: int = 0
    skipped: int = 0
    error_message: str = ""
    webhook_summary: str = ""
    # Effective exclusions (merged from local + sync folder)
    # App should update local settings if these differ
    effective_excluded_folders: list[str] | None = None


def run_export(
    output_folder: str,
    supabase_path: str | None = None,
    cache_path: str | None = None,
    excluded_folders: list[str] | None = None,
    excluded_folders_updated: str | None = None,
    webhook_configs: list[dict] | None = None,
    timeout: int = 120,
    logger: logging.Logger | None = None,
) -> ExportResult:
    """Run export programmatically (for use by menubar app).

    Args:
        output_folder: Directory to export files to.
        supabase_path: Path to supabase.json file.
        cache_path: Path to Granola cache file.
        excluded_folders: List of folder names to exclude (from local settings).
        excluded_folders_updated: ISO timestamp of when local exclusions were updated.
        webhook_configs: List of webhook configuration dicts.
        timeout: HTTP timeout in seconds.
        logger: Optional logger for debug output.

    Returns:
        ExportResult with stats and any error information.
    """
    logger = logger or logging.getLogger(__name__)
    output_dir = Path(output_folder)

    # Debug: log input parameters
    logger.info(f"run_export called with excluded_folders={excluded_folders}, excluded_folders_updated={excluded_folders_updated}")

    # Load and merge exclusions from sync folder config
    # This allows exclusions to sync across multiple computers
    effective_excluded, sync_config = get_effective_exclusions(
        output_dir,
        excluded_folders or [],
        excluded_folders_updated,
    )
    excluded_set = set(effective_excluded)
    logger.info(f"Effective excluded folders: {effective_excluded}")

    # 1. Resolve supabase path
    if not supabase_path:
        # Try default location
        default_supabase = Path.home() / "Library" / "Application Support" / "Granola" / "supabase.json"
        if default_supabase.exists():
            supabase_path = str(default_supabase)
        else:
            return ExportResult(success=False, error_message="supabase.json path not set")

    supabase_file = Path(supabase_path)
    if not supabase_file.exists():
        return ExportResult(success=False, error_message=f"supabase.json not found at {supabase_path}")

    # 2. Get access token
    try:
        access_token = get_access_token(supabase_file)
    except (AuthError, FileNotFoundError) as e:
        return ExportResult(success=False, error_message=f"Failed to read supabase.json: {e}")

    # 3. Fetch documents from API
    try:
        client = GranolaClient(access_token, timeout=timeout)
        api_docs = client.get_documents()
    except APIError as e:
        return ExportResult(success=False, error_message=f"API request failed: {e}")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        # Write full traceback to log file for debugging
        log_path = Path.home() / ".config" / "granola" / "error.log"
        log_path.write_text(f"Error fetching docs: {e}\n\n{tb}")
        return ExportResult(success=False, error_message=f"Unexpected error: {e} (see ~/.config/granola/error.log)")

    logger.info(f"Retrieved {len(api_docs)} documents from API")

    # 3b. Fetch folder assignments from API (not cache - cache may be corrupted)
    api_doc_folders: dict[str, list[str]] = {}
    api_folders: dict[str, str] = {}
    try:
        api_folders, api_doc_folders = client.get_doc_folder_mapping()
        logger.info(f"Retrieved {len(api_folders)} folders from API, {len(api_doc_folders)} doc-folder mappings")
    except APIError as e:
        logger.warning(f"Failed to fetch folder data from API (continuing without folders): {e}")
    except Exception as e:
        logger.warning(f"Error fetching folder data: {e}")

    # 4. Read cache for transcripts only (folders now come from API)
    # If cache read fails, continue with empty cache (still sync API docs)
    cache_file = Path(cache_path) if cache_path else get_default_cache_path()
    cache_data = None
    try:
        cache_data = read_cache(cache_file)
    except Exception as e:
        logger.warning(f"Failed to read cache file (continuing without transcripts): {e}")

    # If no cache data, create empty structure
    if cache_data is None:
        from granola.cache.reader import CacheData
        cache_data = CacheData(
            documents={},
            transcripts={},
            folders={},
            doc_folders={},
            shared_documents={},
        )

    logger.info(f"Loaded cache: {len(cache_data.transcripts)} transcripts")

    # Helper to get folder names - prefer API data, fall back to cache
    def get_folder_names(doc_id: str) -> list[str]:
        """Get folder names for a document, preferring API over cache."""
        if doc_id in api_doc_folders:
            return api_doc_folders[doc_id]
        return cache_data.get_folder_names(doc_id)

    # 5. Build export documents
    all_doc_ids: set[str] = set()
    export_docs: list[ExportDoc] = []

    for api_doc in api_docs:
        folders = get_folder_names(api_doc.id)

        if excluded_set and any(f in excluded_set for f in folders):
            continue

        all_doc_ids.add(api_doc.id)
        segments = cache_data.transcripts.get(api_doc.id, [])
        notes_content = _get_notes_content(api_doc)

        has_notes = notes_content and notes_content.strip()
        has_transcript = len(segments) > 0
        if not has_notes and not has_transcript:
            continue

        content = format_combined(
            title=api_doc.title,
            doc_id=api_doc.id,
            created_at=api_doc.created_at,
            updated_at=api_doc.updated_at,
            notes_content=notes_content,
            segments=segments,
            folders=folders,
        )
        transcript_text = format_transcript(segments) if segments else ""

        try:
            ts = api_doc.created_at.replace("Z", "+00:00")
            created_at = datetime.fromisoformat(ts)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        except ValueError:
            created_at = datetime.now(timezone.utc)

        try:
            ts = api_doc.updated_at.replace("Z", "+00:00")
            updated_at = datetime.fromisoformat(ts)
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
        except ValueError:
            updated_at = datetime.now(timezone.utc)

        export_docs.append(ExportDoc(
            id=api_doc.id,
            title=api_doc.title,
            created_at=created_at,
            updated_at=updated_at,
            content=content,
            folders=folders,
            has_notes=has_notes,
            has_transcript=has_transcript,
            notes_content=notes_content or "",
            transcript_content=transcript_text,
        ))

    # 5b. Process shared documents from cache
    for shared_doc in cache_data.shared_documents.values():
        if shared_doc.id in all_doc_ids:
            continue

        folders = get_folder_names(shared_doc.id)
        if excluded_set and any(f in excluded_set for f in folders):
            continue

        all_doc_ids.add(shared_doc.id)
        segments = cache_data.transcripts.get(shared_doc.id, [])
        notes_content = _get_shared_notes_content(shared_doc)

        has_notes = notes_content and notes_content.strip()
        has_transcript = len(segments) > 0
        if not has_notes and not has_transcript:
            continue

        content = format_combined(
            title=shared_doc.title,
            doc_id=shared_doc.id,
            created_at=shared_doc.created_at,
            updated_at=shared_doc.updated_at,
            notes_content=notes_content,
            segments=segments,
            folders=folders,
        )
        transcript_text = format_transcript(segments) if segments else ""

        try:
            ts = shared_doc.created_at.replace("Z", "+00:00")
            created_at = datetime.fromisoformat(ts)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        except ValueError:
            created_at = datetime.now(timezone.utc)

        try:
            ts = shared_doc.updated_at.replace("Z", "+00:00")
            updated_at = datetime.fromisoformat(ts)
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
        except ValueError:
            updated_at = datetime.now(timezone.utc)

        export_docs.append(ExportDoc(
            id=shared_doc.id,
            title=shared_doc.title,
            created_at=created_at,
            updated_at=updated_at,
            content=content,
            folders=folders,
            has_notes=has_notes,
            has_transcript=has_transcript,
            notes_content=notes_content or "",
            transcript_content=transcript_text,
        ))

    # 6. Sync to filesystem (passing exclusions to delete excluded folders)
    sync_writer = SyncWriter(output_dir, logger=logger, excluded_folders=list(excluded_set))
    try:
        stats, results = sync_writer.sync(export_docs, all_doc_ids)
    except Exception as e:
        import traceback
        return ExportResult(success=False, error_message=f"Sync failed: {e}\n{traceback.format_exc()}")

    # 6b. Save sync config to sync folder (so exclusions sync across computers)
    save_sync_config(output_dir, sync_config)

    # 7. Dispatch webhooks
    webhook_summary = ""
    if webhook_configs:
        dispatcher = WebhookDispatcher(webhook_configs, logger=logger)
        webhook_results = []

        for result in results:
            if not result.doc.has_notes:
                continue

            payload = WebhookPayload.create(
                event=f"document.{result.action}",
                doc_id=result.doc.id,
                title=result.doc.title or "",
                created_at=result.doc.created_at.isoformat(),
                updated_at=result.doc.updated_at.isoformat(),
                folders=result.doc.folders,
                file_path=str(result.file_path),
                markdown_content=result.doc.content,
                notes_content=result.doc.notes_content,
                transcript_content=result.doc.transcript_content,
                has_notes=result.doc.has_notes,
                has_transcript=result.doc.has_transcript,
            )
            webhook_results.extend(dispatcher.dispatch(payload))

        if webhook_results:
            webhook_summary = dispatcher.get_summary(webhook_results)

    return ExportResult(
        success=True,
        added=stats.added,
        updated=stats.updated,
        moved=stats.moved,
        deleted=stats.deleted,
        skipped=stats.skipped,
        webhook_summary=webhook_summary,
        effective_excluded_folders=list(excluded_set),
    )


def default_export_output() -> Path:
    """Return the default output directory for combined export."""
    return Path.home() / "My Drive" / "z. Granola Notes"


def export_cmd(
    timeout: Annotated[
        int,
        typer.Option("--timeout", help="HTTP timeout in seconds"),
    ] = 120,
    cache: Annotated[
        Optional[str],
        typer.Option("--cache", help="Path to Granola cache file"),
    ] = None,
    output: Annotated[
        Optional[str],
        typer.Option("--output", help="Output directory for exported files"),
    ] = None,
    exclude_folder: Annotated[
        Optional[list[str]],
        typer.Option("--exclude-folder", help="Folder to exclude (can be used multiple times)"),
    ] = None,
    supabase: Annotated[
        Optional[str],
        typer.Option("--supabase", help="Path to supabase.json file"),
    ] = None,
    webhook: Annotated[
        Optional[list[str]],
        typer.Option("--webhook", help="JSON-encoded webhook config (can be used multiple times)"),
    ] = None,
) -> None:
    """Export combined notes and transcripts with folder structure.

    This command fetches notes from the Granola API, reads transcripts from the local cache,
    and combines them into .txt files organized by Granola folder structure.

    Documents in multiple folders will be duplicated into each folder.
    Documents not in any folder will be placed in the "Uncategorized" folder.
    Files are synced incrementally - only updated when the source changes.
    Deleted documents are removed from the output directory.

    Use --exclude-folder to skip documents in specific folders. Documents in an excluded
    folder will be skipped entirely, even if they also belong to other folders.
    """
    from granola.cli.main import state, resolve_path

    # 0. Resolve output directory early (needed for sync config)
    output_dir = resolve_path(output) if output else default_export_output()

    # 0b. Load and merge exclusions from sync folder config
    # This allows exclusions to sync across computers
    cli_excluded = set(exclude_folder) if exclude_folder else set()
    effective_excluded, sync_config = get_effective_exclusions(
        output_dir,
        list(cli_excluded),
        None,  # CLI doesn't track timestamp
    )
    excluded_folders = set(effective_excluded)
    state.logger.info(f"Effective excluded folders: {effective_excluded}")

    # 1. Get supabase path (command option > global state)
    supabase_path = resolve_path(supabase) if supabase else state.supabase
    if not supabase_path:
        console.print(
            "[red]Error:[/red] supabase.json path not set. "
            "Use --supabase flag, SUPABASE_FILE env, or config file."
        )
        raise typer.Exit(1)

    if not supabase_path.exists():
        console.print(f"[red]Error:[/red] supabase.json not found at {supabase_path}")
        raise typer.Exit(1)

    # Get access token
    state.logger.info(f"Reading supabase configuration from {supabase_path}")
    try:
        access_token = get_access_token(supabase_path)
    except (AuthError, FileNotFoundError) as e:
        console.print(f"[red]Error:[/red] Failed to read supabase.json: {e}")
        raise typer.Exit(1)

    # 2. Fetch documents from API
    console.print("Fetching documents from Granola API...")
    state.logger.info(f"Fetching documents from Granola API (timeout={timeout}s)")

    try:
        client = GranolaClient(access_token, timeout=timeout)
        api_docs = client.get_documents()
    except APIError as e:
        console.print(f"[red]Error:[/red] API request failed: {e}")
        raise typer.Exit(1)

    state.logger.info(f"Retrieved {len(api_docs)} documents from API")

    # 3b. Fetch folder assignments from API
    api_doc_folders: dict[str, list[str]] = {}
    api_folders: dict[str, str] = {}
    try:
        api_folders, api_doc_folders = client.get_doc_folder_mapping()
        state.logger.info(f"Retrieved {len(api_folders)} folders from API, {len(api_doc_folders)} doc-folder mappings")
    except APIError as e:
        state.logger.warning(f"Failed to fetch folder data from API (continuing without folders): {e}")

    # 3c. Read cache for transcripts only (folders now come from API)
    cache_path = resolve_path(cache) if cache else get_default_cache_path()

    state.logger.info(f"Reading cache file from {cache_path}")
    cache_data = None
    try:
        cache_data = read_cache(cache_path)
    except Exception as e:
        state.logger.warning(f"Failed to read cache file (continuing without transcripts): {e}")

    # If no cache data, create empty structure
    if cache_data is None:
        from granola.cache.reader import CacheData
        cache_data = CacheData(
            documents={},
            transcripts={},
            folders={},
            doc_folders={},
            shared_documents={},
        )

    state.logger.info(f"Loaded cache data: {len(cache_data.transcripts)} transcripts")

    # Helper to get folder names - prefer API data, fall back to cache
    def get_folder_names(doc_id: str) -> list[str]:
        if doc_id in api_doc_folders:
            return api_doc_folders[doc_id]
        return cache_data.get_folder_names(doc_id)

    # 4. Build export documents by merging API docs with cache data
    all_doc_ids: set[str] = set()
    export_docs: list[ExportDoc] = []

    for api_doc in api_docs:
        # Get folder names for this document (from API, not cache)
        folders = get_folder_names(api_doc.id)

        # Skip if document is in any excluded folder
        if excluded_folders and any(f in excluded_folders for f in folders):
            state.logger.debug(f"Skipping document '{api_doc.title}' - in excluded folder")
            continue

        all_doc_ids.add(api_doc.id)

        # Get transcript segments
        segments = cache_data.transcripts.get(api_doc.id, [])

        # Get notes content (convert ProseMirror to Markdown)
        notes_content = _get_notes_content(api_doc)

        # Skip documents with no notes and no transcript
        has_notes = notes_content and notes_content.strip()
        has_transcript = len(segments) > 0
        if not has_notes and not has_transcript:
            state.logger.debug(f"Skipping document '{api_doc.title}' - no notes or transcript")
            continue

        # Format the combined content
        content = format_combined(
            title=api_doc.title,
            doc_id=api_doc.id,
            created_at=api_doc.created_at,
            updated_at=api_doc.updated_at,
            notes_content=notes_content,
            segments=segments,
            folders=folders,
        )

        # Format transcript separately for webhooks
        transcript_text = format_transcript(segments) if segments else ""

        # Parse created_at timestamp
        try:
            ts = api_doc.created_at.replace("Z", "+00:00")
            created_at = datetime.fromisoformat(ts)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        except ValueError:
            created_at = datetime.now(timezone.utc)

        # Parse updated_at timestamp
        try:
            ts = api_doc.updated_at.replace("Z", "+00:00")
            updated_at = datetime.fromisoformat(ts)
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
        except ValueError:
            updated_at = datetime.now(timezone.utc)

        export_docs.append(ExportDoc(
            id=api_doc.id,
            title=api_doc.title,
            created_at=created_at,
            updated_at=updated_at,
            content=content,
            folders=folders,
            has_notes=has_notes,
            has_transcript=has_transcript,
            notes_content=notes_content or "",
            transcript_content=transcript_text,
        ))

    # 4b. Process shared documents from cache
    state.logger.info(f"Processing {len(cache_data.shared_documents)} shared documents")
    for shared_doc in cache_data.shared_documents.values():
        # Skip if we already have this document from the API
        if shared_doc.id in all_doc_ids:
            continue

        # Get folder names for this document (from API, not cache)
        folders = get_folder_names(shared_doc.id)

        # Skip if document is in any excluded folder
        if excluded_folders and any(f in excluded_folders for f in folders):
            state.logger.debug(f"Skipping shared document '{shared_doc.title}' - in excluded folder")
            continue

        all_doc_ids.add(shared_doc.id)

        # Get transcript segments (shared docs may have transcripts in cache)
        segments = cache_data.transcripts.get(shared_doc.id, [])

        # Get notes content from shared doc
        notes_content = _get_shared_notes_content(shared_doc)

        # Skip documents with no notes and no transcript
        has_notes = notes_content and notes_content.strip()
        has_transcript = len(segments) > 0
        if not has_notes and not has_transcript:
            state.logger.debug(f"Skipping shared document '{shared_doc.title}' - no notes or transcript")
            continue

        # Format the combined content
        content = format_combined(
            title=shared_doc.title,
            doc_id=shared_doc.id,
            created_at=shared_doc.created_at,
            updated_at=shared_doc.updated_at,
            notes_content=notes_content,
            segments=segments,
            folders=folders,
        )

        # Format transcript separately for webhooks
        transcript_text = format_transcript(segments) if segments else ""

        # Parse created_at timestamp
        try:
            ts = shared_doc.created_at.replace("Z", "+00:00")
            created_at = datetime.fromisoformat(ts)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        except ValueError:
            created_at = datetime.now(timezone.utc)

        # Parse updated_at timestamp
        try:
            ts = shared_doc.updated_at.replace("Z", "+00:00")
            updated_at = datetime.fromisoformat(ts)
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
        except ValueError:
            updated_at = datetime.now(timezone.utc)

        export_docs.append(ExportDoc(
            id=shared_doc.id,
            title=shared_doc.title,
            created_at=created_at,
            updated_at=updated_at,
            content=content,
            folders=folders,
            has_notes=has_notes,
            has_transcript=has_transcript,
            notes_content=notes_content or "",
            transcript_content=transcript_text,
        ))

    # 5. Sync to output directory
    console.print(f"Syncing {len(export_docs)} documents to {output_dir}...")
    state.logger.info(f"Starting sync to {output_dir}, {len(export_docs)} documents")

    # 6. Sync to filesystem (passing exclusions to delete excluded folders)
    sync_writer = SyncWriter(output_dir, logger=state.logger, excluded_folders=list(excluded_folders))
    try:
        stats, results = sync_writer.sync(export_docs, all_doc_ids)
    except Exception as e:
        console.print(f"[red]Error:[/red] Sync failed: {e}")
        raise typer.Exit(1)

    # 6b. Save sync config to sync folder
    save_sync_config(output_dir, sync_config)

    # 7. Print results
    console.print(
        f"[green]✓[/green] Export completed: "
        f"{stats.added} added, {stats.updated} updated, "
        f"{stats.moved} moved, {stats.deleted} deleted, {stats.skipped} skipped"
    )
    state.logger.info(
        f"Export completed: added={stats.added}, updated={stats.updated}, "
        f"moved={stats.moved}, deleted={stats.deleted}, skipped={stats.skipped}"
    )

    # 8. Dispatch webhooks for documents with notes that were added or updated
    webhook_configs = []
    if webhook:
        for w in webhook:
            try:
                webhook_configs.append(json.loads(w))
            except json.JSONDecodeError as e:
                state.logger.warning(f"Invalid webhook config: {e}")

    if webhook_configs:
        dispatcher = WebhookDispatcher(webhook_configs, logger=state.logger)
        webhook_results = []

        for result in results:
            # Only send webhooks for documents with notes content
            if not result.doc.has_notes:
                state.logger.debug(
                    f"Skipping webhook for '{result.doc.title}' - no notes content"
                )
                continue

            # Build webhook payload
            payload = WebhookPayload.create(
                event=f"document.{result.action}",
                doc_id=result.doc.id,
                title=result.doc.title or "",
                created_at=result.doc.created_at.isoformat(),
                updated_at=result.doc.updated_at.isoformat(),
                folders=result.doc.folders,
                file_path=str(result.file_path),
                markdown_content=result.doc.content,
                notes_content=result.doc.notes_content,
                transcript_content=result.doc.transcript_content,
                has_notes=result.doc.has_notes,
                has_transcript=result.doc.has_transcript,
            )

            # Dispatch to all configured webhooks
            webhook_results.extend(dispatcher.dispatch(payload))

        # Print webhook summary
        if webhook_results:
            summary = dispatcher.get_summary(webhook_results)
            console.print(f"[blue]ℹ[/blue] {summary}")
            state.logger.info(summary)


def _get_notes_content(doc: Document) -> str | None:
    """Extract Granola AI-generated notes from an API document.

    Priority:
    1. Notes (ProseMirror) - converted to Markdown (if non-empty)
    2. LastViewedPanel.Content (ProseMirror) - converted to Markdown
    3. LastViewedPanel.OriginalContent (HTML)
    4. Content (raw)

    Note: notes_plain is human-written notes, not Granola AI notes.
    """
    # Try Notes (ProseMirror) - Granola AI-generated notes
    if doc.notes:
        content = to_markdown(doc.notes)
        if content and content.strip():
            return content

    # Try LastViewedPanel.Content (ProseMirror) - also AI-generated
    if doc.last_viewed_panel and doc.last_viewed_panel.content:
        return to_markdown(doc.last_viewed_panel.content)

    # Try LastViewedPanel.OriginalContent (HTML - return as-is)
    if doc.last_viewed_panel and doc.last_viewed_panel.original_content:
        return doc.last_viewed_panel.original_content

    # Fallback to Content field
    return doc.content


def _get_shared_notes_content(shared_doc: SharedDocument) -> str | None:
    """Extract notes content from a shared document in the cache.

    Priority:
    1. notes_markdown - AI-generated notes already in markdown
    2. last_viewed_panel.content - ProseMirror content
    """
    # Try notes_markdown first
    if shared_doc.notes_markdown and shared_doc.notes_markdown.strip():
        return shared_doc.notes_markdown

    # Try last_viewed_panel.content (stored as raw dict in cache)
    if shared_doc.last_viewed_panel:
        lvp = shared_doc.last_viewed_panel
        content_data = lvp.get("content")
        if content_data:
            # Parse as ProseMirrorDoc and convert to markdown
            try:
                pm_doc = ProseMirrorDoc.model_validate(content_data)
                return to_markdown(pm_doc)
            except Exception:
                pass

    return None
