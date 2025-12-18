"""Settings panel for Wholesail Manager."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Callable

from granola.menubar.settings import Settings, get_available_folders


class SettingsPanel:
    """A window for managing all app settings."""

    def __init__(
        self,
        settings: Settings,
        on_save: Callable[[Settings], None],
        on_open_webhooks: Callable[[], None],
    ):
        """Initialize the settings panel.

        Args:
            settings: Current settings object.
            on_save: Callback when settings are saved.
            on_open_webhooks: Callback to open webhook panel.
        """
        self.settings = settings
        self.on_save = on_save
        self.on_open_webhooks = on_open_webhooks
        self.folder_vars: dict[str, tk.BooleanVar] = {}

        self.root = tk.Tk()
        self.root.title("Settings - Wholesail Manager")
        self.root.geometry("600x550")
        self.root.minsize(500, 450)

        # Bring window to foreground on macOS
        self._bring_to_front()

        self._create_widgets()

    def _bring_to_front(self):
        """Bring the window to the foreground on macOS."""
        import subprocess
        import sys
        import os

        if sys.platform == "darwin":
            try:
                pid = os.getpid()
                subprocess.run(
                    [
                        "osascript",
                        "-e",
                        f'tell application "System Events" to set frontmost of '
                        f'(first process whose unix id is {pid}) to true',
                    ],
                    capture_output=True,
                    timeout=2,
                )
            except Exception:
                pass

        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.focus_force()
        self.root.after(500, lambda: self.root.attributes("-topmost", False))

    def _create_widgets(self):
        """Create the UI widgets."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Settings",
            font=("Helvetica", 18, "bold"),
        )
        title_label.pack(anchor=tk.W, pady=(0, 15))

        # Create a canvas with scrollbar for the settings
        canvas = tk.Canvas(main_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor=tk.NW, width=560)
        canvas.configure(yscrollcommand=scrollbar.set)

        # Bind mouse wheel scrolling
        self._bind_mousewheel(canvas, scrollable_frame)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # === Sync Folder Section ===
        sync_frame = ttk.LabelFrame(scrollable_frame, text="Sync Folder", padding="10")
        sync_frame.pack(fill=tk.X, pady=(0, 10))

        folder_row = ttk.Frame(sync_frame)
        folder_row.pack(fill=tk.X)

        self.output_folder_var = tk.StringVar(value=self.settings.output_folder or "")
        folder_entry = ttk.Entry(folder_row, textvariable=self.output_folder_var, width=50)
        folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        ttk.Button(folder_row, text="Browse...", command=self._browse_folder, width=10).pack(side=tk.RIGHT)

        ttk.Label(sync_frame, text="Synced notes will be saved to this folder.", foreground="gray").pack(anchor=tk.W, pady=(5, 0))

        # === Excluded Folders Section ===
        exclude_frame = ttk.LabelFrame(scrollable_frame, text="Excluded Folders", padding="10")
        exclude_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(exclude_frame, text="Check folders to exclude from sync:").pack(anchor=tk.W)

        # Get available folders
        available_folders = get_available_folders(self.settings.cache_path)

        if available_folders:
            folder_list_frame = ttk.Frame(exclude_frame)
            folder_list_frame.pack(fill=tk.X, pady=(5, 0))

            # Create checkboxes for each folder (max height with scroll if needed)
            folder_canvas = tk.Canvas(folder_list_frame, height=120, highlightthickness=0)
            folder_scrollbar = ttk.Scrollbar(folder_list_frame, orient=tk.VERTICAL, command=folder_canvas.yview)
            folder_inner = ttk.Frame(folder_canvas)

            folder_inner.bind(
                "<Configure>",
                lambda e: folder_canvas.configure(scrollregion=folder_canvas.bbox("all")),
            )

            folder_canvas.create_window((0, 0), window=folder_inner, anchor=tk.NW)
            folder_canvas.configure(yscrollcommand=folder_scrollbar.set)

            for folder in available_folders:
                var = tk.BooleanVar(value=folder in self.settings.excluded_folders)
                self.folder_vars[folder] = var
                cb = ttk.Checkbutton(folder_inner, text=folder, variable=var)
                cb.pack(anchor=tk.W)

            folder_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            folder_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Bind scrolling to folder list
            self._bind_mousewheel(folder_canvas, folder_inner)
        else:
            ttk.Label(exclude_frame, text="(No folders found in Granola cache)", foreground="gray").pack(anchor=tk.W, pady=(5, 0))

        # === Auto Sync Section ===
        autosync_frame = ttk.LabelFrame(scrollable_frame, text="Auto Sync", padding="10")
        autosync_frame.pack(fill=tk.X, pady=(0, 10))

        interval_row = ttk.Frame(autosync_frame)
        interval_row.pack(fill=tk.X)

        ttk.Label(interval_row, text="Sync interval:").pack(side=tk.LEFT)

        self.interval_var = tk.StringVar()
        interval_values = [
            ("Every 5 minutes", 5),
            ("Every 15 minutes", 15),
            ("Every 30 minutes", 30),
            ("Every hour", 60),
            ("Disabled", 0),
        ]
        self.interval_map = {label: val for label, val in interval_values}
        self.interval_reverse_map = {val: label for label, val in interval_values}

        current_interval = self.interval_reverse_map.get(
            self.settings.sync_interval_minutes, "Every 15 minutes"
        )
        self.interval_var.set(current_interval)

        interval_combo = ttk.Combobox(
            interval_row,
            textvariable=self.interval_var,
            values=[label for label, _ in interval_values],
            state="readonly",
            width=20,
        )
        interval_combo.pack(side=tk.LEFT, padx=(10, 0))

        # === Notifications Section ===
        notif_frame = ttk.LabelFrame(scrollable_frame, text="Notifications", padding="10")
        notif_frame.pack(fill=tk.X, pady=(0, 10))

        notif_row = ttk.Frame(notif_frame)
        notif_row.pack(fill=tk.X)

        ttk.Label(notif_row, text="Notification level:").pack(side=tk.LEFT)

        self.notif_var = tk.StringVar()
        notif_options = [
            ("Verbose (all syncs & webhooks)", "verbose"),
            ("Errors only", "errors"),
            ("None", "none"),
        ]
        self.notif_map = {label: val for label, val in notif_options}
        self.notif_reverse_map = {val: label for label, val in notif_options}

        current_notif = self.notif_reverse_map.get(
            self.settings.notification_level, "Verbose (all syncs & webhooks)"
        )
        self.notif_var.set(current_notif)

        notif_combo = ttk.Combobox(
            notif_row,
            textvariable=self.notif_var,
            values=[label for label, _ in notif_options],
            state="readonly",
            width=30,
        )
        notif_combo.pack(side=tk.LEFT, padx=(10, 0))

        # Description
        notif_desc = ttk.Label(
            notif_frame,
            text="Verbose: Notify on every sync and webhook.\n"
                 "Errors only: Only notify when something fails.\n"
                 "None: No notifications at all.",
            foreground="gray",
            justify=tk.LEFT,
        )
        notif_desc.pack(anchor=tk.W, pady=(10, 0))

        # === Webhooks Section ===
        webhook_frame = ttk.LabelFrame(scrollable_frame, text="Webhooks", padding="10")
        webhook_frame.pack(fill=tk.X, pady=(0, 10))

        webhook_row = ttk.Frame(webhook_frame)
        webhook_row.pack(fill=tk.X)

        # Show webhook count
        enabled_count = sum(1 for w in self.settings.webhooks if w.get("enabled", True))
        total_count = len(self.settings.webhooks)
        webhook_status = f"{enabled_count} of {total_count} webhooks enabled" if total_count > 0 else "No webhooks configured"

        ttk.Label(webhook_row, text=webhook_status).pack(side=tk.LEFT)
        ttk.Button(webhook_row, text="Manage Webhooks...", command=self._open_webhooks, width=18).pack(side=tk.RIGHT)

        ttk.Label(
            webhook_frame,
            text="Webhooks send note data to external services when syncing.",
            foreground="gray",
        ).pack(anchor=tk.W, pady=(5, 0))

        # === Bottom buttons ===
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="Cancel", command=self._close, width=10).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Save", command=self._save, width=10).pack(side=tk.RIGHT)

    def _bind_mousewheel(self, canvas, frame):
        """Bind mouse wheel scrolling for native feel on macOS."""
        import sys

        def on_mousewheel(event):
            if sys.platform == "darwin":
                canvas.yview_scroll(int(-1 * event.delta), "units")
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<MouseWheel>", on_mousewheel)
        frame.bind("<MouseWheel>", on_mousewheel)
        for child in frame.winfo_children():
            child.bind("<MouseWheel>", on_mousewheel)

    def _browse_folder(self):
        """Open folder browser dialog."""
        initial_dir = self.output_folder_var.get() or str(Path.home())
        folder = filedialog.askdirectory(
            initialdir=initial_dir,
            title="Select sync destination folder",
        )
        if folder:
            self.output_folder_var.set(folder)

    def _open_webhooks(self):
        """Open the webhooks panel."""
        self.on_open_webhooks()

    def _save(self):
        """Save settings and close."""
        # Validate output folder
        output_folder = self.output_folder_var.get().strip()
        if output_folder and not Path(output_folder).exists():
            if not messagebox.askyesno(
                "Folder not found",
                f"The folder '{output_folder}' does not exist.\n\nCreate it?",
            ):
                return
            try:
                Path(output_folder).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create folder: {e}")
                return

        # Collect excluded folders
        excluded = [folder for folder, var in self.folder_vars.items() if var.get()]

        # Get interval
        interval_label = self.interval_var.get()
        interval_minutes = self.interval_map.get(interval_label, 15)

        # Get notification level
        notif_label = self.notif_var.get()
        notif_level = self.notif_map.get(notif_label, "verbose")

        # Update settings
        self.settings.output_folder = output_folder
        self.settings.excluded_folders = excluded
        self.settings.sync_interval_minutes = interval_minutes
        self.settings.notification_level = notif_level
        # Update legacy field for backwards compatibility
        self.settings.show_notifications = notif_level != "none"

        # Save
        self.on_save(self.settings)
        self._close()

    def _close(self):
        """Close the panel."""
        self.root.destroy()

    def show(self):
        """Show the panel and wait for it to close."""
        # Center on screen
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"+{x}+{y}")

        self.root.mainloop()


