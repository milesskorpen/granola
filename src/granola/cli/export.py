"""Combined export command with folder structure."""

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
from granola.formatters.combined import format_combined
from granola.prosemirror.converter import to_markdown
from granola.writers.sync_writer import ExportDoc, SyncWriter

console = Console()


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
) -> None:
    """Export combined notes and transcripts with folder structure.

    This command fetches notes from the Granola API, reads transcripts from the local cache,
    and combines them into .txt files organized by Granola folder structure.

    Documents in multiple folders will be duplicated into each folder.
    Documents not in any folder will be placed in the root directory.
    Files are synced incrementally - only updated when the source changes.
    Deleted documents are removed from the output directory.
    """
    from granola.cli.main import state, resolve_path

    # 1. Get supabase path
    supabase_path = state.supabase
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

    # 3. Read cache for transcripts and folders
    cache_path = resolve_path(cache) if cache else get_default_cache_path()

    state.logger.info(f"Reading cache file from {cache_path}")
    try:
        cache_data = read_cache(cache_path)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to read cache file: {e}")
        raise typer.Exit(1)

    state.logger.info(
        f"Loaded cache data: {len(cache_data.transcripts)} transcripts, "
        f"{len(cache_data.folders)} folders"
    )

    # 4. Build export documents by merging API docs with cache data
    all_doc_ids: set[str] = set()
    export_docs: list[ExportDoc] = []

    for api_doc in api_docs:
        all_doc_ids.add(api_doc.id)

        # Get folder names for this document
        folders = cache_data.get_folder_names(api_doc.id)

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
        ))

    # 4b. Process shared documents from cache
    state.logger.info(f"Processing {len(cache_data.shared_documents)} shared documents")
    for shared_doc in cache_data.shared_documents.values():
        # Skip if we already have this document from the API
        if shared_doc.id in all_doc_ids:
            continue

        all_doc_ids.add(shared_doc.id)

        # Get folder names for this document
        folders = cache_data.get_folder_names(shared_doc.id)

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
        ))

    # 5. Resolve output directory
    output_dir = resolve_path(output) if output else default_export_output()

    console.print(f"Syncing {len(export_docs)} documents to {output_dir}...")
    state.logger.info(f"Starting sync to {output_dir}, {len(export_docs)} documents")

    # 6. Sync to filesystem
    sync_writer = SyncWriter(output_dir, logger=state.logger)
    try:
        stats = sync_writer.sync(export_docs, all_doc_ids)
    except Exception as e:
        console.print(f"[red]Error:[/red] Sync failed: {e}")
        raise typer.Exit(1)

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
