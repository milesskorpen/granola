"""Advanced sync writer with folder structure support."""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass
class ExportDoc:
    """A document to be exported with its folder assignments."""

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    content: str  # formatted content
    folders: list[str] = field(default_factory=list)  # folder names (empty = root)


@dataclass
class SyncStats:
    """Statistics about the sync operation."""

    added: int = 0
    updated: int = 0
    moved: int = 0
    deleted: int = 0
    skipped: int = 0


class SyncWriter:
    """Handles syncing documents to the filesystem with folder structure."""

    def __init__(self, output_dir: Path, logger: logging.Logger | None = None):
        """Initialize the sync writer.

        Args:
            output_dir: Root directory for exported files.
            logger: Optional logger for debug output.
        """
        self.output_dir = output_dir
        self.logger = logger or logging.getLogger(__name__)

    def sync(self, docs: list[ExportDoc], all_doc_ids: set[str]) -> SyncStats:
        """Synchronize documents to the output directory with folder structure.

        Handles adding, updating, moving, and deleting files as needed.

        Args:
            docs: Documents to sync.
            all_doc_ids: Set of all valid document IDs (for orphan detection).

        Returns:
            Statistics about the sync operation.
        """
        stats = SyncStats()

        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Scan existing files and build ID -> paths mapping
        existing_files = self._scan_existing_files()

        # Step 2: Process each document
        for doc in docs:
            doc_stats = self._process_document(doc, existing_files)
            stats.added += doc_stats.added
            stats.updated += doc_stats.updated
            stats.moved += doc_stats.moved
            stats.deleted += doc_stats.deleted
            stats.skipped += doc_stats.skipped

        # Step 3: Delete orphaned files (files whose doc IDs are not in all_doc_ids)
        for doc_id, paths in existing_files.items():
            # Use short ID matching (first 8 chars)
            if not any(full_id.startswith(doc_id) for full_id in all_doc_ids):
                for path in paths:
                    self.logger.debug(f"Deleting orphan: {path} (id: {doc_id})")
                    try:
                        path.unlink()
                        stats.deleted += 1
                    except OSError as e:
                        self.logger.warning(f"Failed to delete orphan {path}: {e}")

        # Step 4: Clean up empty folders
        self._clean_empty_folders()

        return stats

    def _scan_existing_files(self) -> dict[str, list[Path]]:
        """Walk the output directory and build a map of doc ID -> file paths.

        Extracts the ID from filenames in the format: title_shortid.txt
        """
        existing_files: dict[str, list[Path]] = {}

        for path in self.output_dir.rglob("*.txt"):
            if path.is_file():
                doc_id = _extract_id_from_filename(path.name)
                if doc_id:
                    if doc_id not in existing_files:
                        existing_files[doc_id] = []
                    existing_files[doc_id].append(path)

        return existing_files

    def _process_document(
        self, doc: ExportDoc, existing_files: dict[str, list[Path]]
    ) -> SyncStats:
        """Handle a single document: writes to appropriate folders.

        Removes from folders it no longer belongs to.
        """
        stats = SyncStats()

        filename = self._generate_filename(doc.title, doc.id, doc.created_at)

        # Get short ID for matching
        short_id = doc.id[:8] if len(doc.id) >= 8 else doc.id
        existing_paths = existing_files.get(short_id, [])

        # Determine target paths based on folders
        target_paths = self._get_target_paths(doc.folders, filename)

        # Build sets for quick lookup
        existing_path_set = set(existing_paths)
        target_path_set = set(target_paths)

        # Write to each target path
        for target_path in target_paths:
            # Create folder if needed
            target_path.parent.mkdir(parents=True, exist_ok=True)

            if target_path in existing_path_set:
                # File exists at this path - check if we need to update
                if self._should_update_file(target_path, doc.updated_at):
                    target_path.write_text(doc.content)
                    self.logger.debug(f"Updated: {target_path}")
                    stats.updated += 1
                else:
                    stats.skipped += 1
            else:
                # New path - write the file
                target_path.write_text(doc.content)
                self.logger.debug(f"Added: {target_path}")
                stats.added += 1

        # Remove files from folders they no longer belong to
        for existing_path in existing_paths:
            if existing_path not in target_path_set:
                self.logger.debug(f"Removing from old folder: {existing_path}")
                try:
                    existing_path.unlink()
                    stats.moved += 1
                except OSError as e:
                    self.logger.warning(f"Failed to remove old file {existing_path}: {e}")

        # Clear processed paths from existing_files to avoid double-deletion
        if short_id in existing_files:
            del existing_files[short_id]

        return stats

    def _get_target_paths(self, folders: list[str], filename: str) -> list[Path]:
        """Return the full paths where the document should be written."""
        if not folders:
            # No folders - place in "Uncategorized" folder
            return [self.output_dir / "Uncategorized" / filename]

        paths = []
        for folder in folders:
            sanitized_folder = _sanitize_folder_name(folder)
            paths.append(self.output_dir / sanitized_folder / filename)
        return paths

    def _generate_filename(self, title: str, doc_id: str, created_at: datetime) -> str:
        """Create a filename from date, title, and ID.

        Format: {YYYY-MM-DD}_{sanitized_title}_{short_id}.txt
        """
        # Format date as YYYY-MM-DD
        date_prefix = created_at.strftime("%Y-%m-%d")

        name = title.strip() if title else "untitled"

        # Sanitize the title
        name = INVALID_CHARS.sub("_", name)
        name = re.sub(r"_+", "_", name)
        name = name.strip("_")

        if not name:
            name = "untitled"

        # Limit title length to leave room for date and ID
        if len(name) > 70:
            name = name[:70]

        # Use first 8 chars of ID
        short_id = doc_id[:8] if len(doc_id) >= 8 else doc_id

        return f"{date_prefix}_{name}_{short_id}.txt"

    def _should_update_file(self, file_path: Path, doc_updated_at: datetime) -> bool:
        """Check if a file should be updated based on timestamps."""
        try:
            file_mtime = file_path.stat().st_mtime
            file_updated_at = datetime.fromtimestamp(file_mtime, tz=timezone.utc)
        except OSError:
            return True

        # Normalize doc_updated_at to UTC
        if doc_updated_at.tzinfo is None:
            doc_updated_at = doc_updated_at.replace(tzinfo=timezone.utc)

        return doc_updated_at > file_updated_at

    def _clean_empty_folders(self) -> None:
        """Remove empty directories from the output directory."""
        # Walk in reverse order (deepest first) to clean nested empty folders
        for path in sorted(self.output_dir.rglob("*"), reverse=True):
            if path.is_dir() and path != self.output_dir:
                try:
                    # Check if directory is empty
                    if not any(path.iterdir()):
                        self.logger.debug(f"Removing empty folder: {path}")
                        path.rmdir()
                except OSError:
                    pass  # Ignore errors


def _extract_id_from_filename(filename: str) -> str:
    """Extract the document ID from a filename.

    Expected format: title_shortid.txt
    """
    # Remove .txt extension
    name = filename.removesuffix(".txt")

    # Find the last underscore
    last_underscore = name.rfind("_")
    if last_underscore == -1 or last_underscore == len(name) - 1:
        return ""

    # Extract the ID portion (should be 8 chars for short ID)
    doc_id = name[last_underscore + 1 :]
    if len(doc_id) >= 8:
        return doc_id[:8]  # Return just the short ID for matching

    return ""


def _sanitize_folder_name(name: str) -> str:
    """Sanitize a folder name for use as a directory name."""
    name = name.strip()
    name = INVALID_CHARS.sub("_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_")

    if not name:
        name = "unnamed_folder"

    # Limit length
    if len(name) > 100:
        name = name[:100]

    return name
