"""Notes export command."""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from granola.api.auth import AuthError, get_access_token
from granola.api.client import APIError, GranolaClient
from granola.formatters.markdown import to_markdown_file
from granola.writers.file_writer import write_documents

console = Console()


def default_notes_output() -> Path:
    """Return the default output directory for notes."""
    return Path.home() / "My Drive" / "z. Granola Notes" / "Markdown"


def notes_cmd(
    timeout: Annotated[
        int,
        typer.Option("--timeout", help="HTTP timeout in seconds"),
    ] = 120,
    output: Annotated[
        Optional[str],
        typer.Option("--output", help="Output directory for exported Markdown files"),
    ] = None,
) -> None:
    """Export Granola notes to Markdown files."""
    from granola.cli.main import state, resolve_path

    # Get supabase path
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

    # Fetch documents from API
    console.print("Fetching documents from Granola API...")
    state.logger.info(f"Fetching documents from Granola API (timeout={timeout}s)")

    try:
        client = GranolaClient(access_token, timeout=timeout)
        documents = client.get_documents()
    except APIError as e:
        console.print(f"[red]Error:[/red] API request failed: {e}")
        raise typer.Exit(1)

    state.logger.info(f"Retrieved {len(documents)} documents")

    # Resolve output directory
    output_dir = resolve_path(output) if output else default_notes_output()

    console.print(f"Exporting {len(documents)} notes to {output_dir}...")
    state.logger.info(f"Writing documents to Markdown files in {output_dir}")

    # Write documents
    try:
        written = write_documents(
            documents,
            output_dir,
            converter=to_markdown_file,
            extension=".md",
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to write files: {e}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Export completed successfully ({written} files written)")
    state.logger.info(f"Export completed successfully, {written} files written")
