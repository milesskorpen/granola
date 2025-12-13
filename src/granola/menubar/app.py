"""Granola Sync menu bar application."""

import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import rumps

from granola.menubar.settings import (
    Settings,
    get_available_folders,
    get_launchd_plist_path,
)

# Launchd plist for starting at login
LOGIN_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / "com.granola.menubar.plist"
LOGIN_PLIST_LABEL = "com.granola.menubar"


class GranolaSyncApp(rumps.App):
    """Menu bar app for Granola Sync."""

    def __init__(self):
        super().__init__(
            "Granola Sync",
            icon=None,  # Will use emoji title instead
            title="🥣",
            quit_button=None,  # We'll add our own
        )

        self.settings = Settings.load()
        self.syncing = False

        # Build menu
        self.status_item = rumps.MenuItem("Status: Ready")
        self.status_item.set_callback(None)

        self.last_sync_item = rumps.MenuItem(self._get_last_sync_text())
        self.last_sync_item.set_callback(None)

        # Start at login menu item
        self.start_at_login_item = rumps.MenuItem(
            "Start at Login",
            callback=self.toggle_start_at_login,
        )
        self.start_at_login_item.state = self._is_login_item_installed()

        self.menu = [
            self.status_item,
            self.last_sync_item,
            None,  # Separator
            rumps.MenuItem("Sync Now", callback=self.sync_now),
            None,  # Separator
            rumps.MenuItem("Settings...", callback=self.open_settings),
            rumps.MenuItem("Manage Excluded Folders...", callback=self.manage_exclusions),
            None,  # Separator
            self._build_auto_sync_menu(),
            self.start_at_login_item,
            None,  # Separator
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

        # Start auto-sync timer if enabled
        self._setup_timer()

    def _get_last_sync_text(self) -> str:
        """Get formatted last sync text."""
        if self.settings.last_sync_time:
            try:
                last = datetime.fromisoformat(self.settings.last_sync_time)
                delta = datetime.now() - last
                if delta.seconds < 60:
                    ago = "just now"
                elif delta.seconds < 3600:
                    ago = f"{delta.seconds // 60} min ago"
                else:
                    ago = f"{delta.seconds // 3600} hours ago"
                status = "✓" if self.settings.last_sync_status == "success" else "✗"
                return f"Last sync: {status} {ago}"
            except ValueError:
                pass
        return "Last sync: Never"

    def _build_auto_sync_menu(self) -> rumps.MenuItem:
        """Build the auto-sync submenu."""
        auto_sync = rumps.MenuItem("Auto Sync")

        intervals = [
            ("Every 5 minutes", 5),
            ("Every 15 minutes", 15),
            ("Every 30 minutes", 30),
            ("Every hour", 60),
            ("Disabled", 0),
        ]

        for label, minutes in intervals:
            item = rumps.MenuItem(label, callback=lambda sender, m=minutes: self.set_sync_interval(sender, m))
            if self.settings.sync_interval_minutes == minutes:
                item.state = 1
            auto_sync.add(item)

        return auto_sync

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
            rumps.notification(
                "Granola Sync",
                "Sync in progress",
                "Please wait for the current sync to complete.",
            )
            return
        self._do_sync()

    def _do_sync(self) -> None:
        """Perform the actual sync in a background thread."""
        if not self.settings.output_folder:
            rumps.notification(
                "Granola Sync",
                "Configuration needed",
                "Please set an output folder in Settings.",
            )
            return

        self.syncing = True
        self.status_item.title = "Status: Syncing..."
        self.title = "🔄"

        def sync_thread():
            try:
                # Build command
                cmd = [
                    sys.executable,
                    "-m",
                    "granola.cli.main",
                    "export",
                    "--output",
                    self.settings.output_folder,
                ]

                if self.settings.supabase_path:
                    cmd.extend(["--supabase", self.settings.supabase_path])

                if self.settings.cache_path:
                    cmd.extend(["--cache", self.settings.cache_path])

                for folder in self.settings.excluded_folders:
                    cmd.extend(["--exclude-folder", folder])

                # Run sync
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                )

                # Update status
                self.settings.last_sync_time = datetime.now().isoformat()
                if result.returncode == 0:
                    self.settings.last_sync_status = "success"
                    self.settings.last_sync_message = result.stdout.strip().split("\n")[-1]
                    if self.settings.show_notifications:
                        rumps.notification(
                            "Granola Sync",
                            "Sync completed",
                            self.settings.last_sync_message,
                        )
                else:
                    self.settings.last_sync_status = "error"
                    self.settings.last_sync_message = result.stderr.strip()[:100]
                    rumps.notification(
                        "Granola Sync",
                        "Sync failed",
                        self.settings.last_sync_message,
                    )

                self.settings.save()

            except subprocess.TimeoutExpired:
                self.settings.last_sync_status = "error"
                self.settings.last_sync_message = "Sync timed out"
                self.settings.save()
                rumps.notification("Granola Sync", "Sync failed", "Operation timed out")

            except Exception as e:
                self.settings.last_sync_status = "error"
                self.settings.last_sync_message = str(e)[:100]
                self.settings.save()
                rumps.notification("Granola Sync", "Sync failed", str(e)[:100])

            finally:
                self.syncing = False
                self.status_item.title = "Status: Ready"
                self.last_sync_item.title = self._get_last_sync_text()
                self.title = "🥣"

        thread = threading.Thread(target=sync_thread, daemon=True)
        thread.start()

    def open_settings(self, _) -> None:
        """Open settings dialog."""
        # Use AppleScript for folder picker
        script = '''
        tell application "System Events"
            activate
            set selectedFolder to choose folder with prompt "Select sync destination folder:"
            return POSIX path of selectedFolder
        end tell
        '''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                folder = result.stdout.strip()
                self.settings.update(output_folder=folder)
                rumps.notification(
                    "Granola Sync",
                    "Settings updated",
                    f"Sync folder: {folder}",
                )
        except Exception:
            pass

    def manage_exclusions(self, _) -> None:
        """Manage excluded folders."""
        available = get_available_folders(self.settings.cache_path)
        if not available:
            rumps.notification(
                "Granola Sync",
                "No folders found",
                "Could not read folders from Granola cache.",
            )
            return

        # Build list with current exclusion status
        items = []
        for folder in available:
            prefix = "☑" if folder in self.settings.excluded_folders else "☐"
            items.append(f"{prefix} {folder}")

        # Use AppleScript for list selection
        items_str = '", "'.join(items)
        script = f'''
        tell application "System Events"
            activate
            set folderList to {{"{items_str}"}}
            set selectedItems to choose from list folderList ¬
                with prompt "Select folders to EXCLUDE from sync:" ¬
                with multiple selections allowed ¬
                default items {{}}
            if selectedItems is false then
                return ""
            else
                set AppleScript's text item delimiters to "|"
                return selectedItems as text
            end if
        end tell
        '''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                selected = result.stdout.strip().split("|")
                # Extract folder names (remove checkbox prefix)
                excluded = [s.split(" ", 1)[1] for s in selected if " " in s]
                self.settings.update(excluded_folders=excluded)
                rumps.notification(
                    "Granola Sync",
                    "Exclusions updated",
                    f"{len(excluded)} folder(s) excluded",
                )
        except Exception:
            pass

    def set_sync_interval(self, sender, minutes: int) -> None:
        """Set the auto-sync interval."""
        # Update checkmarks
        for item in sender.parent.values():
            item.state = 0
        sender.state = 1

        self.settings.update(sync_interval_minutes=minutes)
        self._setup_timer()

        if minutes > 0:
            rumps.notification(
                "Granola Sync",
                "Auto-sync enabled",
                f"Syncing every {minutes} minutes",
            )
        else:
            rumps.notification(
                "Granola Sync",
                "Auto-sync disabled",
                "Use 'Sync Now' to sync manually",
            )

    def _is_login_item_installed(self) -> bool:
        """Check if the app is set to start at login."""
        return LOGIN_PLIST_PATH.exists()

    def toggle_start_at_login(self, sender) -> None:
        """Toggle start at login."""
        if self._is_login_item_installed():
            self._uninstall_login_item()
            sender.state = 0
            rumps.notification(
                "Granola Sync",
                "Start at Login disabled",
                "App will not start automatically",
            )
        else:
            self._install_login_item()
            sender.state = 1
            rumps.notification(
                "Granola Sync",
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

    def quit_app(self, _) -> None:
        """Quit the application."""
        rumps.quit_application()


def main():
    """Entry point for the menu bar app."""
    app = GranolaSyncApp()
    app.run()


if __name__ == "__main__":
    main()
