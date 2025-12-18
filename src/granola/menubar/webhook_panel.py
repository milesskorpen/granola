"""Webhook management panel for Wholesail Manager."""

import json
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from pathlib import Path
from datetime import datetime
from typing import Callable


class WebhookPanel:
    """A window for managing webhooks."""

    def __init__(
        self,
        webhooks: list[dict],
        available_folders: list[str],
        output_folder: str,
        on_save: Callable[[list[dict]], None],
    ):
        """Initialize the webhook panel.

        Args:
            webhooks: Current list of webhook configurations.
            available_folders: List of available Granola folders.
            output_folder: Path to the output folder for finding test files.
            on_save: Callback to save webhooks when changes are made.
        """
        self.webhooks = [dict(w) for w in webhooks]  # Deep copy
        self.available_folders = available_folders
        self.output_folder = output_folder
        self.on_save = on_save

        self.root = tk.Tk()
        self.root.title("Manage Webhooks - Wholesail Manager")
        self.root.geometry("700x450")
        self.root.minsize(600, 350)

        # Bring window to foreground on macOS
        self._bring_to_front()

        self._create_widgets()
        self._populate_list()

    def _bring_to_front(self):
        """Bring the window to the foreground on macOS."""
        import subprocess
        import sys
        import os

        # Activate the Python app itself on macOS
        if sys.platform == "darwin":
            try:
                # Use AppleScript to bring Python to front by process ID
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

        # Also use tkinter methods
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.focus_force()
        self.root.after(500, lambda: self.root.attributes("-topmost", False))

    def _create_widgets(self):
        """Create the UI widgets."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Webhooks",
            font=("Helvetica", 16, "bold"),
        )
        title_label.pack(anchor=tk.W, pady=(0, 10))

        # Description
        desc_label = ttk.Label(
            main_frame,
            text="Webhooks are called when notes are synced. Configure endpoints to send note data to external services.",
            wraplength=650,
        )
        desc_label.pack(anchor=tk.W, pady=(0, 10))

        # List frame with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Treeview for webhooks
        columns = ("name", "url", "method", "folders", "enabled")
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )

        self.tree.heading("name", text="Name")
        self.tree.heading("url", text="URL")
        self.tree.heading("method", text="Method")
        self.tree.heading("folders", text="Folders")
        self.tree.heading("enabled", text="Enabled")

        self.tree.column("name", width=120, minwidth=80)
        self.tree.column("url", width=250, minwidth=150)
        self.tree.column("method", width=60, minwidth=50)
        self.tree.column("folders", width=120, minwidth=80)
        self.tree.column("enabled", width=60, minwidth=50)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind mouse wheel scrolling for macOS (trackpad and mouse)
        self._bind_mousewheel(self.tree)

        # Double-click to edit
        self.tree.bind("<Double-1>", lambda e: self._edit_webhook())

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        # Left buttons
        left_buttons = ttk.Frame(button_frame)
        left_buttons.pack(side=tk.LEFT)

        ttk.Button(left_buttons, text="Add", command=self._add_webhook, width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(left_buttons, text="Edit", command=self._edit_webhook, width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(left_buttons, text="Delete", command=self._delete_webhook, width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(left_buttons, text="Test", command=self._test_webhook, width=10).pack(side=tk.LEFT, padx=(0, 5))

        # Right buttons
        right_buttons = ttk.Frame(button_frame)
        right_buttons.pack(side=tk.RIGHT)

        ttk.Button(right_buttons, text="History", command=self._show_history, width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(right_buttons, text="Toggle", command=self._toggle_webhook, width=10).pack(side=tk.LEFT, padx=(0, 5))

        # Close button
        close_frame = ttk.Frame(main_frame)
        close_frame.pack(fill=tk.X)

        ttk.Button(close_frame, text="Close", command=self._close, width=10).pack(side=tk.RIGHT)

    def _bind_mousewheel(self, widget):
        """Bind mouse wheel scrolling for native feel on macOS."""
        import sys

        def on_mousewheel(event):
            # macOS uses delta directly, inverted for natural scrolling
            if sys.platform == "darwin":
                widget.yview_scroll(int(-1 * event.delta), "units")
            else:
                widget.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # Bind to the widget and its parent frame
        widget.bind("<MouseWheel>", on_mousewheel)
        # Also bind when mouse enters/leaves to ensure scrolling works
        widget.bind("<Enter>", lambda e: widget.focus_set())

    def _populate_list(self):
        """Populate the treeview with webhooks."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Add webhooks
        for i, webhook in enumerate(self.webhooks):
            name = webhook.get("name", f"Webhook {i+1}")
            url = webhook.get("url", "")
            method = webhook.get("method", "POST")

            # Support both legacy "folder" and new "folders" fields
            folders = webhook.get("folders", [])
            if not folders and webhook.get("folder"):
                folders = [webhook["folder"]]

            if folders:
                folders_display = ", ".join(folders)
                # Truncate if too long
                if len(folders_display) > 25:
                    folders_display = folders_display[:22] + "..."
            else:
                folders_display = "All folders"

            enabled = "Yes" if webhook.get("enabled", True) else "No"

            # Truncate URL for display
            url_display = url[:40] + "..." if len(url) > 40 else url

            self.tree.insert("", tk.END, iid=str(i), values=(name, url_display, method, folders_display, enabled))

    def _get_selected_index(self) -> int | None:
        """Get the index of the selected webhook."""
        selection = self.tree.selection()
        if not selection:
            return None
        return int(selection[0])

    def _add_webhook(self):
        """Open dialog to add a new webhook."""
        dialog = WebhookEditDialog(
            self.root,
            title="Add Webhook",
            available_folders=self.available_folders,
        )
        if dialog.result:
            self.webhooks.append(dialog.result)
            self._save_and_refresh()

    def _edit_webhook(self):
        """Open dialog to edit selected webhook."""
        index = self._get_selected_index()
        if index is None:
            messagebox.showinfo("Edit Webhook", "Please select a webhook to edit.")
            return

        webhook = self.webhooks[index]
        dialog = WebhookEditDialog(
            self.root,
            title="Edit Webhook",
            webhook=webhook,
            available_folders=self.available_folders,
        )
        if dialog.result:
            self.webhooks[index] = dialog.result
            self._save_and_refresh()

    def _delete_webhook(self):
        """Delete the selected webhook."""
        index = self._get_selected_index()
        if index is None:
            messagebox.showinfo("Delete Webhook", "Please select a webhook to delete.")
            return

        name = self.webhooks[index].get("name", f"Webhook {index+1}")
        if messagebox.askyesno("Delete Webhook", f"Delete webhook '{name}'?"):
            del self.webhooks[index]
            self._save_and_refresh()

    def _toggle_webhook(self):
        """Toggle the enabled state of selected webhook."""
        index = self._get_selected_index()
        if index is None:
            messagebox.showinfo("Toggle Webhook", "Please select a webhook to toggle.")
            return

        self.webhooks[index]["enabled"] = not self.webhooks[index].get("enabled", True)
        self._save_and_refresh()

    def _show_history(self):
        """Show the webhook history panel."""
        WebhookHistoryPanel(self.root).show()

    def _test_webhook(self):
        """Test the selected webhook with a recent note."""
        index = self._get_selected_index()
        if index is None:
            messagebox.showinfo("Test Webhook", "Please select a webhook to test.")
            return

        webhook = self.webhooks[index]

        # Support both legacy "folder" and new "folders" fields
        folder_filters = webhook.get("folders", [])
        if not folder_filters and webhook.get("folder"):
            folder_filters = [webhook["folder"]]

        # Find a recent note file
        if not self.output_folder:
            messagebox.showerror("Test Webhook", "No output folder configured.")
            return

        output_path = Path(self.output_folder)
        if not output_path.exists():
            messagebox.showerror("Test Webhook", f"Output folder not found: {output_path}")
            return

        # If webhook has folder filters, only look in those folders
        txt_files: list[Path] = []
        if folder_filters:
            missing_folders = []
            for folder in folder_filters:
                search_path = output_path / folder
                if not search_path.exists():
                    missing_folders.append(folder)
                else:
                    txt_files.extend(search_path.glob("*.txt"))

            if missing_folders and not txt_files:
                messagebox.showerror(
                    "Test Webhook",
                    f"Folders not found in output directory: {', '.join(missing_folders)}\n\n"
                    "Run a sync first to create notes in these folders.",
                )
                return
        else:
            txt_files = list(output_path.rglob("*.txt"))

        if not txt_files:
            msg = f"No .txt files found in folders: {', '.join(folder_filters)}." if folder_filters else "No .txt files found in output folder."
            messagebox.showerror("Test Webhook", msg)
            return

        # Sort by modification time (most recent first)
        txt_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        # Randomly select a file, weighted towards more recent ones
        # Weight decays exponentially: most recent = 1.0, then 0.5, 0.25, etc.
        import random
        weights = [0.5 ** i for i in range(len(txt_files))]
        recent_file = random.choices(txt_files, weights=weights, k=1)[0]

        # Read content
        try:
            content = recent_file.read_text()
        except Exception as e:
            messagebox.showerror("Test Webhook", f"Error reading file: {e}")
            return

        # Extract info from filename: {YYYY-MM-DD}_{title}_{short_id}.txt
        filename = recent_file.stem
        parts = filename.split("_")
        if len(parts) >= 3:
            # First part is date (YYYY-MM-DD), last part is short ID
            doc_id = parts[-1]
            # Title is everything between date and ID
            title = " ".join(parts[1:-1]).replace("_", " ")
        else:
            doc_id = "test-id"
            title = filename

        # Get folder from path
        rel_path = recent_file.relative_to(output_path)
        folders = [rel_path.parent.name] if rel_path.parent.name != "." else []

        # Parse content to extract notes and transcript sections
        notes_content, transcript_content = self._parse_content_sections(content)

        # Send test webhook
        from granola.webhooks import WebhookDispatcher, WebhookPayload

        payload = WebhookPayload.create(
            event="document.test",
            doc_id=doc_id,
            title=title,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            folders=folders,
            file_path=str(recent_file),
            markdown_content=content,
            notes_content=notes_content,
            transcript_content=transcript_content,
            has_notes=bool(notes_content.strip()),
            has_transcript=bool(transcript_content.strip()),
            webhook_folder_filters=folder_filters,
        )

        dispatcher = WebhookDispatcher([webhook])
        result = dispatcher.dispatch_test(payload, 0)

        if result and result.success:
            messagebox.showinfo(
                "Test Webhook",
                f"Successfully sent test to '{webhook.get('name')}'!\n\n"
                f"File: {recent_file.name}\n"
                f"Title: {title}\n"
                f"Folder: {folders[0] if folders else 'Uncategorized'}",
            )
        else:
            error = result.error_message if result else "Unknown error"
            messagebox.showerror("Test Webhook", f"Failed to send test:\n\n{error}")

    def _parse_content_sections(self, content: str) -> tuple[str, str]:
        """Parse the combined content file to extract notes and transcript sections.

        Args:
            content: The full file content.

        Returns:
            Tuple of (notes_content, transcript_content).
        """
        notes_content = ""
        transcript_content = ""

        # Look for section markers
        notes_marker = "## Notes"
        transcript_marker = "## Transcript"

        notes_start = content.find(notes_marker)
        transcript_start = content.find(transcript_marker)

        if notes_start != -1 and transcript_start != -1:
            # Extract notes section (between notes marker and transcript marker)
            notes_section_start = notes_start + len(notes_marker)
            notes_content = content[notes_section_start:transcript_start].strip()
            # Remove the separator line if present
            if notes_content.startswith("\n"):
                notes_content = notes_content[1:]
            notes_content = notes_content.rstrip("=").strip()

            # Extract transcript section (after transcript marker)
            transcript_section_start = transcript_start + len(transcript_marker)
            transcript_content = content[transcript_section_start:].strip()
            if transcript_content == "(No transcript available)":
                transcript_content = ""
        elif notes_start != -1:
            # Only notes section
            notes_section_start = notes_start + len(notes_marker)
            notes_content = content[notes_section_start:].strip()
        elif transcript_start != -1:
            # Only transcript section
            transcript_section_start = transcript_start + len(transcript_marker)
            transcript_content = content[transcript_section_start:].strip()

        # Clean up "(No notes)" placeholder
        if notes_content == "(No notes)":
            notes_content = ""

        return notes_content, transcript_content

    def _save_and_refresh(self):
        """Save webhooks and refresh the list."""
        self.on_save(self.webhooks)
        self._populate_list()

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


