"""Launchd plist management for background syncing."""

import subprocess
import sys
from pathlib import Path

PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / "com.granola.sync.plist"
PLIST_LABEL = "com.granola.sync"


def create_plist(
    output_folder: str,
    interval_minutes: int = 15,
    excluded_folders: list[str] | None = None,
    supabase_path: str | None = None,
    cache_path: str | None = None,
) -> str:
    """Generate launchd plist XML content."""
    # Build command arguments
    args = [
        sys.executable,
        "-m",
        "granola.cli.main",
        "export",
        "--output",
        output_folder,
    ]

    if supabase_path:
        args.extend(["--supabase", supabase_path])

    if cache_path:
        args.extend(["--cache", cache_path])

    for folder in (excluded_folders or []):
        args.extend(["--exclude-folder", folder])

    # Build plist
    args_xml = "\n".join(f"        <string>{arg}</string>" for arg in args)

    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>

    <key>ProgramArguments</key>
    <array>
{args_xml}
    </array>

    <key>StartInterval</key>
    <integer>{interval_minutes * 60}</integer>

    <key>RunAtLoad</key>
    <true/>

    <key>StandardOutPath</key>
    <string>{Path.home()}/.config/granola/sync.log</string>

    <key>StandardErrorPath</key>
    <string>{Path.home()}/.config/granola/sync.error.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>
"""
    return plist


def install_plist(
    output_folder: str,
    interval_minutes: int = 15,
    excluded_folders: list[str] | None = None,
    supabase_path: str | None = None,
    cache_path: str | None = None,
) -> None:
    """Install and load the launchd plist."""
    # Unload existing if present
    uninstall_plist()

    # Create config directory
    config_dir = Path.home() / ".config" / "granola"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Ensure LaunchAgents directory exists
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Write plist
    plist_content = create_plist(
        output_folder=output_folder,
        interval_minutes=interval_minutes,
        excluded_folders=excluded_folders,
        supabase_path=supabase_path,
        cache_path=cache_path,
    )
    PLIST_PATH.write_text(plist_content)

    # Load plist
    subprocess.run(
        ["launchctl", "load", str(PLIST_PATH)],
        check=True,
        capture_output=True,
    )


def uninstall_plist() -> None:
    """Unload and remove the launchd plist."""
    if PLIST_PATH.exists():
        try:
            subprocess.run(
                ["launchctl", "unload", str(PLIST_PATH)],
                check=False,
                capture_output=True,
            )
        except Exception:
            pass

        try:
            PLIST_PATH.unlink()
        except Exception:
            pass


def is_installed() -> bool:
    """Check if the launchd job is installed and loaded."""
    if not PLIST_PATH.exists():
        return False

    result = subprocess.run(
        ["launchctl", "list", PLIST_LABEL],
        capture_output=True,
    )
    return result.returncode == 0


def get_status() -> dict:
    """Get status of the launchd job."""
    if not PLIST_PATH.exists():
        return {"installed": False, "running": False}

    result = subprocess.run(
        ["launchctl", "list", PLIST_LABEL],
        capture_output=True,
        text=True,
    )

    return {
        "installed": True,
        "running": result.returncode == 0,
        "output": result.stdout if result.returncode == 0 else result.stderr,
    }
