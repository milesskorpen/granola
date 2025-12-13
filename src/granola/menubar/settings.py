"""Settings management for Granola Sync app."""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


def get_config_dir() -> Path:
    """Return the config directory, creating it if needed."""
    config_dir = Path.home() / ".config" / "granola"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_settings_path() -> Path:
    """Return the path to the settings file."""
    return get_config_dir() / "settings.json"


def get_launchd_plist_path() -> Path:
    """Return the path to the launchd plist."""
    return Path.home() / "Library" / "LaunchAgents" / "com.granola.sync.plist"


@dataclass
class Settings:
    """Application settings."""

    # Sync configuration
    output_folder: str = ""
    excluded_folders: list[str] = field(default_factory=list)
    sync_interval_minutes: int = 15

    # Paths
    supabase_path: str = ""
    cache_path: str = ""

    # State
    last_sync_time: Optional[str] = None
    last_sync_status: str = "never"  # "success", "error", "never"
    last_sync_message: str = ""

    # App settings
    start_at_login: bool = False
    show_notifications: bool = True

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
                Path.home() / "Library" / "CloudStorage" / "GoogleDrive-*" / "My Drive" / "z. Granola Notes",
                Path.home() / "My Drive" / "z. Granola Notes",
            ]:
                # Handle glob pattern
                if "*" in str(folder):
                    import glob
                    matches = glob.glob(str(folder))
                    if matches:
                        self.output_folder = matches[0]
                        break
                elif folder.exists():
                    self.output_folder = str(folder)
                    break

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from disk."""
        settings_path = get_settings_path()
        if settings_path.exists():
            try:
                data = json.loads(settings_path.read_text())
                return cls(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()

    def save(self) -> None:
        """Save settings to disk."""
        settings_path = get_settings_path()
        settings_path.write_text(json.dumps(asdict(self), indent=2))

    def update(self, **kwargs) -> None:
        """Update settings and save."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.save()


def get_available_folders(cache_path: Optional[str] = None) -> list[str]:
    """Get list of available Granola folders from cache."""
    if not cache_path:
        settings = Settings.load()
        cache_path = settings.cache_path

    if not cache_path or not Path(cache_path).exists():
        return []

    try:
        content = Path(cache_path).read_text()
        import json
        outer = json.loads(content)
        inner = json.loads(outer.get("cache", "{}"))
        state = inner.get("state", {})

        folders = []
        for folder_data in state.get("documentListsMetadata", {}).values():
            title = folder_data.get("title", "")
            if title:
                folders.append(title)

        return sorted(folders)
    except Exception:
        return []