def show_settings_panel(
    settings: Settings,
    on_save: Callable[[Settings], None],
    on_open_webhooks: Callable[[], None],
):
    """Show the settings panel.

    Args:
        settings: Current settings object.
        on_save: Callback when settings are saved.
        on_open_webhooks: Callback to open webhook panel.
    """
    panel = SettingsPanel(settings, on_save, on_open_webhooks)
    panel.show()


def main():
    """Run the settings panel as a standalone application."""
    import argparse

    parser = argparse.ArgumentParser(description="Settings panel")
    parser.add_argument("--cache-path", default="", help="Path to Granola cache file")
    args = parser.parse_args()

    # Load settings
    settings = Settings.load()
    if args.cache_path:
        settings.cache_path = args.cache_path

    def on_save(updated_settings: Settings) -> None:
        """Save settings."""
        updated_settings.save()

    def on_open_webhooks() -> None:
        """Open webhook panel."""
        from granola.menubar.webhook_panel import show_webhook_panel

        def on_webhook_save(webhooks: list[dict]) -> None:
            s = Settings.load()
            s.webhooks = webhooks
            s.save()

        show_webhook_panel(
            webhooks=settings.webhooks,
            available_folders=get_available_folders(settings.cache_path),
            output_folder=settings.output_folder or "",
            on_save=on_webhook_save,
        )

    panel = SettingsPanel(settings, on_save, on_open_webhooks)
    panel.show()


if __name__ == "__main__":
    main()
