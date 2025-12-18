"""Webhook history storage and management."""

import json
from pathlib import Path
from typing import Callable

from granola.webhooks.models import WebhookHistoryEntry

# Maximum number of history entries to keep
MAX_HISTORY_ENTRIES = 100


def get_history_path() -> Path:
    """Return the path to the webhook history file."""
    config_dir = Path.home() / ".config" / "granola"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "webhook_history.json"


def load_history() -> list[WebhookHistoryEntry]:
    """Load webhook history from disk."""
    history_path = get_history_path()
    if not history_path.exists():
        return []

    try:
        data = json.loads(history_path.read_text())
        return [WebhookHistoryEntry.from_dict(entry) for entry in data]
    except (json.JSONDecodeError, TypeError, KeyError):
        return []


def save_history(entries: list[WebhookHistoryEntry]) -> None:
    """Save webhook history to disk."""
    history_path = get_history_path()
    data = [entry.to_dict() for entry in entries]
    history_path.write_text(json.dumps(data, indent=2))


def add_history_entry(entry: WebhookHistoryEntry) -> None:
    """Add a new entry to the history, maintaining the max size."""
    entries = load_history()
    entries.insert(0, entry)  # Add to front (most recent first)

    # Trim to max size
    if len(entries) > MAX_HISTORY_ENTRIES:
        entries = entries[:MAX_HISTORY_ENTRIES]

    save_history(entries)


def clear_history() -> None:
    """Clear all webhook history."""
    save_history([])


def delete_history_entry(entry_id: str) -> bool:
    """Delete a specific history entry by ID.

    Returns True if the entry was found and deleted.
    """
    entries = load_history()
    original_len = len(entries)
    entries = [e for e in entries if e.id != entry_id]

    if len(entries) < original_len:
        save_history(entries)
        return True
    return False


def get_history_entry(entry_id: str) -> WebhookHistoryEntry | None:
    """Get a specific history entry by ID."""
    entries = load_history()
    for entry in entries:
        if entry.id == entry_id:
            return entry
    return None
