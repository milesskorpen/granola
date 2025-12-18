"""Data models for webhook support."""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class WebhookConfig:
    """Configuration for a single webhook endpoint."""

    name: str
    url: str
    method: str = "POST"
    enabled: bool = True
    folders: list[str] = field(default_factory=list)  # If empty, fire for all folders

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WebhookConfig":
        """Create a WebhookConfig from a dictionary."""
        # Support both legacy "folder" (str) and new "folders" (list)
        folders = data.get("folders", [])
        if not folders and data.get("folder"):
            # Migrate from legacy single folder to list
            folders = [data["folder"]]
        return cls(
            name=data.get("name", ""),
            url=data.get("url", ""),
            method=data.get("method", "POST").upper(),
            enabled=data.get("enabled", True),
            folders=folders,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def is_valid(self) -> bool:
        """Check if the webhook config is valid."""
        return bool(self.name and self.url and self.method in ("GET", "POST", "PUT", "PATCH"))

    def matches_folder(self, doc_folders: list[str]) -> bool:
        """Check if this webhook should fire for a document in the given folders."""
        if not self.folders:
            return True  # No folder filter, fire for all
        # Check if any of the webhook's folders match any of the document's folders
        return bool(set(self.folders) & set(doc_folders))


@dataclass
class WebhookDocument:
    """Document data included in webhook payload."""

    id: str
    title: str
    created_at: str
    updated_at: str
    folders: list[str]
    file_path: str
    markdown_content: str  # Combined content (for backwards compatibility)
    notes_content: str  # Just the notes section
    transcript_content: str  # Just the transcript section
    has_notes: bool
    has_transcript: bool
    webhook_folder_filters: list[str]  # Which folder filters triggered this webhook (empty = all folders)


@dataclass
class WebhookPayload:
    """Payload sent to webhook endpoints."""

    event: str  # "document.created" | "document.updated"
    timestamp: str  # ISO 8601
    document: WebhookDocument

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event": self.event,
            "timestamp": self.timestamp,
            "document": asdict(self.document),
        }

    @classmethod
    def create(
        cls,
        event: str,
        doc_id: str,
        title: str,
        created_at: str,
        updated_at: str,
        folders: list[str],
        file_path: str,
        markdown_content: str,
        notes_content: str,
        transcript_content: str,
        has_notes: bool,
        has_transcript: bool,
        webhook_folder_filters: list[str] | None = None,
    ) -> "WebhookPayload":
        """Create a webhook payload with current timestamp."""
        return cls(
            event=event,
            timestamp=datetime.now(timezone.utc).isoformat(),
            document=WebhookDocument(
                id=doc_id,
                title=title,
                created_at=created_at,
                updated_at=updated_at,
                folders=folders,
                file_path=file_path,
                markdown_content=markdown_content,
                notes_content=notes_content,
                transcript_content=transcript_content,
                has_notes=has_notes,
                has_transcript=has_transcript,
                webhook_folder_filters=webhook_folder_filters or [],
            ),
        )


@dataclass
class WebhookResult:
    """Result of a webhook call."""

    success: bool
    webhook_name: str
    status_code: int | None = None
    error_message: str | None = None


@dataclass
class WebhookHistoryEntry:
    """A single entry in the webhook call history."""

    id: str  # Unique ID for this history entry
    timestamp: str  # ISO 8601 timestamp of when the call was made
    webhook_name: str
    url: str
    method: str
    payload: dict[str, Any]  # The full payload that was sent
    success: bool
    status_code: int | None = None
    error_message: str | None = None
    document_title: str = ""  # For easy display in history list

    @classmethod
    def create(
        cls,
        webhook_config: "WebhookConfig",
        payload: dict[str, Any],
        result: "WebhookResult",
    ) -> "WebhookHistoryEntry":
        """Create a history entry from a webhook call."""
        import uuid

        doc_title = ""
        if "document" in payload and "title" in payload["document"]:
            doc_title = payload["document"]["title"]

        return cls(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            webhook_name=webhook_config.name,
            url=webhook_config.url,
            method=webhook_config.method,
            payload=payload,
            success=result.success,
            status_code=result.status_code,
            error_message=result.error_message,
            document_title=doc_title,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WebhookHistoryEntry":
        """Create a history entry from a dictionary."""
        return cls(
            id=data.get("id", ""),
            timestamp=data.get("timestamp", ""),
            webhook_name=data.get("webhook_name", ""),
            url=data.get("url", ""),
            method=data.get("method", "POST"),
            payload=data.get("payload", {}),
            success=data.get("success", False),
            status_code=data.get("status_code"),
            error_message=data.get("error_message"),
            document_title=data.get("document_title", ""),
        )
