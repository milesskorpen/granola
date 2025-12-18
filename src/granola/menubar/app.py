"""Wholesail Manager menu bar application."""

import json
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import rumps
from importlib import resources as importlib_resources

from granola.menubar.settings import (
    Settings,
    get_available_folders,
    get_launchd_plist_path,
)

# Launchd plist for starting at login
LOGIN_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / "com.granola.menubar.plist"
LOGIN_PLIST_LABEL = "com.granola.menubar"


def notify(title: str, subtitle: str, message: str, is_error: bool = False) -> None:
    """Send a notification without sound.

    Args:
        title: Notification title.
        subtitle: Notification subtitle.
        message: Notification message.
        is_error: Whether this is an error notification.
    """
    rumps.notification(title, subtitle, message, sound=False)


# Global reference to app for notification level checking
_app_instance: "WholesailManagerApp | None" = None


def should_notify(is_error: bool = False) -> bool:
    """Check if we should send a notification based on settings.

    Args:
        is_error: Whether this is an error notification.

    Returns:
        True if notification should be sent.
    """
    if _app_instance is None:
        return True

    level = _app_instance.settings.notification_level
    if level == "none":
        return False
    if level == "errors":
        return is_error
    # "verbose" - always notify
    return True


class WholesailManagerApp(rumps.App):
    """Menu bar app for Wholesail Manager."""

    def __init__(self):
        # Try to load app icon from various locations
        icon_path: str | None = None

        # List of potential icon locations to check
        icon_candidates = [
            # Project root (for development)
            Path(__file__).parent.parent.parent.parent / "app_icon.png",
            # Packaged assets directory
            Path(__file__).parent / "assets" / "app_icon.png",
            # macOS app bundle Resources directory
            Path(sys.executable).parent.parent / "Resources" / "app_icon.png",
        ]

        # Try importlib resources for packaged distribution
        try:
            icon_res = importlib_resources.files("granola.menubar").joinpath("assets/app_icon.png")
            if hasattr(icon_res, "is_file") and icon_res.is_file():
                icon_candidates.insert(0, Path(str(icon_res)))
        except Exception:
            pass

        # Find first existing icon
        for candidate in icon_candidates:
            if candidate.exists():
                icon_path = str(candidate)
                break

        self._using_icon = icon_path is not None

        super().__init__(
            "Wholesail Manager",
            icon=icon_path,
            title=None if icon_path else "🚢",
            quit_button=None,  # We'll add our own
        )

        self.settings = Settings.load()
        self.syncing = False

        # Set global reference for notification level checking
        global _app_instance
        _app_instance = self

        # Build menu
        self.status_item = rumps.MenuItem("Status: Ready")
        self.status_item.set_callback(None)

        self.last_sync_item = rumps.MenuItem(self._get_last_sync_text())
        self.last_sync_item.set_callback(None)

        self.last_sync_stats_item = rumps.MenuItem(self._get_last_sync_stats_text())
        self.last_sync_stats_item.set_callback(None)

        # Start at login menu item
        self.start_at_login_item = rumps.MenuItem(
            "Start at Login",
            callback=self.toggle_start_at_login,
        )
        self.start_at_login_item.state = self._is_login_item_installed()

        self.menu = [
            self.status_item,
            self.last_sync_item,
            self.last_sync_stats_item,
            None,  # Separator
            rumps.MenuItem("Sync Now", callback=self.sync_now),
            None,  # Separator
            rumps.MenuItem("Settings...", callback=self.open_settings_panel),
            self.start_at_login_item,
            None,  # Separator
            rumps.MenuItem("Restart", callback=self.restart_app),
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

        # Start auto-sync timer if enabled
        self._setup_timer()

    def _get_last_sync_text(self) -> str:
        """Get formatted last sync text."""
        if self.settings.last_sync_time:
            try:
                last = datetime.fromisoformat(self.settings.last_sync_time)
                time_str = last.strftime("%-I:%M %p").lower()  # e.g., "3:25 pm"
                status = "✓" if self.settings.last_sync_status == "success" else "✗"
                return f"Last sync: {status} {time_str}"
            except ValueError:
                pass
        return "Last sync: Never"

    def _get_last_sync_stats_text(self) -> str:
        """Get formatted sync stats text."""
        if self.settings.last_sync_status == "never":
            return "Stats: No sync yet"

        parts = []
        if self.settings.last_sync_added > 0:
            parts.append(f"{self.settings.last_sync_added} added")
        if self.settings.last_sync_updated > 0:
            parts.append(f"{self.settings.last_sync_updated} updated")
        if self.settings.last_sync_moved > 0:
            parts.append(f"{self.settings.last_sync_moved} moved")
        if self.settings.last_sync_deleted > 0:
            parts.append(f"{self.settings.last_sync_deleted} deleted")

        if parts:
            return f"Stats: {', '.join(parts)}"
        elif self.settings.last_sync_skipped > 0:
            return f"Stats: {self.settings.last_sync_skipped} unchanged"
        else:
            return "Stats: No changes"

    def _setup_timer(self) -> None:
        """Setup the auto-sync timer."""
        if hasattr(self, "_timer") and self._timer:
            self._timer.stop()
            self._timer = None

        if self.settings.sync_interval_minutes > 0:
            interval = self.settings.sync_interval_minutes * 60
            self._timer = rumps.Timer(self._auto_sync, interval)
            self._timer.start()

    def _auto_sync(self, _) -> None:
        """Called by timer for auto-sync."""
        if not self.syncing:
            self._do_sync()

    @rumps.clicked("Sync Now")
    def sync_now(self, _) -> None:
        """Manually trigger a sync."""
        if self.syncing:
            if should_notify():
                notify(
                    "Wholesail Manager",
                    "Sync in progress",
                    "Please wait for the current sync to complete.",
                )
            return
        self._do_sync()

    def _do_sync(self) -> None:
        """Perform the actual sync in a background thread."""
        if not self.settings.output_folder:
            if should_notify(is_error=True):
                notify(
                    "Wholesail Manager",
                    "Configuration needed",
                    "Please set an output folder in Settings.",
                )
            return

        self.syncing = True
        self.status_item.title = "Status: Syncing..."
        if not self._using_icon:
            self.title = "🔄"

        def sync_thread():
            try:
                from granola.cli.export import run_export

                # Get enabled webhook configs
                webhook_configs = [
                    w for w in self.settings.webhooks
                    if w.get("enabled", True)
                ]

                # Run export directly
                result = run_export(
                    output_folder=self.settings.output_folder,
                    supabase_path=self.settings.supabase_path or None,
                    cache_path=self.settings.cache_path or None,
                    excluded_folders=list(self.settings.excluded_folders),
                    webhook_configs=webhook_configs if webhook_configs else None,
                    timeout=120,
                )

                # Update status
                self.settings.last_sync_time = datetime.now().isoformat()
                if result.success:
                    self.settings.last_sync_status = "success"
                    self.settings.last_sync_added = result.added
                    self.settings.last_sync_updated = result.updated
                    self.settings.last_sync_moved = result.moved
                    self.settings.last_sync_deleted = result.deleted
                    self.settings.last_sync_skipped = result.skipped

                    # Build message
                    parts = []
                    if result.added > 0:
                        parts.append(f"{result.added} added")
                    if result.updated > 0:
                        parts.append(f"{result.updated} updated")
                    if result.moved > 0:
                        parts.append(f"{result.moved} moved")
                    if result.deleted > 0:
                        parts.append(f"{result.deleted} deleted")
                    if parts:
                        self.settings.last_sync_message = ", ".join(parts)
                    else:
                        self.settings.last_sync_message = f"{result.skipped} unchanged"

                    if should_notify(is_error=False):
                        notify(
                            "Wholesail Manager",
                            "Sync completed",
                            self.settings.last_sync_message,
                        )
                else:
                    self.settings.last_sync_status = "error"
                    self.settings.last_sync_message = result.error_message[:100]
                    # Reset stats on error
                    self.settings.last_sync_added = 0
                    self.settings.last_sync_updated = 0
                    self.settings.last_sync_moved = 0
                    self.settings.last_sync_deleted = 0
                    self.settings.last_sync_skipped = 0
                    if should_notify(is_error=True):
                        notify(
                            "Wholesail Manager",
                            "Sync failed",
                            self.settings.last_sync_message,
                        )

                self.settings.save()

            except Exception as e:
                import traceback
                self.settings.last_sync_status = "error"
                # Include traceback in error message for debugging
                tb = traceback.format_exc()
                self.settings.last_sync_message = f"{e}: {tb}"[:2000]
                self.settings.save()
                if should_notify(is_error=True):
                    notify("Wholesail Manager", "Sync failed", str(e)[:100])

            finally:
                self.syncing = False
                self.status_item.title = "Status: Ready"
                self.last_sync_item.title = self._get_last_sync_text()
                self.last_sync_stats_item.title = self._get_last_sync_stats_text()
                if not self._using_icon:
                    self.title = "🥣"

        thread = threading.Thread(target=sync_thread, daemon=True)
        thread.start()

    def open_settings_panel(self, _) -> None:
        """Open the settings panel as a separate process."""
        try:
            # In a py2app bundle, sys.executable points to the app bundle
            # We need to find the actual Python interpreter
            python_exe = sys.executable

            # Check if we're in a .app bundle
            if ".app/Contents/MacOS" in python_exe:
                # Use the python executable in the same directory
                bundle_python = Path(python_exe).parent / "python"
                if bundle_python.exists():
                    python_exe = str(bundle_python)

            subprocess.Popen(
                [
                    python_exe,
                    "-m",
                    "granola.menubar.settings_panel",
                    "--cache-path",
                    self.settings.cache_path or "",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            if should_notify(is_error=True):
                notify(
                    "Wholesail Manager",
                    "Error opening settings",
                    str(e)[:100],
                )

        # Schedule a reload of settings after a delay
        # to pick up any changes made in the panel
        def reload_settings_later():
            import time
            time.sleep(1)
            self.settings = Settings.load()
            self._setup_timer()  # Restart timer with potentially new interval

        thread = threading.Thread(target=reload_settings_later, daemon=True)
        thread.start()

    def _is_login_item_installed(self) -> bool:
        """Check if the app is set to start at login."""
        return LOGIN_PLIST_PATH.exists()

    def toggle_start_at_login(self, sender) -> None:
        """Toggle start at login."""
        if self._is_login_item_installed():
            self._uninstall_login_item()
            sender.state = 0
            if should_notify():
                notify(
                    "Wholesail Manager",
                    "Start at Login disabled",
                    "App will not start automatically",
                )
        else:
            self._install_login_item()
            sender.state = 1
            if should_notify():
                notify(
                    "Wholesail Manager",
                    "Start at Login enabled",
                    "App will start when you log in",
                )

    def _install_login_item(self) -> None:
        """Install launchd plist to start at login."""
        # Find the granola-menubar script
        script_path = Path(sys.executable).parent / "granola-menubar"
        if not script_path.exists():
            # Fallback to module execution
            program_args = f"""    <array>
        <string>{sys.executable}</string>
        <string>-m</string>
        <string>granola.menubar.app</string>
    </array>"""
        else:
            program_args = f"""    <array>
        <string>{script_path}</string>
    </array>"""

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LOGIN_PLIST_LABEL}</string>

    <key>ProgramArguments</key>
{program_args}

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <false/>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:{Path(sys.executable).parent}</string>
    </dict>
</dict>
</plist>
"""
        # Ensure LaunchAgents directory exists
        LOGIN_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Write plist
        LOGIN_PLIST_PATH.write_text(plist_content)

        # Load it
        subprocess.run(
            ["launchctl", "load", str(LOGIN_PLIST_PATH)],
            capture_output=True,
        )

    def _uninstall_login_item(self) -> None:
        """Remove launchd plist for login."""
        if LOGIN_PLIST_PATH.exists():
            # Unload first
            subprocess.run(
                ["launchctl", "unload", str(LOGIN_PLIST_PATH)],
                capture_output=True,
            )
            # Remove file
            try:
                LOGIN_PLIST_PATH.unlink()
            except Exception:
                pass

    def restart_app(self, _) -> None:
        """Restart the application."""
        # Get the path to the current script/executable
        script_path = Path(sys.executable).parent / "granola-menubar"
        if not script_path.exists():
            # Fallback to module execution
            cmd = [sys.executable, "-m", "granola.menubar.app"]
        else:
            cmd = [str(script_path)]

        # Start a new instance
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Quit the current instance
        rumps.quit_application()

    def quit_app(self, _) -> None:
        """Quit the application."""
        rumps.quit_application()


def main():
    """Entry point for the menu bar app."""
    app = WholesailManagerApp()
    app.run()


if __name__ == "__main__":
    main()
