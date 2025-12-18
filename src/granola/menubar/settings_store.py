"""Thread-safe settings store with atomic writes and subscriber notifications."""

import json
import os
import tempfile
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional


def get_config_dir() -> Path:
    """Return the config directory, creating it if needed."""
    config_dir = Path.home() / ".config" / "granola"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_settings_path() -> Path:
    """Return the path to the settings file."""
    return get_config_dir() / "settings.json"


@dataclass
class SettingsData:
    """Application settings data."""

    # Sync configuration
    output_folder: str = ""
    excluded_folders: list[str] = field(default_factory=list)
    excluded_folders_updated: Optional[str] = None  # ISO timestamp
    sync_interval_minutes: int = 15
    auto_sync_enabled: bool = True

    # Paths
    supabase_path: str = ""
    cache_path: str = ""

    # State
    last_sync_time: Optional[str] = None
    last_sync_status: str = "never"  # "success", "error", "never"
    last_sync_message: str = ""

    # Sync stats
    last_sync_added: int = 0
    last_sync_updated: int = 0
    last_sync_moved: int = 0
    last_sync_deleted: int = 0
    last_sync_skipped: int = 0

    # App settings
    start_at_login: bool = False
    notification_level: str = "verbose"  # "verbose", "errors", "none"

    # Webhooks configuration
    webhooks: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Set default paths if not provided."""
        if not self.supabase_path:
            default_supabase = Path.home() / "Library" / "Application Support" / "Granola" / "supabase.json"
            if default_supabase.exists():
                self.supabase_path = str(default_supabase)

        if not self.cache_path:
            default_cache = Path.home() / "Library" / "Application Support" / "Granola" / "cache-v3.json"
            if default_cache.exists():
                self.cache_path = str(default_cache)

        if not self.output_folder:
            # Try common locations
            for folder in [
                Path.home() / "Google Drive" / "My Drive" / "z. Granola Notes",
                Path.home() / "My Drive" / "z. Granola Notes",
            ]:
                if folder.exists():
                    self.output_folder = str(folder)
                    break
            # Try glob pattern for CloudStorage
            import glob
            matches = glob.glob(str(Path.home() / "Library" / "CloudStorage" / "GoogleDrive-*" / "My Drive" / "z. Granola Notes"))
            if matches and not self.output_folder:
                self.output_folder = matches[0]


# Subscriber callback type: called with key name that changed
SettingsSubscriber = Callable[[str], None]


class SettingsStore:
    """Thread-safe settings store with atomic writes and change notifications.

    Usage:
        store = SettingsStore.shared()

        # Subscribe to changes
        store.subscribe(lambda key: print(f"{key} changed"))

        # Get values
        folder = store.output_folder

        # Set values (automatically saves and notifies)
        store.output_folder = "/new/path"
    """

    _instance: Optional["SettingsStore"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._data: SettingsData = SettingsData()
        self._subscribers: list[SettingsSubscriber] = []
        self._write_lock = threading.Lock()
        self._load()

    @classmethod
    def shared(cls) -> "SettingsStore":
        """Get the shared singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _load(self) -> None:
        """Load settings from disk."""
        import dataclasses
        settings_path = get_settings_path()
        if settings_path.exists():
            try:
                data = json.loads(settings_path.read_text())
                # Handle legacy show_notifications field
                if "show_notifications" in data and "notification_level" not in data:
                    data["notification_level"] = "verbose" if data["show_notifications"] else "none"
                # Handle legacy sync_interval without auto_sync_enabled
                if "auto_sync_enabled" not in data:
                    data["auto_sync_enabled"] = data.get("sync_interval_minutes", 15) > 0
                # Filter to only valid dataclass fields
                valid_fields = {f.name for f in dataclasses.fields(SettingsData)}
                self._data = SettingsData(**{k: v for k, v in data.items() if k in valid_fields})
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Failed to load settings: {e}")
                self._data = SettingsData()
        else:
            self._data = SettingsData()

    def _save_atomic(self) -> None:
        """Save settings atomically using temp file + fsync + rename."""
        settings_path = get_settings_path()

        with self._write_lock:
            # Write to temp file in same directory (for atomic rename)
            fd, tmp_path = tempfile.mkstemp(
                dir=settings_path.parent,
                prefix=".settings_",
                suffix=".tmp"
            )
            try:
                data_dict = asdict(self._data)
                json_bytes = json.dumps(data_dict, indent=2).encode("utf-8")
                os.write(fd, json_bytes)
                os.fsync(fd)
                os.close(fd)

                # Atomic replace
                os.replace(tmp_path, settings_path)
            except Exception:
                os.close(fd)
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

    def _notify(self, key: str) -> None:
        """Notify all subscribers of a change."""
        for subscriber in self._subscribers:
            try:
                subscriber(key)
            except Exception as e:
                print(f"Settings subscriber error: {e}")

    def subscribe(self, callback: SettingsSubscriber) -> Callable[[], None]:
        """Subscribe to settings changes.

        Args:
            callback: Function called with key name when a setting changes.

        Returns:
            Unsubscribe function.
        """
        self._subscribers.append(callback)

        def unsubscribe():
            if callback in self._subscribers:
                self._subscribers.remove(callback)

        return unsubscribe

    def reload(self) -> None:
        """Reload settings from disk."""
        self._load()

    # === Property accessors with auto-save and notification ===

    @property
    def output_folder(self) -> str:
        return self._data.output_folder

    @output_folder.setter
    def output_folder(self, value: str) -> None:
        if self._data.output_folder != value:
            self._data.output_folder = value
            self._save_atomic()
            self._notify("output_folder")

    @property
    def excluded_folders(self) -> list[str]:
        return self._data.excluded_folders.copy()

    @excluded_folders.setter
    def excluded_folders(self, value: list[str]) -> None:
        if self._data.excluded_folders != value:
            from datetime import datetime, timezone
            self._data.excluded_folders = list(value)
            self._data.excluded_folders_updated = datetime.now(timezone.utc).isoformat()
            self._save_atomic()
            self._notify("excluded_folders")

    @property
    def excluded_folders_updated(self) -> Optional[str]:
        return self._data.excluded_folders_updated

    @property
    def sync_interval_minutes(self) -> int:
        return self._data.sync_interval_minutes

    @sync_interval_minutes.setter
    def sync_interval_minutes(self, value: int) -> None:
        if self._data.sync_interval_minutes != value:
            self._data.sync_interval_minutes = value
            self._save_atomic()
            self._notify("sync_interval_minutes")

    @property
    def auto_sync_enabled(self) -> bool:
        return self._data.auto_sync_enabled

    @auto_sync_enabled.setter
    def auto_sync_enabled(self, value: bool) -> None:
        if self._data.auto_sync_enabled != value:
            self._data.auto_sync_enabled = value
            self._save_atomic()
            self._notify("auto_sync_enabled")

    @property
    def supabase_path(self) -> str:
        return self._data.supabase_path

    @property
    def cache_path(self) -> str:
        return self._data.cache_path

    @property
    def last_sync_time(self) -> Optional[str]:
        return self._data.last_sync_time

    @last_sync_time.setter
    def last_sync_time(self, value: Optional[str]) -> None:
        self._data.last_sync_time = value
        self._save_atomic()

    @property
    def last_sync_status(self) -> str:
        return self._data.last_sync_status

    @last_sync_status.setter
    def last_sync_status(self, value: str) -> None:
        self._data.last_sync_status = value
        self._save_atomic()

    @property
    def last_sync_message(self) -> str:
        return self._data.last_sync_message

    @last_sync_message.setter
    def last_sync_message(self, value: str) -> None:
        self._data.last_sync_message = value
        self._save_atomic()

    @property
    def last_sync_added(self) -> int:
        return self._data.last_sync_added

    @last_sync_added.setter
    def last_sync_added(self, value: int) -> None:
        self._data.last_sync_added = value

    @property
    def last_sync_updated(self) -> int:
        return self._data.last_sync_updated

    @last_sync_updated.setter
    def last_sync_updated(self, value: int) -> None:
        self._data.last_sync_updated = value

    @property
    def last_sync_moved(self) -> int:
        return self._data.last_sync_moved

    @last_sync_moved.setter
    def last_sync_moved(self, value: int) -> None:
        self._data.last_sync_moved = value

    @property
    def last_sync_deleted(self) -> int:
        return self._data.last_sync_deleted

    @last_sync_deleted.setter
    def last_sync_deleted(self, value: int) -> None:
        self._data.last_sync_deleted = value

    @property
    def last_sync_skipped(self) -> int:
        return self._data.last_sync_skipped

    @last_sync_skipped.setter
    def last_sync_skipped(self, value: int) -> None:
        self._data.last_sync_skipped = value

    @property
    def start_at_login(self) -> bool:
        return self._data.start_at_login

    @start_at_login.setter
    def start_at_login(self, value: bool) -> None:
        if self._data.start_at_login != value:
            self._data.start_at_login = value
            self._save_atomic()
            self._notify("start_at_login")

    @property
    def notification_level(self) -> str:
        return self._data.notification_level

    @notification_level.setter
    def notification_level(self, value: str) -> None:
        if self._data.notification_level != value:
            self._data.notification_level = value
            self._save_atomic()
            self._notify("notification_level")

    @property
    def webhooks(self) -> list[dict]:
        return [dict(w) for w in self._data.webhooks]

    @webhooks.setter
    def webhooks(self, value: list[dict]) -> None:
        self._data.webhooks = [dict(w) for w in value]
        self._save_atomic()
        self._notify("webhooks")

    def update_sync_stats(
        self,
        added: int = 0,
        updated: int = 0,
        moved: int = 0,
        deleted: int = 0,
        skipped: int = 0,
    ) -> None:
        """Update sync statistics (batched save)."""
        self._data.last_sync_added = added
        self._data.last_sync_updated = updated
        self._data.last_sync_moved = moved
        self._data.last_sync_deleted = deleted
        self._data.last_sync_skipped = skipped
        self._save_atomic()

    def save(self) -> None:
        """Force save current state."""
        self._save_atomic()
