"""File writer with sanitization and incremental updates."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

from granola.api.models import Document
from granola.utils.filename import make_unique, sanitize_filename

T = TypeVar("T")


def write_documents(
    docs: list[Document],
    output_dir: Path,
    converter: Callable[[Document], str],
    extension: str = ".md",
) -> int:
    """Write documents to files with incremental updates.

    Args:
        docs: List of documents to write.
        output_dir: Directory to write files to.
        converter: Function to convert document to string content.
        extension: File extension (default: .md).

    Returns:
        Number of files written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    used_filenames: dict[str, int] = {}
    written = 0

    for doc in docs:
        # Generate unique filename
        filename = sanitize_filename(doc.title or doc.id, fallback=doc.id)
        filename = make_unique(filename, used_filenames)
        used_filenames[filename] = used_filenames.get(filename, 0) + 1

        file_path = output_dir / f"{filename}{extension}"

        # Check if file needs updating
        if not should_update_file(file_path, doc.updated_at):
            continue

        # Convert and write
        content = converter(doc)
        file_path.write_text(content)
        written += 1

    return written


def should_update_file(file_path: Path, updated_at: str) -> bool:
    """Check if file needs updating based on timestamps.

    Args:
        file_path: Path to the file.
        updated_at: Document's updated_at timestamp (ISO 8601).

    Returns:
        True if the file should be written.
    """
    # If file doesn't exist, we should write it
    if not file_path.exists():
        return True

    # Parse the document's updated_at timestamp
    try:
        ts = updated_at.replace("Z", "+00:00")
        doc_updated_at = datetime.fromisoformat(ts)
    except ValueError:
        # If we can't parse the timestamp, write the file to be safe
        return True

    # Get the file's modification time
    try:
        file_mtime = file_path.stat().st_mtime
        # Convert to datetime with timezone awareness
        file_updated_at = datetime.fromtimestamp(file_mtime, tz=timezone.utc)
    except OSError:
        return True

    # Normalize both to UTC for comparison
    if doc_updated_at.tzinfo is None:
        doc_updated_at = doc_updated_at.replace(tzinfo=timezone.utc)

    # Write the file if the document is newer than the existing file
    return doc_updated_at > file_updated_at
