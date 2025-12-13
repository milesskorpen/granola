"""Main Typer CLI application for Granola."""

import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from dotenv import load_dotenv
from rich.console import Console

from granola import __version__

# Create the Typer app
app = typer.Typer(
    name="granola",
    help="An application for exporting Granola meeting notes.",
    no_args_is_help=True,
)

# Console for rich output
console = Console()

# Global state for config
class State:
    debug: bool = False
    supabase: Optional[Path] = None
    logger: logging.Logger = logging.getLogger("granola")


state = State()


def setup_logging(debug: bool) -> logging.Logger:
    """Configure logging based on debug flag."""
    logger = logging.getLogger("granola")
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)

    return logger


def resolve_path(input_path: Optional[str]) -> Optional[Path]:
    """Expand ~ and environment variables in paths."""
    if not input_path:
        return None

    import os
    path_str = input_path.strip()
    if not path_str:
        return None

    path_str = os.path.expandvars(path_str)
    path = Path(path_str).expanduser()
    return path.resolve()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"granola {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Enable debug logging"),
    ] = False,
    supabase: Annotated[
        Optional[str],
        typer.Option("--supabase", help="Path to supabase.json file"),
    ] = None,
    config: Annotated[
        Optional[str],
        typer.Option("--config", help="Path to config file"),
    ] = None,
    version: Annotated[
        Optional[bool],
        typer.Option("--version", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    """Granola CLI - Export notes and transcripts from Granola."""
    # Load .env file
    load_dotenv()

    # Setup logging
    state.debug = debug
    state.logger = setup_logging(debug)

    # Handle supabase path from flag, env, or config
    import os
    if supabase:
        state.supabase = resolve_path(supabase)
    elif os.environ.get("SUPABASE_FILE"):
        state.supabase = resolve_path(os.environ.get("SUPABASE_FILE"))

    if state.debug:
        state.logger.debug(f"Debug mode enabled")
        if state.supabase:
            state.logger.debug(f"Supabase file: {state.supabase}")


# Import and register subcommands
from granola.cli.notes import notes_cmd
from granola.cli.transcripts import transcripts_cmd
from granola.cli.export import export_cmd

app.command(name="notes")(notes_cmd)
app.command(name="transcripts")(transcripts_cmd)
app.command(name="export")(export_cmd)


if __name__ == "__main__":
    app()