class WebhookEditDialog:
    """Dialog for adding/editing a webhook."""

    def __init__(
        self,
        parent,
        title: str,
        webhook: dict | None = None,
        available_folders: list[str] | None = None,
    ):
        self.result = None
        self.available_folders = available_folders or []
        self.folder_vars: dict[str, tk.BooleanVar] = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x400")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Make it float above
        self.dialog.attributes("-topmost", True)

        self._create_widgets(webhook)

        # Center on parent
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")

        self.dialog.wait_window()

    def _create_widgets(self, webhook: dict | None):
        """Create dialog widgets."""
        frame = ttk.Frame(self.dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Name
        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar(value=webhook.get("name", "") if webhook else "")
        ttk.Entry(frame, textvariable=self.name_var, width=50).grid(row=0, column=1, sticky=tk.EW, pady=5)

        # URL
        ttk.Label(frame, text="URL:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.url_var = tk.StringVar(value=webhook.get("url", "https://") if webhook else "https://")
        ttk.Entry(frame, textvariable=self.url_var, width=50).grid(row=1, column=1, sticky=tk.EW, pady=5)

        # Method
        ttk.Label(frame, text="Method:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.method_var = tk.StringVar(value=webhook.get("method", "POST") if webhook else "POST")
        method_combo = ttk.Combobox(
            frame,
            textvariable=self.method_var,
            values=["POST", "GET", "PUT", "PATCH"],
            state="readonly",
            width=10,
        )
        method_combo.grid(row=2, column=1, sticky=tk.W, pady=5)

        # Folder filter (multi-select)
        ttk.Label(frame, text="Folder Filter:").grid(row=3, column=0, sticky=tk.NW, pady=5)

        # Get current folders (support both legacy "folder" and new "folders")
        current_folders: list[str] = []
        if webhook:
            current_folders = webhook.get("folders", [])
            if not current_folders and webhook.get("folder"):
                current_folders = [webhook["folder"]]

        # Create a frame with scrollbar for folder checkboxes
        folder_frame = ttk.Frame(frame)
        folder_frame.grid(row=3, column=1, sticky=tk.EW, pady=5)

        # "All folders" checkbox
        self.all_folders_var = tk.BooleanVar(value=len(current_folders) == 0)
        all_cb = ttk.Checkbutton(
            folder_frame,
            text="All folders",
            variable=self.all_folders_var,
            command=self._on_all_folders_toggle,
        )
        all_cb.pack(anchor=tk.W)

        # Separator
        ttk.Separator(folder_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        # Scrollable area for folder checkboxes
        if self.available_folders:
            canvas = tk.Canvas(folder_frame, height=100, highlightthickness=0)
            scrollbar = ttk.Scrollbar(folder_frame, orient=tk.VERTICAL, command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor=tk.NW)
            canvas.configure(yscrollcommand=scrollbar.set)

            # Create checkboxes for each folder
            for folder in self.available_folders:
                var = tk.BooleanVar(value=folder in current_folders)
                self.folder_vars[folder] = var
                cb = ttk.Checkbutton(
                    scrollable_frame,
                    text=folder,
                    variable=var,
                    command=self._on_folder_toggle,
                )
                cb.pack(anchor=tk.W, padx=(10, 0))

            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Bind mouse wheel scrolling for native feel on macOS
            def on_canvas_mousewheel(event):
                import sys
                if sys.platform == "darwin":
                    canvas.yview_scroll(int(-1 * event.delta), "units")
                else:
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

            canvas.bind("<MouseWheel>", on_canvas_mousewheel)
            scrollable_frame.bind("<MouseWheel>", on_canvas_mousewheel)
            # Bind to all child checkboxes too
            for child in scrollable_frame.winfo_children():
                child.bind("<MouseWheel>", on_canvas_mousewheel)
        else:
            ttk.Label(folder_frame, text="(No folders available)", foreground="gray").pack(anchor=tk.W)

        # Enabled
        self.enabled_var = tk.BooleanVar(value=webhook.get("enabled", True) if webhook else True)
        ttk.Checkbutton(frame, text="Enabled", variable=self.enabled_var).grid(
            row=4, column=1, sticky=tk.W, pady=5
        )

        # Configure grid
        frame.columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=(20, 0))

        ttk.Button(button_frame, text="Cancel", command=self._cancel, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save", command=self._save, width=10).pack(side=tk.LEFT, padx=5)

    def _on_all_folders_toggle(self):
        """Handle toggling the 'All folders' checkbox."""
        if self.all_folders_var.get():
            # Uncheck all individual folder checkboxes
            for var in self.folder_vars.values():
                var.set(False)

    def _on_folder_toggle(self):
        """Handle toggling an individual folder checkbox."""
        # If any folder is selected, uncheck "All folders"
        if any(var.get() for var in self.folder_vars.values()):
            self.all_folders_var.set(False)
        else:
            # If no folders selected, check "All folders"
            self.all_folders_var.set(True)

    def _save(self):
        """Validate and save the webhook."""
        name = self.name_var.get().strip()
        url = self.url_var.get().strip()
        method = self.method_var.get()
        enabled = self.enabled_var.get()

        # Collect selected folders
        folders = [folder for folder, var in self.folder_vars.items() if var.get()]

        # Validation
        if not name:
            messagebox.showerror("Validation Error", "Name is required.")
            return

        if not url or not url.startswith(("http://", "https://")):
            messagebox.showerror("Validation Error", "Valid URL is required (http:// or https://).")
            return

        self.result = {
            "name": name,
            "url": url,
            "method": method,
            "folders": folders,
            "enabled": enabled,
        }

        self.dialog.destroy()

    def _cancel(self):
        """Cancel the dialog."""
        self.dialog.destroy()


class WebhookHistoryPanel:
    """A window for viewing webhook call history."""

    def __init__(self, parent: tk.Tk | None = None):
        """Initialize the history panel.

        Args:
            parent: Optional parent window.
        """
        from granola.webhooks import load_history

        self.history = load_history()
        self.parent = parent

        if parent:
            self.root = tk.Toplevel(parent)
            self.root.transient(parent)
        else:
            self.root = tk.Tk()

        self.root.title("Webhook History - Wholesail Manager")
        self.root.geometry("900x500")
        self.root.minsize(700, 400)

        # Make it float above
        self.root.attributes("-topmost", True)
        self.root.after(500, lambda: self.root.attributes("-topmost", False))

        self._create_widgets()
        self._populate_list()

    def _create_widgets(self):
        """Create the UI widgets."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Webhook History",
            font=("Helvetica", 16, "bold"),
        )
        title_label.pack(anchor=tk.W, pady=(0, 10))

        # Description
        desc_label = ttk.Label(
            main_frame,
            text="View past webhook calls and replay them. Most recent calls are shown first.",
            wraplength=850,
        )
        desc_label.pack(anchor=tk.W, pady=(0, 10))

        # List frame with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Treeview for history
        columns = ("timestamp", "webhook", "document", "status", "code")
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )

        self.tree.heading("timestamp", text="Time")
        self.tree.heading("webhook", text="Webhook")
        self.tree.heading("document", text="Document")
        self.tree.heading("status", text="Status")
        self.tree.heading("code", text="Code")

        self.tree.column("timestamp", width=150, minwidth=120)
        self.tree.column("webhook", width=150, minwidth=100)
        self.tree.column("document", width=300, minwidth=150)
        self.tree.column("status", width=80, minwidth=60)
        self.tree.column("code", width=60, minwidth=50)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind mouse wheel scrolling for macOS (trackpad and mouse)
        self._bind_mousewheel(self.tree)

        # Double-click to view details
        self.tree.bind("<Double-1>", lambda e: self._view_details())

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        # Left buttons
        left_buttons = ttk.Frame(button_frame)
        left_buttons.pack(side=tk.LEFT)

        ttk.Button(left_buttons, text="Replay", command=self._replay, width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(left_buttons, text="View Details", command=self._view_details, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(left_buttons, text="Delete", command=self._delete, width=10).pack(side=tk.LEFT, padx=(0, 5))

        # Right buttons
        right_buttons = ttk.Frame(button_frame)
        right_buttons.pack(side=tk.RIGHT)

        ttk.Button(right_buttons, text="Clear All", command=self._clear_all, width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(right_buttons, text="Refresh", command=self._refresh, width=10).pack(side=tk.LEFT, padx=(0, 5))

        # Close button
        close_frame = ttk.Frame(main_frame)
        close_frame.pack(fill=tk.X)

        ttk.Button(close_frame, text="Close", command=self._close, width=10).pack(side=tk.RIGHT)

    def _bind_mousewheel(self, widget):
        """Bind mouse wheel scrolling for native feel on macOS."""
        import sys

        def on_mousewheel(event):
            # macOS uses delta directly, inverted for natural scrolling
            if sys.platform == "darwin":
                widget.yview_scroll(int(-1 * event.delta), "units")
            else:
                widget.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # Bind to the widget and its parent frame
        widget.bind("<MouseWheel>", on_mousewheel)
        # Also bind when mouse enters/leaves to ensure scrolling works
        widget.bind("<Enter>", lambda e: widget.focus_set())

    def _populate_list(self):
        """Populate the treeview with history entries."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Add history entries
        for entry in self.history:
            # Format timestamp for display
            try:
                dt = datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))
                timestamp_display = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                timestamp_display = entry.timestamp[:19]

            status = "Success" if entry.success else "Failed"
            code = str(entry.status_code) if entry.status_code else "-"

            # Truncate document title
            doc_title = entry.document_title or "(unknown)"
            if len(doc_title) > 40:
                doc_title = doc_title[:37] + "..."

            self.tree.insert(
                "",
                tk.END,
                iid=entry.id,
                values=(timestamp_display, entry.webhook_name, doc_title, status, code),
            )

    def _get_selected_entry(self):
        """Get the selected history entry."""
        selection = self.tree.selection()
        if not selection:
            return None
        entry_id = selection[0]
        for entry in self.history:
            if entry.id == entry_id:
                return entry
        return None

    def _replay(self):
        """Replay the selected webhook call."""
        entry = self._get_selected_entry()
        if not entry:
            messagebox.showinfo("Replay", "Please select a history entry to replay.")
            return

        if not messagebox.askyesno(
            "Replay Webhook",
            f"Replay webhook '{entry.webhook_name}' for document '{entry.document_title}'?\n\n"
            f"URL: {entry.url}",
        ):
            return

        from granola.webhooks import WebhookDispatcher

        dispatcher = WebhookDispatcher([])
        result = dispatcher.replay(entry)

        if result.success:
            messagebox.showinfo(
                "Replay Successful",
                f"Successfully replayed webhook '{entry.webhook_name}'!\n\n"
                f"Status code: {result.status_code}",
            )
        else:
            messagebox.showerror(
                "Replay Failed",
                f"Failed to replay webhook:\n\n{result.error_message}",
            )

        # Refresh the list to show the new entry
        self._refresh()

    def _view_details(self):
        """View details of the selected history entry."""
        entry = self._get_selected_entry()
        if not entry:
            messagebox.showinfo("View Details", "Please select a history entry to view.")
            return

        # Create a detail dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Webhook Details - {entry.webhook_name}")
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        # Info section
        info_frame = ttk.LabelFrame(frame, text="Call Information", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))

        info_text = (
            f"Webhook: {entry.webhook_name}\n"
            f"URL: {entry.url}\n"
            f"Method: {entry.method}\n"
            f"Timestamp: {entry.timestamp}\n"
            f"Status: {'Success' if entry.success else 'Failed'}\n"
            f"Status Code: {entry.status_code or 'N/A'}\n"
            f"Document: {entry.document_title}"
        )

        if entry.error_message:
            info_text += f"\nError: {entry.error_message}"

        info_label = ttk.Label(info_frame, text=info_text, justify=tk.LEFT)
        info_label.pack(anchor=tk.W)

        # Payload section
        payload_frame = ttk.LabelFrame(frame, text="Payload (JSON)", padding="10")
        payload_frame.pack(fill=tk.BOTH, expand=True)

        payload_text = tk.Text(payload_frame, wrap=tk.WORD, font=("Courier", 10))
        payload_scrollbar = ttk.Scrollbar(payload_frame, orient=tk.VERTICAL, command=payload_text.yview)
        payload_text.configure(yscrollcommand=payload_scrollbar.set)

        payload_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        payload_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Insert formatted JSON
        try:
            formatted_json = json.dumps(entry.payload, indent=2)
        except Exception:
            formatted_json = str(entry.payload)
        payload_text.insert("1.0", formatted_json)
        payload_text.config(state=tk.DISABLED)

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def copy_payload():
            dialog.clipboard_clear()
            dialog.clipboard_append(formatted_json)
            messagebox.showinfo("Copied", "Payload copied to clipboard.")

        ttk.Button(button_frame, text="Copy Payload", command=copy_payload, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=dialog.destroy, width=10).pack(side=tk.RIGHT)

    def _delete(self):
        """Delete the selected history entry."""
        entry = self._get_selected_entry()
        if not entry:
            messagebox.showinfo("Delete", "Please select a history entry to delete.")
            return

        if messagebox.askyesno(
            "Delete Entry",
            f"Delete this history entry?\n\n"
            f"Webhook: {entry.webhook_name}\n"
            f"Document: {entry.document_title}",
        ):
            from granola.webhooks import delete_history_entry

            delete_history_entry(entry.id)
            self._refresh()

    def _clear_all(self):
        """Clear all history entries."""
        if not self.history:
            messagebox.showinfo("Clear All", "History is already empty.")
            return

        if messagebox.askyesno(
            "Clear All History",
            f"Delete all {len(self.history)} history entries?\n\n"
            "This action cannot be undone.",
        ):
            from granola.webhooks import clear_history

            clear_history()
            self._refresh()

    def _refresh(self):
        """Refresh the history list."""
        from granola.webhooks import load_history

        self.history = load_history()
        self._populate_list()

    def _close(self):
        """Close the panel."""
        self.root.destroy()

    def show(self):
        """Show the panel and wait for it to close."""
        # Center on screen or parent
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()

        if self.parent:
            x = self.parent.winfo_x() + (self.parent.winfo_width() - width) // 2
            y = self.parent.winfo_y() + (self.parent.winfo_height() - height) // 2
        else:
            x = (self.root.winfo_screenwidth() // 2) - (width // 2)
            y = (self.root.winfo_screenheight() // 2) - (height // 2)

        self.root.geometry(f"+{x}+{y}")

        if self.parent:
            self.root.wait_window()
        else:
            self.root.mainloop()


def show_webhook_panel(
    webhooks: list[dict],
    available_folders: list[str],
    output_folder: str,
    on_save: Callable[[list[dict]], None],
):
    """Show the webhook management panel.

    Args:
        webhooks: Current list of webhook configurations.
        available_folders: List of available Granola folders.
        output_folder: Path to the output folder.
        on_save: Callback when webhooks are saved.
    """
    panel = WebhookPanel(webhooks, available_folders, output_folder, on_save)
    panel.show()


def show_webhook_history_panel(parent: tk.Tk | None = None):
    """Show the webhook history panel.

    Args:
        parent: Optional parent window.
    """
    panel = WebhookHistoryPanel(parent)
    panel.show()


def main():
    """Run the webhook panel as a standalone application."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Webhook management panel")
    parser.add_argument("--settings-path", required=True, help="Path to settings.json")
    parser.add_argument("--cache-path", default="", help="Path to Granola cache file")
    parser.add_argument("--output-folder", default="", help="Output folder path")
    args = parser.parse_args()

    settings_path = Path(args.settings_path)

    # Load current settings
    webhooks = []
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text())
            webhooks = data.get("webhooks", [])
        except Exception:
            pass

    # Get available folders from cache
    available_folders = []
    if args.cache_path and Path(args.cache_path).exists():
        try:
            from granola.menubar.settings import get_available_folders
            available_folders = get_available_folders(args.cache_path)
        except Exception:
            pass

    def on_save(updated_webhooks: list[dict]) -> None:
        """Save webhooks to settings file."""
        try:
            # Read current settings
            data = {}
            if settings_path.exists():
                data = json.loads(settings_path.read_text())

            # Update webhooks
            data["webhooks"] = updated_webhooks

            # Write back
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    panel = WebhookPanel(
        webhooks=webhooks,
        available_folders=available_folders,
        output_folder=args.output_folder,
        on_save=on_save,
    )
    panel.show()


if __name__ == "__main__":
    main()
