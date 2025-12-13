"""Transcripts export command."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from granola.cache.reader import CacheDocument, get_default_cache_path, read_cache
from granola.formatters.transcript import format_transcript
from granola.utils.filename import make_unique, sanitize_filename

console = Console()


def transcripts_cmd(
    cache: Annotated[
        Optional[str],
        typer.Option("--cache", help="Path to Granola cache file"),
    ] = None,
    output: Annotated[
        Optional[str],
        typer.Option("--output", help="Output directory for exported transcript files"),
    ] = None,
) -> None:
    """Export Granola transcripts to text files."""
    from granola.cli.main import state, resolve_path

    # Resolve cache path
    cache_path = resolve_path(cache) if cache else get_default_cache_path()

    if not cache_path.exists():
        console.print(f"[red]Error:[/red] Cache file not found at {cache_path}")
        raise typer.Exit(1)

    # Read cache
    console.print("Reading Granola cache file...")
    state.logger.info(f"Reading Granola cache file from {cache_path}")

    try:
        cache_data = read_cache(cache_path)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to read cache file: {e}")
        raise typer.Exit(1)

    state.logger.info(
        f"Loaded cache data: {len(cache_data.documents)} documents, "
        f"{len(cache_data.transcripts)} transcripts"
    )

    # Resolve output directory
    output_dir = resolve_path(output) if output else Path("./transcripts")
    output_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"Exporting {len(cache_data.transcripts)} transcripts to {output_dir}...")
    state.logger.info(f"Writing transcripts to {output_dir}")

    # Write transcripts
    used_filenames: dict[str, int] = {}
    count = 0

    for doc_id, segments in cache_data.transcripts.items():
        # Skip if no segments
        if not segments:
            continue

        # Get document info
        doc = cache_data.documents.get(doc_id)
        if not doc:
            doc = CacheDocument(id=doc_id, title=doc_id, created_at="", updated_at="")

        # Generate filename
        filename = sanitize_filename(doc.title or doc.id, fallback=doc.id)
        filename = make_unique(filename, used_filenames)
        used_filenames[filename] = used_filenames.get(filename, 0) + 1

        file_path = output_dir / f"{filename}.txt"

        # Check if file needs updating
        if not _should_update_file(doc, file_path):
            continue

        # Format transcript
        content = format_transcript(doc, segments)
        if not content:
            continue

        # Write file
        try:
            file_path.write_text(content)
            count += 1
        except Exception as e:
            console.print(f"[red]Error:[/red] Failed to write {file_path}: {e}")
            raise typer.Exit(1)

    console.print(f"[green]✓[/green] Export completed successfully ({count} files written)")
    state.logger.info(f"Export completed successfully, {count} files written")


def _should_update_file(doc: CacheDocument, file_path: Path) -> bool:
    """Check if the file needs to be updated based on timestamps."""
    if not file_path.exists():
        return True

    if not doc.updated_at:
        return True

    try:
        ts = doc.updated_at.replace("Z", "+00:00")
        doc_updated = datetime.fromisoformat(ts)
    except ValueError:
        return True

    try:
        file_mtime = file_path.stat().st_mtime
        file_updated = datetime.fromtimestamp(file_mtime, tz=timezone.utc)
    except OSError:
        return True

    if doc_updated.tzinfo is None:
        doc_updated = doc_updated.replace(tzinfo=timezone.utc)

    return doc_updated > file_updated
