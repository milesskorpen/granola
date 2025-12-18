"""Sync folder configuration management.

Stores sync preferences (like excluded folders) in the sync folder itself,
allowing settings to sync across multiple computers.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Config file name stored in the sync folder root
SYNC_CONFIG_FILENAME = ".granola-sync.json"


@dataclass
class SyncConfig:
    """Configuration stored in the sync folder."""

    excluded_folders: list[str] = field(default_factory=list)
    updated_at: str = ""  # ISO timestamp

    def __post_init__(self):
        if not self.updated_at:
            self.updated_at = datetime.now(timezone.utc).isoformat()


def load_sync_config(sync_folder: Path) -> Optional[SyncConfig]:
    """Load sync config from the sync folder.

    Args:
        sync_folder: Path to the sync output folder.

    Returns:
        SyncConfig if file exists and is valid, None otherwise.
    """
    config_path = sync_folder / SYNC_CONFIG_FILENAME
    if not config_path.exists():
        return None

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return SyncConfig(
            excluded_folders=data.get("excluded_folders", []),
            updated_at=data.get("updated_at", ""),
        )
    except (json.JSONDecodeError, OSError):
        return None


def save_sync_config(sync_folder: Path, config: SyncConfig) -> bool:
    """Save sync config to the sync folder.

    Args:
        sync_folder: Path to the sync output folder.
        config: Configuration to save.

    Returns:
        True if saved successfully, False otherwise.
    """
    config_path = sync_folder / SYNC_CONFIG_FILENAME

    try:
        # Ensure folder exists
        sync_folder.mkdir(parents=True, exist_ok=True)

        # Update timestamp
        config.updated_at = datetime.now(timezone.utc).isoformat()

        # Write atomically
        data = asdict(config)
        config_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True
    except OSError:
        return False


def merge_configs(
    local_excluded: list[str],
    local_updated: Optional[str],
    sync_config: Optional[SyncConfig],
) -> tuple[list[str], bool]:
    """Merge local and sync folder configurations.

    Uses the newer timestamp to determine which config takes precedence.

    Args:
        local_excluded: Excluded folders from local settings.
        local_updated: Timestamp of local settings (ISO format).
        sync_config: Config loaded from sync folder (may be None).

    Returns:
        Tuple of (merged excluded folders, whether local was updated).
    """
    if sync_config is None:
        # No sync config - use local
        return local_excluded, False

    if not local_updated:
        # No local timestamp - use sync config
        return sync_config.excluded_folders, True

    try:
        local_dt = datetime.fromisoformat(local_updated.replace("Z", "+00:00"))
        sync_dt = datetime.fromisoformat(sync_config.updated_at.replace("Z", "+00:00"))

        if sync_dt > local_dt:
            # Sync config is newer - update local
            return sync_config.excluded_folders, True
        else:
            # Local is newer or same - keep local
            return local_excluded, False
    except ValueError:
        # Parse error - prefer sync config if it exists
        return sync_config.excluded_folders, True


def get_effective_exclusions(
    sync_folder: Path,
    local_excluded: list[str],
    local_updated: Optional[str],
) -> tuple[list[str], SyncConfig]:
    """Get the effective exclusion list, merging local and sync folder configs.

    This is the main entry point for getting exclusions during sync.

    Args:
        sync_folder: Path to the sync output folder.
        local_excluded: Excluded folders from local app settings.
        local_updated: Timestamp of local settings.

    Returns:
        Tuple of (effective excluded folders, updated SyncConfig to save).
    """
    # Load sync folder config
    sync_config = load_sync_config(sync_folder)

    # Merge configs
    merged_excluded, local_was_updated = merge_configs(
        local_excluded, local_updated, sync_config
    )

    # Create the config to save back
    result_config = SyncConfig(excluded_folders=merged_excluded)

    return merged_excluded, result_config
