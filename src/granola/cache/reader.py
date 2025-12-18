"""Cache file reader for Granola local cache."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TranscriptSegment:
    """A single segment of speech in a transcript."""

    id: str
    document_id: str
    start_timestamp: str
    end_timestamp: str
    text: str
    source: str  # "system" or "microphone"
    is_final: bool


@dataclass
class CacheDocument:
    """A meeting document from the cache."""

    id: str
    title: str
    created_at: str
    updated_at: str


@dataclass
class Folder:
    """A document folder/list from Granola."""

    id: str
    title: str
    parent_id: Optional[str] = None


@dataclass
class SharedDocument:
    """A shared document from the cache with full content."""

    id: str
    title: str
    created_at: str
    updated_at: str
    notes_markdown: Optional[str] = None  # AI-generated notes in markdown
    last_viewed_panel: Optional[dict] = None  # Raw last_viewed_panel data


@dataclass
class CacheData:
    """Parsed cache data containing documents, transcripts, and folder structure."""

    documents: dict[str, CacheDocument] = field(default_factory=dict)
    transcripts: dict[str, list[TranscriptSegment]] = field(default_factory=dict)
    folders: dict[str, Folder] = field(default_factory=dict)
    doc_folders: dict[str, list[str]] = field(default_factory=dict)  # doc_id -> [folder_id]
    shared_documents: dict[str, SharedDocument] = field(default_factory=dict)

    def get_folder_names(self, doc_id: str) -> list[str]:
        """Get folder names for a given document ID.

        Args:
            doc_id: The document ID.

        Returns:
            List of folder names the document belongs to.
        """
        folder_ids = self.doc_folders.get(doc_id, [])
        names = []
        for folder_id in folder_ids:
            folder = self.folders.get(folder_id)
            if folder and folder.title:
                names.append(folder.title)
        return names


def read_cache(cache_path: Path) -> CacheData:
    """Read and parse the Granola cache file.

    The cache file is double-JSON encoded:
    - Outer JSON: {"cache": "<json-string>"}
    - Inner JSON: Contains state.documents, state.transcripts, etc.

    Args:
        cache_path: Path to the cache-v3.json file.

    Returns:
        Parsed CacheData object.

    Raises:
        FileNotFoundError: If the cache file doesn't exist.
        json.JSONDecodeError: If the JSON is invalid.
    """
    content = cache_path.read_text(encoding="utf-8")

    # Parse outer JSON
    outer = json.loads(content)
    cache_str = outer.get("cache", "")

    # Parse inner JSON
    inner = json.loads(cache_str)
    state = inner.get("state", {})

    # Parse documents
    documents: dict[str, CacheDocument] = {}
    for doc_id, doc_data in state.get("documents", {}).items():
        if isinstance(doc_data, dict):
            documents[doc_id] = CacheDocument(
                id=doc_id,
                title=doc_data.get("title", ""),
                created_at=doc_data.get("created_at", ""),
                updated_at=doc_data.get("updated_at", ""),
            )

    # Parse transcripts
    transcripts: dict[str, list[TranscriptSegment]] = {}
    for doc_id, segments_data in state.get("transcripts", {}).items():
        if isinstance(segments_data, list):
            segments = []
            for seg in segments_data:
                if isinstance(seg, dict):
                    segments.append(
                        TranscriptSegment(
                            id=seg.get("id", ""),
                            document_id=seg.get("document_id", doc_id),
                            start_timestamp=seg.get("start_timestamp", ""),
                            end_timestamp=seg.get("end_timestamp", ""),
                            text=seg.get("text", ""),
                            source=seg.get("source", ""),
                            is_final=seg.get("is_final", False),
                        )
                    )
            transcripts[doc_id] = segments

    # Parse folders (documentListsMetadata)
    folders: dict[str, Folder] = {}
    for folder_id, folder_data in state.get("documentListsMetadata", {}).items():
        if isinstance(folder_data, dict):
            folders[folder_id] = Folder(
                id=folder_id,
                title=folder_data.get("title", ""),
                parent_id=folder_data.get("parent_document_list_id"),
            )

    # Build doc -> folders mapping by inverting documentLists (folder_id -> [doc_id])
    doc_folders: dict[str, list[str]] = {}
    for folder_id, doc_ids in state.get("documentLists", {}).items():
        if isinstance(doc_ids, list):
            for doc_id in doc_ids:
                if doc_id not in doc_folders:
                    doc_folders[doc_id] = []
                doc_folders[doc_id].append(folder_id)

    # Parse shared documents
    shared_documents: dict[str, SharedDocument] = {}
    for doc_id, doc_data in state.get("sharedDocuments", {}).items():
        if isinstance(doc_data, dict):
            shared_documents[doc_id] = SharedDocument(
                id=doc_id,
                title=doc_data.get("title", ""),
                created_at=doc_data.get("created_at", ""),
                updated_at=doc_data.get("updated_at", ""),
                notes_markdown=doc_data.get("notes_markdown"),
                last_viewed_panel=doc_data.get("last_viewed_panel"),
            )

    return CacheData(
        documents=documents,
        transcripts=transcripts,
        folders=folders,
        doc_folders=doc_folders,
        shared_documents=shared_documents,
    )


def get_default_cache_path() -> Path:
    """Return the default cache file path for macOS.

    Returns:
        Path to ~/Library/Application Support/Granola/cache-v3.json
    """
    return Path.home() / "Library" / "Application Support" / "Granola" / "cache-v3.json"
