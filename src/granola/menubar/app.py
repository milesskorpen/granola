"""Wholesail Manager menu bar application."""

import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import rumps
from AppKit import NSApp
from importlib import resources as importlib_resources

from granola.menubar.settings_store import SettingsStore

# Launchd plist for starting at login
LOGIN_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / "com.granola.menubar.plist"
LOGIN_PLIST_LABEL = "com.granola.menubar"


# Global reference to app for notification level checking
_app_instance: "WholesailManagerApp | None" = None


def notify(title: str, subtitle: str, message: str) -> None:
    """Send a notification without sound."""
    rumps.notification(title, subtitle, message, sound=False)


def should_notify(is_error: bool = False) -> bool:
    """Check if we should send a notification based on settings.

    Args:
        is_error: Whether this is an error notification.

    Returns:
        True if notification should be sent.
    """
    if _app_instance is None:
        return True

    level = _app_instance.store.notification_level
    if level == "none":
        return False
    if level == "errors":
        return is_error
    # "verbose" - always notify
    return True


class WholesailManagerApp(rumps.App):
    """Menu bar app for Wholesail Manager."""

    def __init__(self):
        # Try to load menu bar icon from various locations
        # Menu bar icons should be small (22x22 or 44x44 for @2x)
        icon_path: str | None = None

        # List of potential icon locations to check
        icon_candidates = [
            # Packaged assets directory (menubar-sized icon)
            Path(__file__).parent / "assets" / "menubar_icon.png",
            # macOS app bundle Resources directory
            Path(sys.executable).parent.parent / "Resources" / "menubar_icon.png",
            # Fallback to full-size app icon
            Path(__file__).parent.parent.parent.parent / "app_icon.png",
        ]

        # Try importlib resources for packaged distribution
        try:
            icon_res = importlib_resources.files("granola.menubar").joinpath("assets/menubar_icon.png")
            if hasattr(icon_res, "is_file") and icon_res.is_file():
                icon_candidates.insert(0, Path(str(icon_res)))
        except Exception:
            pass

        # Find first existing icon
        for candidate in icon_candidates:
            if candidate.exists():
                icon_path = str(candidate)
                print(f"[DEBUG] Found menu bar icon: {icon_path}")
                break
            else:
                print(f"[DEBUG] Icon not found at: {candidate}")

        self._using_icon = icon_path is not None
        if not self._using_icon:
            print("[DEBUG] No icon found, using emoji fallback")

        super().__init__(
            "Wholesail Manager",
            icon=icon_path,
            title=None if icon_path else "🚢",
            quit_button=None,  # We'll add our own
        )

        # Use the shared settings store
        self.store = SettingsStore.shared()
        self.syncing = False

        # Set global reference for notification level checking
        global _app_instance
        _app_instance = self

        # Subscribe to settings changes
        self.store.subscribe(self._on_settings_changed)

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
            rumps.MenuItem("Settings...", callback=self.open_settings),
            self.start_at_login_item,
            None,  # Separator
            rumps.MenuItem("Restart", callback=self.restart_app),
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

        # Start auto-sync timer if enabled
        self._setup_timer()

    def _on_settings_changed(self, key: str) -> None:
        """Handle settings changes from the preferences window."""
        if key in ("sync_interval_minutes", "auto_sync_enabled"):
            self._setup_timer()

    def _get_last_sync_text(self) -> str:
        """Get formatted last sync text."""
        if self.store.last_sync_time:
            try:
                last = datetime.fromisoformat(self.store.last_sync_time)
                time_str = last.strftime("%-I:%M %p").lower()  # e.g., "3:25 pm"
                status = "✓" if self.store.last_sync_status == "success" else "✗"
                return f"Last sync: {status} {time_str}"
            except ValueError:
                pass
        return "Last sync: Never"

    def _get_last_sync_stats_text(self) -> str:
        """Get formatted sync stats text."""
        if self.store.last_sync_status == "never":
            return "Stats: No sync yet"

        parts = []
        if self.store.last_sync_added > 0:
            parts.append(f"{self.store.last_sync_added} added")
        if self.store.last_sync_updated > 0:
            parts.append(f"{self.store.last_sync_updated} updated")
        if self.store.last_sync_moved > 0:
            parts.append(f"{self.store.last_sync_moved} moved")
        if self.store.last_sync_deleted > 0:
            parts.append(f"{self.store.last_sync_deleted} deleted")

        if parts:
            return f"Stats: {', '.join(parts)}"
        elif self.store.last_sync_skipped > 0:
            return f"Stats: {self.store.last_sync_skipped} unchanged"
        else:
            return "Stats: No changes"

    def _setup_timer(self) -> None:
        """Setup the auto-sync timer."""
        if hasattr(self, "_timer") and self._timer:
            self._timer.stop()
            self._timer = None

        if self.store.auto_sync_enabled and self.store.sync_interval_minutes > 0:
            interval = self.store.sync_interval_minutes * 60
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
        if not self.store.output_folder:
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
                    w for w in self.store.webhooks
                    if w.get("enabled", True)
                ]

                # Run export directly
                result = run_export(
                    output_folder=self.store.output_folder,
                    supabase_path=self.store.supabase_path or None,
                    cache_path=self.store.cache_path or None,
                    excluded_folders=list(self.store.excluded_folders),
                    excluded_folders_updated=self.store.excluded_folders_updated,
                    webhook_configs=webhook_configs if webhook_configs else None,
                    timeout=120,
                )

                # Update status
                self.store.last_sync_time = datetime.now().isoformat()
                if result.success:
                    self.store.last_sync_status = "success"
                    self.store.update_sync_stats(
                        added=result.added,
                        updated=result.updated,
                        moved=result.moved,
                        deleted=result.deleted,
                        skipped=result.skipped,
                    )

                    # Sync exclusions from sync folder config back to local settings
                    # This handles the case where another computer updated exclusions
                    if result.effective_excluded_folders is not None:
                        local_excluded = set(self.store.excluded_folders)
                        effective_excluded = set(result.effective_excluded_folders)
                        if local_excluded != effective_excluded:
                            # Update local settings without changing timestamp
                            # (the sync folder config is authoritative)
                            self.store._data.excluded_folders = list(effective_excluded)
                            self.store._save_atomic()

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
                        self.store.last_sync_message = ", ".join(parts)
                    else:
                        self.store.last_sync_message = f"{result.skipped} unchanged"

                    if should_notify(is_error=False):
                        notify(
                            "Wholesail Manager",
                            "Sync completed",
                            self.store.last_sync_message,
                        )
                else:
                    self.store.last_sync_status = "error"
                    self.store.last_sync_message = result.error_message[:100]
                    self.store.update_sync_stats()  # Reset stats
                    if should_notify(is_error=True):
                        notify(
                            "Wholesail Manager",
                            "Sync failed",
                            self.store.last_sync_message,
                        )

            except Exception as e:
                import traceback
                self.store.last_sync_status = "error"
                tb = traceback.format_exc()
                self.store.last_sync_message = f"{e}: {tb}"[:2000]
                self.store.save()
                if should_notify(is_error=True):
                    notify("Wholesail Manager", "Sync failed", str(e)[:100])

            finally:
                self.syncing = False
                self.status_item.title = "Status: Ready"
                self.last_sync_item.title = self._get_last_sync_text()
                self.last_sync_stats_item.title = self._get_last_sync_stats_text()
                if not self._using_icon:
                    self.title = "🚢"

        thread = threading.Thread(target=sync_thread, daemon=True)
        thread.start()

    def open_settings(self, _) -> None:
        """Open the native preferences window."""
        from granola.menubar.preferences_window import show_preferences_window
        show_preferences_window()

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
        script_path = Path(sys.executable).parent / "granola-menubar"
        if not script_path.exists():
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
        LOGIN_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOGIN_PLIST_PATH.write_text(plist_content)

        subprocess.run(
            ["launchctl", "load", str(LOGIN_PLIST_PATH)],
            capture_output=True,
        )

    def _uninstall_login_item(self) -> None:
        """Remove launchd plist for login."""
        if LOGIN_PLIST_PATH.exists():
            subprocess.run(
                ["launchctl", "unload", str(LOGIN_PLIST_PATH)],
                capture_output=True,
            )
            try:
                LOGIN_PLIST_PATH.unlink()
            except Exception:
                pass

    def restart_app(self, _) -> None:
        """Restart the application."""
        script_path = Path(sys.executable).parent / "granola-menubar"
        if not script_path.exists():
            cmd = [sys.executable, "-m", "granola.menubar.app"]
        else:
            cmd = [str(script_path)]

        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

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
