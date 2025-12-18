"""Native AppKit Preferences Window for Wholesail Manager."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import objc
from AppKit import (
    NSAlert,
    NSAlertFirstButtonReturn,
    NSApp,
    NSBackingStoreBuffered,
    NSBezelStyleRounded,
    NSButton,
    NSButtonTypeSwitch,
    NSColor,
    NSFont,
    NSLayoutAttributeBottom,
    NSLayoutAttributeCenterY,
    NSLayoutAttributeHeight,
    NSLayoutAttributeLeading,
    NSLayoutAttributeTop,
    NSLayoutAttributeTrailing,
    NSLayoutAttributeWidth,
    NSLayoutConstraint,
    NSLayoutRelationEqual,
    NSLineBreakByTruncatingTail,
    NSMakeRect,
    NSMenu,
    NSMenuItem,
    NSObject,
    NSOpenPanel,
    NSPopUpButton,
    NSScrollView,
    NSStackView,
    NSTableColumn,
    NSTableView,
    NSTableViewSelectionHighlightStyleSourceList,
    NSTextField,
    NSUserInterfaceLayoutOrientationVertical,
    NSView,
    NSViewHeightSizable,
    NSViewWidthSizable,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskResizable,
    NSWindowStyleMaskTitled,
    NSWorkspace,
    NSControlStateValueOff,
    NSControlStateValueOn,
)
from Foundation import (
    NSMakeSize,
    NSURL,
)

from granola.menubar.settings_store import SettingsStore


# Window dimensions
WINDOW_MIN_WIDTH = 680
WINDOW_MIN_HEIGHT = 520
WINDOW_INITIAL_WIDTH = 720
WINDOW_INITIAL_HEIGHT = 580
SIDEBAR_WIDTH = 180


def _ensureEditMenu():
    """Ensure the application has an Edit menu with standard shortcuts.

    This is needed because menu bar apps don't get the standard Edit menu,
    so Cmd+C/V/X/A don't work in text fields without it.
    """
    mainMenu = NSApp.mainMenu()
    if mainMenu is None:
        mainMenu = NSMenu.alloc().init()
        NSApp.setMainMenu_(mainMenu)

    # Check if Edit menu already exists
    editMenuItem = mainMenu.itemWithTitle_("Edit")
    if editMenuItem is not None:
        return

    # Create Edit menu
    editMenu = NSMenu.alloc().initWithTitle_("Edit")

    # Undo
    undoItem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Undo", "undo:", "z")
    editMenu.addItem_(undoItem)

    # Redo
    redoItem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Redo", "redo:", "Z")
    editMenu.addItem_(redoItem)

    editMenu.addItem_(NSMenuItem.separatorItem())

    # Cut
    cutItem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Cut", "cut:", "x")
    editMenu.addItem_(cutItem)

    # Copy
    copyItem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Copy", "copy:", "c")
    editMenu.addItem_(copyItem)

    # Paste
    pasteItem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Paste", "paste:", "v")
    editMenu.addItem_(pasteItem)

    # Delete
    deleteItem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Delete", "delete:", "")
    editMenu.addItem_(deleteItem)

    # Select All
    selectAllItem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Select All", "selectAll:", "a")
    editMenu.addItem_(selectAllItem)

    # Add Edit menu to main menu
    editMenuItem = NSMenuItem.alloc().init()
    editMenuItem.setTitle_("Edit")
    editMenuItem.setSubmenu_(editMenu)
    mainMenu.addItem_(editMenuItem)


def get_available_folders(cache_path: Optional[str] = None) -> list[str]:
    """Get list of available Granola folders from API.

    Falls back to scanning the sync output folder for existing folder names
    if API call fails.
    """
    folders = []

    # Try to get folders from API (more reliable than cache)
    try:
        store = SettingsStore.shared()
        if store.supabase_path and Path(store.supabase_path).exists():
            from granola.api.auth import get_access_token
            from granola.api.client import GranolaClient

            access_token = get_access_token(Path(store.supabase_path))
            # Use short timeout to avoid blocking UI
            client = GranolaClient(access_token, timeout=10)
            api_folders, _ = client.get_doc_folder_mapping()
            folders = list(api_folders.values()) if api_folders else []
            print(f"[DEBUG] Got {len(folders)} folders from API")
    except Exception as e:
        print(f"[DEBUG] API folder fetch error: {e}")
        import traceback
        traceback.print_exc()

    # Fallback 1: try cache if API failed
    if not folders:
        if not cache_path:
            cache_path = SettingsStore.shared().cache_path

        if cache_path and Path(cache_path).exists():
            try:
                content = Path(cache_path).read_text(encoding="utf-8")
                outer = json.loads(content)
                inner = json.loads(outer.get("cache", "{}"))
                state = inner.get("state", {})

                for folder_data in state.get("documentListsMetadata", {}).values():
                    title = folder_data.get("title", "")
                    if title:
                        folders.append(title)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"[DEBUG] Cache parse error: {e}")

    # Fallback 2: scan sync output folder for existing folder names
    if not folders:
        store = SettingsStore.shared()
        if store.output_folder and Path(store.output_folder).exists():
            output_path = Path(store.output_folder)
            for item in output_path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    folders.append(item.name)

    return sorted(set(folders))


# === Auto Layout Helpers ===

def _disableAutoresizing(view: NSView) -> None:
    """Disable autoresizing mask translation for a view."""
    view.setTranslatesAutoresizingMaskIntoConstraints_(False)


def _activate(*constraints) -> None:
    """Activate a list of constraints."""
    NSLayoutConstraint.activateConstraints_(list(constraints))


def _pinEdges(view: NSView, to_view: NSView, insets: tuple = (0, 0, 0, 0)) -> list:
    """Pin all edges of view to another view with insets (top, leading, bottom, trailing)."""
    top, leading, bottom, trailing = insets
    return [
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            view, NSLayoutAttributeTop, NSLayoutRelationEqual, to_view, NSLayoutAttributeTop, 1.0, top
        ),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            view, NSLayoutAttributeLeading, NSLayoutRelationEqual, to_view, NSLayoutAttributeLeading, 1.0, leading
        ),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            view, NSLayoutAttributeBottom, NSLayoutRelationEqual, to_view, NSLayoutAttributeBottom, 1.0, -bottom
        ),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            view, NSLayoutAttributeTrailing, NSLayoutRelationEqual, to_view, NSLayoutAttributeTrailing, 1.0, -trailing
        ),
    ]


def _setHeight(view: NSView, height: float) -> NSLayoutConstraint:
    """Set a fixed height constraint."""
    return NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
        view, NSLayoutAttributeHeight, NSLayoutRelationEqual, None, 0, 1.0, height
    )


def _setWidth(view: NSView, width: float) -> NSLayoutConstraint:
    """Set a fixed width constraint."""
    return NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
        view, NSLayoutAttributeWidth, NSLayoutRelationEqual, None, 0, 1.0, width
    )


def _pinLeading(view: NSView, parent: NSView, constant: float = 0) -> NSLayoutConstraint:
    """Pin view's leading edge."""
    return NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
        view, NSLayoutAttributeLeading, NSLayoutRelationEqual,
        parent, NSLayoutAttributeLeading, 1.0, constant
    )


def _pinTrailing(view: NSView, parent: NSView, constant: float = 0) -> NSLayoutConstraint:
    """Pin view's trailing edge."""
    return NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
        view, NSLayoutAttributeTrailing, NSLayoutRelationEqual,
        parent, NSLayoutAttributeTrailing, 1.0, -constant
    )


def _pinTop(view: NSView, parent: NSView, constant: float = 0) -> NSLayoutConstraint:
    """Pin view's top edge."""
    return NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
        view, NSLayoutAttributeTop, NSLayoutRelationEqual,
        parent, NSLayoutAttributeTop, 1.0, constant
    )


def _pinBottom(view: NSView, parent: NSView, constant: float = 0) -> NSLayoutConstraint:
    """Pin view's bottom edge."""
    return NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
        view, NSLayoutAttributeBottom, NSLayoutRelationEqual,
        parent, NSLayoutAttributeBottom, 1.0, -constant
    )


def _alignCenterY(view: NSView, to_view: NSView) -> NSLayoutConstraint:
    """Align view's vertical center with another view."""
    return NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
        view, NSLayoutAttributeCenterY, NSLayoutRelationEqual,
        to_view, NSLayoutAttributeCenterY, 1.0, 0
    )


def _pinAfter(view: NSView, anchor_view: NSView, spacing: float = 8) -> NSLayoutConstraint:
    """Pin view after (to the right of) another view."""
    return NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
        view, NSLayoutAttributeLeading, NSLayoutRelationEqual,
        anchor_view, NSLayoutAttributeTrailing, 1.0, spacing
    )


def _createScrollableStackView() -> tuple:
    """Create a scrollable stack view structure.

    Returns: (scrollView, stackView)

    Structure:
    - NSScrollView (clips content, provides scrollbars)
      - documentView (NSView, sized to content)
        - NSStackView (vertical, holds all content)

    The document view is constrained to match scroll view width,
    preventing the "narrow column" issue.
    """
    # Create scroll view
    scrollView = NSScrollView.alloc().init()
    scrollView.setHasVerticalScroller_(True)
    scrollView.setHasHorizontalScroller_(False)
    scrollView.setAutohidesScrollers_(True)
    scrollView.setBorderType_(0)  # No border
    scrollView.setDrawsBackground_(False)
    _disableAutoresizing(scrollView)

    # Create document view (container for stack)
    documentView = NSView.alloc().init()
    _disableAutoresizing(documentView)

    # Create vertical stack view
    stackView = NSStackView.alloc().init()
    stackView.setOrientation_(NSUserInterfaceLayoutOrientationVertical)
    stackView.setAlignment_(1)  # NSLayoutAttributeLeading
    stackView.setSpacing_(16)
    stackView.setEdgeInsets_((20, 20, 20, 20))  # top, left, bottom, right
    _disableAutoresizing(stackView)

    # Add stack to document view
    documentView.addSubview_(stackView)

    # Pin stack view to document view edges (with margins built into stack's edgeInsets)
    _activate(
        _pinTop(stackView, documentView, 0),
        _pinLeading(stackView, documentView, 0),
        _pinTrailing(stackView, documentView, 0),
        # Bottom constraint allows document view to size to content
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            stackView, NSLayoutAttributeBottom, NSLayoutRelationEqual,
            documentView, NSLayoutAttributeBottom, 1.0, 0
        ),
    )

    # Set document view in scroll view
    scrollView.setDocumentView_(documentView)

    # Get the clip view (contentView of scroll view)
    clipView = scrollView.contentView()

    # Critical: Pin document view width to clip view width
    # This prevents the narrow column issue
    _activate(
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            documentView, NSLayoutAttributeLeading, NSLayoutRelationEqual,
            clipView, NSLayoutAttributeLeading, 1.0, 0
        ),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            documentView, NSLayoutAttributeTrailing, NSLayoutRelationEqual,
            clipView, NSLayoutAttributeTrailing, 1.0, 0
        ),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            documentView, NSLayoutAttributeTop, NSLayoutRelationEqual,
            clipView, NSLayoutAttributeTop, 1.0, 0
        ),
    )

    return scrollView, stackView


def _createSectionHeader(title: str) -> NSTextField:
    """Create a section header label."""
    label = NSTextField.labelWithString_(title)
    label.setFont_(NSFont.boldSystemFontOfSize_(13))
    _disableAutoresizing(label)
    return label


def _createDescriptionLabel(text: str) -> NSTextField:
    """Create a description label."""
    label = NSTextField.labelWithString_(text)
    label.setFont_(NSFont.systemFontOfSize_(11))
    label.setTextColor_(NSColor.secondaryLabelColor())
    _disableAutoresizing(label)
    return label


def _createHorizontalRow(*views, spacing: float = 8) -> NSStackView:
    """Create a horizontal stack view row containing the given views."""
    row = NSStackView.alloc().init()
    row.setOrientation_(0)  # Horizontal
    row.setAlignment_(3)  # NSLayoutAttributeCenterY
    row.setSpacing_(spacing)
    _disableAutoresizing(row)

    for view in views:
        _disableAutoresizing(view)
        row.addArrangedSubview_(view)

    return row


class SidebarDataSource(NSObject):
    """Data source for the sidebar source list."""

    def initWithItems_controller_(self, items, controller):
        self = objc.super(SidebarDataSource, self).init()
        if self is None:
            return None
        self.items = items  # List of (id, title) tuples
        self.controller = controller
        return self

    def numberOfRowsInTableView_(self, tableView):
        return len(self.items)

    def tableView_objectValueForTableColumn_row_(self, tableView, column, row):
        if 0 <= row < len(self.items):
            return self.items[row][1]  # Return title
        return ""

    def tableViewSelectionDidChange_(self, notification):
        """Handle selection change in sidebar."""
        tableView = notification.object()
        row = tableView.selectedRow()
        if 0 <= row < len(self.items):
            pane_id = self.items[row][0]
            self.controller._showPane_(pane_id)


class PreferencesWindowController(NSObject):
    """Controller for the Preferences window."""

    _instance = None
    _window = None

    @classmethod
    def shared(cls):
        """Get the shared singleton instance."""
        if cls._instance is None:
            cls._instance = cls.alloc().init()
        return cls._instance

    def init(self):
        self = objc.super(PreferencesWindowController, self).init()
        if self is None:
            return None

        self.store = SettingsStore.shared()
        self._current_pane = "sync"
        self._pane_views = {}
        self._button_tags = {}

        return self

    def showWindow_(self, sender):
        """Show the preferences window, creating it if needed."""
        # Ensure Edit menu exists for Cmd+C/V/X/A to work
        _ensureEditMenu()

        if self._window is None or not self._window.isVisible():
            # Window doesn't exist or was closed - recreate it
            # (Closed windows may have invalid state even with releasedWhenClosed=False)
            if self._window is not None:
                self._window.close()
            self._pane_views = {}  # Clear cached panes
            self._createWindow()
        else:
            # Window exists and is visible - just refresh data
            self._refreshCurrentPane()

        self._window.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)

    def _refreshCurrentPane(self):
        """Refresh data in the current pane."""
        if self._current_pane == "sync":
            # Update folder label
            if hasattr(self, '_folder_label'):
                self._folder_label.setStringValue_(self.store.output_folder or "(Not set)")
            # Reload exclusions table
            if hasattr(self, '_exclusions_table'):
                self._exclusions_table.reloadData()
            # Update auto sync checkbox
            if hasattr(self, '_auto_sync_checkbox'):
                from AppKit import NSControlStateValueOn, NSControlStateValueOff
                self._auto_sync_checkbox.setState_(
                    NSControlStateValueOn if self.store.auto_sync_enabled else NSControlStateValueOff
                )
            # Update last sync label
            if hasattr(self, '_last_sync_label'):
                self._last_sync_label.setStringValue_(self._getLastSyncText())
        elif self._current_pane == "webhooks":
            self._refreshWebhooksPane()

    def _createWindow(self):
        """Create the preferences window."""
        # Initial frame (will be overridden by autosave if available)
        frame = NSMakeRect(0, 0, WINDOW_INITIAL_WIDTH, WINDOW_INITIAL_HEIGHT)

        style = (
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskMiniaturizable
            | NSWindowStyleMaskResizable
        )

        self._window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, style, NSBackingStoreBuffered, False
        )
        self._window.setTitle_("Wholesail Manager Settings")

        # Prevent window from being deallocated when closed
        # This fixes crash when reopening settings window
        self._window.setReleasedWhenClosed_(False)

        # Set minimum and content sizes
        self._window.setContentMinSize_(NSMakeSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT))

        # Enable frame autosave (remembers position and size)
        self._window.setFrameAutosaveName_("WholesailPreferencesWindow")

        # Center only if no saved frame
        if not self._window.setFrameUsingName_("WholesailPreferencesWindow"):
            self._window.center()

        # Create main container using Auto Layout
        contentView = self._window.contentView()
        contentView.setWantsLayer_(True)

        # Create sidebar
        self._sidebar_scroll, self._sidebar_table = self._createSidebar()
        contentView.addSubview_(self._sidebar_scroll)

        # Create content area
        self._content_view = NSView.alloc().init()
        _disableAutoresizing(self._content_view)
        contentView.addSubview_(self._content_view)

        # Layout constraints for sidebar and content
        _activate(
            # Sidebar: fixed width, full height
            _pinTop(self._sidebar_scroll, contentView, 0),
            _pinLeading(self._sidebar_scroll, contentView, 0),
            _pinBottom(self._sidebar_scroll, contentView, 0),
            _setWidth(self._sidebar_scroll, SIDEBAR_WIDTH),

            # Content: fills remaining space
            _pinTop(self._content_view, contentView, 0),
            _pinAfter(self._content_view, self._sidebar_scroll, 0),
            _pinTrailing(self._content_view, contentView, 0),
            _pinBottom(self._content_view, contentView, 0),
        )

        # Select first item and show pane
        self._sidebar_table.selectRowIndexes_byExtendingSelection_(
            objc.lookUpClass("NSIndexSet").indexSetWithIndex_(0), False
        )
        self._showPane_("sync")

    def _createSidebar(self) -> tuple:
        """Create the sidebar source list."""
        # Scroll view for the table
        scrollView = NSScrollView.alloc().init()
        scrollView.setHasVerticalScroller_(True)
        scrollView.setHasHorizontalScroller_(False)
        scrollView.setAutohidesScrollers_(True)
        scrollView.setBorderType_(0)
        scrollView.setDrawsBackground_(True)
        _disableAutoresizing(scrollView)

        # Source list style table view
        tableView = NSTableView.alloc().init()
        tableView.setSelectionHighlightStyle_(NSTableViewSelectionHighlightStyleSourceList)
        tableView.setBackgroundColor_(NSColor.windowBackgroundColor())
        tableView.setHeaderView_(None)
        tableView.setRowHeight_(28)
        tableView.setIntercellSpacing_(NSMakeSize(0, 4))

        # Single column for titles
        column = NSTableColumn.alloc().initWithIdentifier_("title")
        column.setWidth_(SIDEBAR_WIDTH - 20)
        column.setEditable_(False)
        tableView.addTableColumn_(column)

        # Data source with pane items
        panes = [
            ("sync", "Sync Settings"),
            ("webhooks", "Webhooks"),
        ]
        self._sidebar_data = SidebarDataSource.alloc().initWithItems_controller_(panes, self)
        tableView.setDataSource_(self._sidebar_data)
        tableView.setDelegate_(self._sidebar_data)

        scrollView.setDocumentView_(tableView)

        return scrollView, tableView

    def _showPane_(self, pane_id: str):
        """Show the specified pane."""
        self._current_pane = pane_id

        # Remove current subviews
        for subview in list(self._content_view.subviews()):
            subview.removeFromSuperview()

        # Get or create pane view
        if pane_id not in self._pane_views:
            if pane_id == "sync":
                self._pane_views[pane_id] = self._createSyncPane()
            elif pane_id == "webhooks":
                self._pane_views[pane_id] = self._createWebhooksPane()

        pane_view = self._pane_views.get(pane_id)
        if pane_view:
            self._content_view.addSubview_(pane_view)
            # Pin pane to fill content view
            _disableAutoresizing(pane_view)
            _activate(*_pinEdges(pane_view, self._content_view))

    # === Sync Settings Pane ===

    def _createSyncPane(self) -> NSView:
        """Create the Sync settings pane using scrollable stack view."""
        scrollView, stackView = _createScrollableStackView()

        # === Sync Folder Section ===
        stackView.addArrangedSubview_(_createSectionHeader("Sync Folder"))

        # Folder path label (truncates with ellipsis)
        folder_path = self.store.output_folder or "(Not set)"
        self._folder_label = NSTextField.labelWithString_(folder_path)
        self._folder_label.setTextColor_(NSColor.secondaryLabelColor())
        self._folder_label.setLineBreakMode_(NSLineBreakByTruncatingTail)
        self._folder_label.setPreferredMaxLayoutWidth_(300)
        _disableAutoresizing(self._folder_label)

        # Allow label to compress but not buttons
        self._folder_label.setContentCompressionResistancePriority_forOrientation_(250, 0)  # Horizontal

        choose_btn = NSButton.alloc().init()
        choose_btn.setTitle_("Choose...")
        choose_btn.setBezelStyle_(NSBezelStyleRounded)
        choose_btn.setTarget_(self)
        choose_btn.setAction_(objc.selector(self.chooseSyncFolder_, signature=b'v@:@'))
        _disableAutoresizing(choose_btn)
        choose_btn.setContentHuggingPriority_forOrientation_(750, 0)  # Don't stretch

        folder_row = _createHorizontalRow(self._folder_label, choose_btn)
        stackView.addArrangedSubview_(folder_row)

        # Reveal button
        reveal_btn = NSButton.alloc().init()
        reveal_btn.setTitle_("Reveal in Finder")
        reveal_btn.setBezelStyle_(NSBezelStyleRounded)
        reveal_btn.setTarget_(self)
        reveal_btn.setAction_(objc.selector(self.revealSyncFolder_, signature=b'v@:@'))
        _disableAutoresizing(reveal_btn)
        stackView.addArrangedSubview_(reveal_btn)

        # === Excluded Folders Section ===
        stackView.addArrangedSubview_(_createSectionHeader("Excluded Folders"))
        stackView.addArrangedSubview_(_createDescriptionLabel("These Granola folders will not be synced."))

        # Exclusions table (full width)
        excl_scroll = NSScrollView.alloc().init()
        excl_scroll.setBorderType_(2)
        excl_scroll.setHasVerticalScroller_(True)
        excl_scroll.setAutohidesScrollers_(True)
        _disableAutoresizing(excl_scroll)
        _activate(_setHeight(excl_scroll, 100))

        self._exclusions_table = NSTableView.alloc().init()
        col = NSTableColumn.alloc().initWithIdentifier_("folder")
        col.setWidth_(400)
        col.setResizingMask_(1)  # NSTableColumnAutoresizingMask
        self._exclusions_table.addTableColumn_(col)
        self._exclusions_table.setHeaderView_(None)
        self._exclusions_table.setColumnAutoresizingStyle_(4)  # NSTableViewUniformColumnAutoresizingStyle

        self._exclusions_data = ExclusionsDataSource.alloc().initWithStore_(self.store)
        self._exclusions_table.setDataSource_(self._exclusions_data)
        self._exclusions_table.setDelegate_(self._exclusions_data)
        excl_scroll.setDocumentView_(self._exclusions_table)
        stackView.addArrangedSubview_(excl_scroll)

        # Add/Remove buttons on same line
        add_excl_btn = NSButton.alloc().init()
        add_excl_btn.setTitle_("Add")
        add_excl_btn.setBezelStyle_(NSBezelStyleRounded)
        add_excl_btn.setTarget_(self)
        add_excl_btn.setAction_(objc.selector(self.addExclusion_, signature=b'v@:@'))
        _disableAutoresizing(add_excl_btn)

        remove_excl_btn = NSButton.alloc().init()
        remove_excl_btn.setTitle_("Remove")
        remove_excl_btn.setBezelStyle_(NSBezelStyleRounded)
        remove_excl_btn.setTarget_(self)
        remove_excl_btn.setAction_(objc.selector(self.removeExclusion_, signature=b'v@:@'))
        _disableAutoresizing(remove_excl_btn)

        excl_buttons_row = _createHorizontalRow(add_excl_btn, remove_excl_btn)
        stackView.addArrangedSubview_(excl_buttons_row)

        # === Auto Sync Section ===
        stackView.addArrangedSubview_(_createSectionHeader("Auto Sync"))

        # Enable checkbox + interval popup
        self._auto_sync_checkbox = NSButton.alloc().init()
        self._auto_sync_checkbox.setButtonType_(NSButtonTypeSwitch)
        self._auto_sync_checkbox.setTitle_("Enable automatic sync")
        self._auto_sync_checkbox.setState_(NSControlStateValueOn if self.store.auto_sync_enabled else NSControlStateValueOff)
        self._auto_sync_checkbox.setTarget_(self)
        self._auto_sync_checkbox.setAction_(objc.selector(self.autoSyncToggled_, signature=b'v@:@'))
        _disableAutoresizing(self._auto_sync_checkbox)

        self._interval_popup = NSPopUpButton.alloc().init()
        for label in ["Every 5 minutes", "Every 15 minutes", "Every 30 minutes", "Every hour"]:
            self._interval_popup.addItemWithTitle_(label)

        intervals = [5, 15, 30, 60]
        current = self.store.sync_interval_minutes
        for i, mins in enumerate(intervals):
            if mins == current:
                self._interval_popup.selectItemAtIndex_(i)
                break

        self._interval_popup.setTarget_(self)
        self._interval_popup.setAction_(objc.selector(self.intervalChanged_, signature=b'v@:@'))
        _disableAutoresizing(self._interval_popup)

        sync_row = _createHorizontalRow(self._auto_sync_checkbox, self._interval_popup)
        stackView.addArrangedSubview_(sync_row)

        # Last sync status
        self._last_sync_label = _createDescriptionLabel(self._getLastSyncText())
        stackView.addArrangedSubview_(self._last_sync_label)

        # === Notifications Section ===
        stackView.addArrangedSubview_(_createSectionHeader("Notifications"))

        levels = [
            ("verbose", "All events", "Notify on every sync and webhook call"),
            ("errors", "Errors only", "Only notify when something fails"),
            ("none", "None", "No notifications (check menu bar for status)"),
        ]

        current_level = self.store.notification_level
        self._notif_buttons = {}

        for level_id, label, description in levels:
            btn = NSButton.alloc().init()
            btn.setButtonType_(4)  # Radio
            btn.setTitle_(label)
            btn.setState_(NSControlStateValueOn if level_id == current_level else NSControlStateValueOff)
            btn.setTarget_(self)
            btn.setAction_(objc.selector(self.notificationLevelChanged_, signature=b'v@:@'))
            btn.setTag_(hash(level_id) % 1000000)
            _disableAutoresizing(btn)
            btn.setContentHuggingPriority_forOrientation_(750, 0)  # Don't stretch
            self._notif_buttons[level_id] = btn
            self._button_tags[btn.tag()] = level_id

            desc_label = _createDescriptionLabel(description)
            desc_label.setContentCompressionResistancePriority_forOrientation_(250, 0)

            row = _createHorizontalRow(btn, desc_label)
            stackView.addArrangedSubview_(row)

        return scrollView

    def _getLastSyncText(self) -> str:
        """Get formatted last sync text."""
        if self.store.last_sync_time:
            try:
                last = datetime.fromisoformat(self.store.last_sync_time)
                time_str = last.strftime("%b %d at %-I:%M %p")
                status = "succeeded" if self.store.last_sync_status == "success" else "failed"
                return f"Last sync {status} {time_str}"
            except ValueError:
                pass
        return "No sync yet"

    def chooseSyncFolder_(self, sender):
        """Show folder picker."""
        panel = NSOpenPanel.openPanel()
        panel.setCanChooseFiles_(False)
        panel.setCanChooseDirectories_(True)
        panel.setAllowsMultipleSelection_(False)
        panel.setCanCreateDirectories_(True)
        panel.setPrompt_("Choose")

        if self.store.output_folder:
            panel.setDirectoryURL_(NSURL.fileURLWithPath_(self.store.output_folder))

        if panel.runModal() == 1:
            url = panel.URL()
            if url:
                path = url.path()
                self.store.output_folder = path
                self._folder_label.setStringValue_(path)

    def revealSyncFolder_(self, sender):
        """Reveal sync folder in Finder."""
        if self.store.output_folder:
            NSWorkspace.sharedWorkspace().openURL_(NSURL.fileURLWithPath_(self.store.output_folder))

    def addExclusion_(self, sender):
        """Add a folder to exclusions."""
        print("[DEBUG] addExclusion_ called")
        available = get_available_folders()
        current = set(self.store.excluded_folders)
        addable = [f for f in available if f not in current]
        print(f"[DEBUG] available={available}, current={current}, addable={addable}")

        if not addable:
            alert = NSAlert.alloc().init()
            alert.setMessageText_("No Folders Available")
            alert.setInformativeText_("All folders are already excluded, or no folders found in Granola.")
            alert.addButtonWithTitle_("OK")
            alert.runModal()
            return

        alert = NSAlert.alloc().init()
        alert.setMessageText_("Add Excluded Folder")
        alert.setInformativeText_("Select a folder to exclude from sync:")
        alert.addButtonWithTitle_("Add")
        alert.addButtonWithTitle_("Cancel")

        popup = NSPopUpButton.alloc().initWithFrame_(NSMakeRect(0, 0, 250, 26))
        for folder in addable:
            popup.addItemWithTitle_(folder)
        alert.setAccessoryView_(popup)

        if alert.runModal() == NSAlertFirstButtonReturn:
            folder = popup.titleOfSelectedItem()
            print(f"[DEBUG] User selected folder: {folder}")
            if folder:
                exclusions = list(self.store.excluded_folders)
                print(f"[DEBUG] Current exclusions before append: {exclusions}")
                exclusions.append(folder)
                print(f"[DEBUG] Exclusions after append: {exclusions}")
                print(f"[DEBUG] About to set store.excluded_folders")
                self.store.excluded_folders = exclusions
                print(f"[DEBUG] After setting, store.excluded_folders = {self.store.excluded_folders}")
                self._exclusions_table.reloadData()

    def removeExclusion_(self, sender):
        """Remove selected exclusion."""
        row = self._exclusions_table.selectedRow()
        if row >= 0:
            exclusions = list(self.store.excluded_folders)
            if row < len(exclusions):
                del exclusions[row]
                self.store.excluded_folders = exclusions
                self._exclusions_table.reloadData()

    def autoSyncToggled_(self, sender):
        """Handle auto sync toggle."""
        self.store.auto_sync_enabled = sender.state() == NSControlStateValueOn

    def intervalChanged_(self, sender):
        """Handle interval change."""
        intervals = [5, 15, 30, 60]
        idx = sender.indexOfSelectedItem()
        if 0 <= idx < len(intervals):
            self.store.sync_interval_minutes = intervals[idx]

    def notificationLevelChanged_(self, sender):
        """Handle notification level change."""
        tag = sender.tag()
        level_id = self._button_tags.get(tag)
        if level_id:
            for lid, btn in self._notif_buttons.items():
                btn.setState_(NSControlStateValueOn if lid == level_id else NSControlStateValueOff)
            self.store.notification_level = level_id

    # === Webhooks Pane ===

    def _createWebhooksPane(self) -> NSView:
        """Create the Webhooks pane using scrollable stack view."""
        scrollView, stackView = _createScrollableStackView()

        # === Webhooks Section ===
        stackView.addArrangedSubview_(_createSectionHeader("Webhooks"))
        stackView.addArrangedSubview_(_createDescriptionLabel("Send note data to external services when syncing."))

        # Webhook count
        webhooks = self.store.webhooks
        enabled = sum(1 for w in webhooks if w.get("enabled", True))
        count_text = f"{enabled} of {len(webhooks)} enabled" if webhooks else "No webhooks configured"

        self._webhook_count_label = _createDescriptionLabel(count_text)
        stackView.addArrangedSubview_(self._webhook_count_label)

        # Webhooks table (expands with window width)
        wh_scroll = NSScrollView.alloc().init()
        wh_scroll.setBorderType_(2)
        wh_scroll.setHasVerticalScroller_(True)
        wh_scroll.setAutohidesScrollers_(True)
        _disableAutoresizing(wh_scroll)
        _activate(_setHeight(wh_scroll, 140))

        self._webhooks_table = NSTableView.alloc().init()
        self._webhooks_table.setColumnAutoresizingStyle_(4)  # Uniform

        name_col = NSTableColumn.alloc().initWithIdentifier_("name")
        name_col.setTitle_("Name")
        name_col.setWidth_(120)
        name_col.setMinWidth_(80)
        name_col.setResizingMask_(1)
        self._webhooks_table.addTableColumn_(name_col)

        url_col = NSTableColumn.alloc().initWithIdentifier_("url")
        url_col.setTitle_("URL")
        url_col.setWidth_(250)
        url_col.setMinWidth_(100)
        url_col.setResizingMask_(1)
        self._webhooks_table.addTableColumn_(url_col)

        enabled_col = NSTableColumn.alloc().initWithIdentifier_("enabled")
        enabled_col.setTitle_("On")
        enabled_col.setWidth_(40)
        enabled_col.setMinWidth_(40)
        enabled_col.setMaxWidth_(50)
        self._webhooks_table.addTableColumn_(enabled_col)

        self._webhooks_data = WebhooksDataSource.alloc().initWithStore_(self.store)
        self._webhooks_table.setDataSource_(self._webhooks_data)
        self._webhooks_table.setDelegate_(self._webhooks_data)
        wh_scroll.setDocumentView_(self._webhooks_table)
        stackView.addArrangedSubview_(wh_scroll)

        # Webhook action buttons
        add_btn = NSButton.alloc().init()
        add_btn.setTitle_("Add")
        add_btn.setBezelStyle_(NSBezelStyleRounded)
        add_btn.setTarget_(self)
        add_btn.setAction_(objc.selector(self.addWebhook_, signature=b'v@:@'))
        _disableAutoresizing(add_btn)

        edit_btn = NSButton.alloc().init()
        edit_btn.setTitle_("Edit")
        edit_btn.setBezelStyle_(NSBezelStyleRounded)
        edit_btn.setTarget_(self)
        edit_btn.setAction_(objc.selector(self.editWebhook_, signature=b'v@:@'))
        _disableAutoresizing(edit_btn)

        remove_btn = NSButton.alloc().init()
        remove_btn.setTitle_("Remove")
        remove_btn.setBezelStyle_(NSBezelStyleRounded)
        remove_btn.setTarget_(self)
        remove_btn.setAction_(objc.selector(self.removeWebhook_, signature=b'v@:@'))
        _disableAutoresizing(remove_btn)

        toggle_btn = NSButton.alloc().init()
        toggle_btn.setTitle_("Toggle")
        toggle_btn.setBezelStyle_(NSBezelStyleRounded)
        toggle_btn.setTarget_(self)
        toggle_btn.setAction_(objc.selector(self.toggleWebhook_, signature=b'v@:@'))
        _disableAutoresizing(toggle_btn)

        wh_buttons_row = _createHorizontalRow(add_btn, edit_btn, remove_btn, toggle_btn)
        stackView.addArrangedSubview_(wh_buttons_row)

        # === Webhook History Section ===
        stackView.addArrangedSubview_(_createSectionHeader("Webhook History"))
        stackView.addArrangedSubview_(_createDescriptionLabel("Recent webhook calls across all webhooks."))

        # History table (expands with window width)
        hist_scroll = NSScrollView.alloc().init()
        hist_scroll.setBorderType_(2)
        hist_scroll.setHasVerticalScroller_(True)
        hist_scroll.setAutohidesScrollers_(True)
        _disableAutoresizing(hist_scroll)
        _activate(_setHeight(hist_scroll, 120))

        self._history_table = NSTableView.alloc().init()
        self._history_table.setColumnAutoresizingStyle_(4)  # Uniform

        time_col = NSTableColumn.alloc().initWithIdentifier_("time")
        time_col.setTitle_("Time")
        time_col.setWidth_(80)
        time_col.setMinWidth_(60)
        self._history_table.addTableColumn_(time_col)

        wh_col = NSTableColumn.alloc().initWithIdentifier_("webhook")
        wh_col.setTitle_("Webhook")
        wh_col.setWidth_(100)
        wh_col.setMinWidth_(60)
        wh_col.setResizingMask_(1)
        self._history_table.addTableColumn_(wh_col)

        doc_col = NSTableColumn.alloc().initWithIdentifier_("document")
        doc_col.setTitle_("Document")
        doc_col.setWidth_(180)
        doc_col.setMinWidth_(80)
        doc_col.setResizingMask_(1)
        self._history_table.addTableColumn_(doc_col)

        status_col = NSTableColumn.alloc().initWithIdentifier_("status")
        status_col.setTitle_("Status")
        status_col.setWidth_(50)
        status_col.setMinWidth_(40)
        status_col.setMaxWidth_(60)
        self._history_table.addTableColumn_(status_col)

        self._history_data = HistoryDataSource.alloc().init()
        self._history_table.setDataSource_(self._history_data)
        self._history_table.setDelegate_(self._history_data)
        hist_scroll.setDocumentView_(self._history_table)
        stackView.addArrangedSubview_(hist_scroll)

        # History action buttons
        replay_btn = NSButton.alloc().init()
        replay_btn.setTitle_("Replay")
        replay_btn.setBezelStyle_(NSBezelStyleRounded)
        replay_btn.setTarget_(self)
        replay_btn.setAction_(objc.selector(self.replayWebhook_, signature=b'v@:@'))
        _disableAutoresizing(replay_btn)

        clear_btn = NSButton.alloc().init()
        clear_btn.setTitle_("Clear All")
        clear_btn.setBezelStyle_(NSBezelStyleRounded)
        clear_btn.setTarget_(self)
        clear_btn.setAction_(objc.selector(self.clearHistory_, signature=b'v@:@'))
        _disableAutoresizing(clear_btn)

        refresh_btn = NSButton.alloc().init()
        refresh_btn.setTitle_("Refresh")
        refresh_btn.setBezelStyle_(NSBezelStyleRounded)
        refresh_btn.setTarget_(self)
        refresh_btn.setAction_(objc.selector(self.refreshHistory_, signature=b'v@:@'))
        _disableAutoresizing(refresh_btn)

        hist_buttons_row = _createHorizontalRow(replay_btn, clear_btn, refresh_btn)
        stackView.addArrangedSubview_(hist_buttons_row)

        return scrollView

    def _refreshWebhooksPane(self):
        """Refresh webhook display."""
        webhooks = self.store.webhooks
        enabled = sum(1 for w in webhooks if w.get("enabled", True))
        count_text = f"{enabled} of {len(webhooks)} enabled" if webhooks else "No webhooks configured"
        self._webhook_count_label.setStringValue_(count_text)
        self._webhooks_table.reloadData()

    def addWebhook_(self, sender):
        """Add a new webhook."""
        dialog = WebhookEditDialog.alloc().initWithWebhook_store_(None, self.store)
        result = dialog.runModal()
        if result:
            webhooks = list(self.store.webhooks)
            webhooks.append(result)
            self.store.webhooks = webhooks
            self._refreshWebhooksPane()

    def editWebhook_(self, sender):
        """Edit selected webhook."""
        row = self._webhooks_table.selectedRow()
        webhooks = self.store.webhooks
        if 0 <= row < len(webhooks):
            dialog = WebhookEditDialog.alloc().initWithWebhook_store_(webhooks[row], self.store)
            result = dialog.runModal()
            if result:
                webhooks = list(self.store.webhooks)
                webhooks[row] = result
                self.store.webhooks = webhooks
                self._refreshWebhooksPane()

    def removeWebhook_(self, sender):
        """Remove selected webhook."""
        row = self._webhooks_table.selectedRow()
        webhooks = self.store.webhooks
        if 0 <= row < len(webhooks):
            webhooks = list(self.store.webhooks)
            del webhooks[row]
            self.store.webhooks = webhooks
            self._refreshWebhooksPane()

    def toggleWebhook_(self, sender):
        """Toggle webhook enabled state."""
        row = self._webhooks_table.selectedRow()
        webhooks = self.store.webhooks
        if 0 <= row < len(webhooks):
            webhooks = list(self.store.webhooks)
            webhooks[row] = dict(webhooks[row])
            webhooks[row]["enabled"] = not webhooks[row].get("enabled", True)
            self.store.webhooks = webhooks
            self._refreshWebhooksPane()

    def replayWebhook_(self, sender):
        """Replay selected history entry."""
        row = self._history_table.selectedRow()
        history = self._history_data.history
        if 0 <= row < len(history):
            entry = history[row]
            from granola.webhooks import WebhookDispatcher
            dispatcher = WebhookDispatcher([])
            result = dispatcher.replay(entry)

            alert = NSAlert.alloc().init()
            if result.success:
                alert.setMessageText_("Replay Successful")
                alert.setInformativeText_(f"Webhook sent successfully (status {result.status_code})")
            else:
                alert.setMessageText_("Replay Failed")
                alert.setInformativeText_(result.error_message or "Unknown error")
            alert.addButtonWithTitle_("OK")
            alert.runModal()

            self._history_data.reload()
            self._history_table.reloadData()

    def clearHistory_(self, sender):
        """Clear all webhook history."""
        from granola.webhooks import clear_history
        clear_history()
        self._history_data.reload()
        self._history_table.reloadData()

    def refreshHistory_(self, sender):
        """Refresh history display."""
        self._history_data.reload()
        self._history_table.reloadData()


class ExclusionsDataSource(NSObject):
    """Data source for exclusions table."""

    def initWithStore_(self, store):
        self = objc.super(ExclusionsDataSource, self).init()
        if self is None:
            return None
        self.store = store
        return self

    def numberOfRowsInTableView_(self, tableView):
        return len(self.store.excluded_folders)

    def tableView_objectValueForTableColumn_row_(self, tableView, column, row):
        folders = self.store.excluded_folders
        if 0 <= row < len(folders):
            return folders[row]
        return ""


class WebhooksDataSource(NSObject):
    """Data source for webhooks table."""

    def initWithStore_(self, store):
        self = objc.super(WebhooksDataSource, self).init()
        if self is None:
            return None
        self.store = store
        return self

    def numberOfRowsInTableView_(self, tableView):
        return len(self.store.webhooks)

    def tableView_objectValueForTableColumn_row_(self, tableView, column, row):
        webhooks = self.store.webhooks
        if 0 <= row < len(webhooks):
            webhook = webhooks[row]
            col_id = column.identifier()
            if col_id == "name":
                return webhook.get("name", "Unnamed")
            elif col_id == "url":
                url = webhook.get("url", "")
                return url[:50] + "..." if len(url) > 50 else url
            elif col_id == "enabled":
                return "Yes" if webhook.get("enabled", True) else "No"
        return ""


class HistoryDataSource(NSObject):
    """Data source for webhook history table."""

    def init(self):
        self = objc.super(HistoryDataSource, self).init()
        if self is None:
            return None
        self.history = []
        self.reload()
        return self

    def reload(self):
        """Reload history from storage."""
        try:
            from granola.webhooks import load_history
            self.history = load_history()
        except Exception:
            self.history = []

    def numberOfRowsInTableView_(self, tableView):
        return len(self.history)

    def tableView_objectValueForTableColumn_row_(self, tableView, column, row):
        if 0 <= row < len(self.history):
            entry = self.history[row]
            col_id = column.identifier()
            if col_id == "time":
                try:
                    dt = datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))
                    return dt.strftime("%-I:%M %p")
                except Exception:
                    return entry.timestamp[:8]
            elif col_id == "webhook":
                return entry.webhook_name[:20]
            elif col_id == "document":
                title = entry.document_title or "Unknown"
                return title[:30] + "..." if len(title) > 30 else title
            elif col_id == "status":
                return "OK" if entry.success else "Fail"
        return ""


class WebhookEditDialog(NSObject):
    """Dialog for editing a webhook."""

    def initWithWebhook_store_(self, webhook, store):
        self = objc.super(WebhookEditDialog, self).init()
        if self is None:
            return None
        self.webhook = webhook or {}
        self.store = store
        self.result = None
        self._folder_checkboxes = {}  # Initialize early to prevent crash
        self._all_folders_checkbox = None
        return self

    def runModal(self):
        """Show dialog and return result."""
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Edit Webhook" if self.webhook.get("name") else "New Webhook")
        alert.addButtonWithTitle_("Save")
        alert.addButtonWithTitle_("Cancel")

        # Get available folders
        available_folders = get_available_folders()
        current_folders = set(self.webhook.get("folders", []))
        all_folders_mode = len(current_folders) == 0

        # Calculate dialog height based on folder count
        folder_rows = max(1, len(available_folders))
        folder_section_height = 20 + (folder_rows * 22)  # label + checkboxes
        dialog_height = 120 + folder_section_height + 10

        # Dialog content using setFrame_ (simpler for fixed-size dialog)
        view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 380, dialog_height))

        y = dialog_height - 30

        # Name
        name_label = NSTextField.labelWithString_("Name:")
        name_label.setFrame_(NSMakeRect(0, y, 50, 18))
        view.addSubview_(name_label)

        self._name_field = NSTextField.alloc().initWithFrame_(NSMakeRect(55, y, 320, 22))
        self._name_field.setStringValue_(self.webhook.get("name", ""))
        view.addSubview_(self._name_field)
        y -= 30

        # URL
        url_label = NSTextField.labelWithString_("URL:")
        url_label.setFrame_(NSMakeRect(0, y, 50, 18))
        view.addSubview_(url_label)

        self._url_field = NSTextField.alloc().initWithFrame_(NSMakeRect(55, y, 320, 22))
        self._url_field.setStringValue_(self.webhook.get("url", "https://"))
        view.addSubview_(self._url_field)
        y -= 30

        # Method
        method_label = NSTextField.labelWithString_("Method:")
        method_label.setFrame_(NSMakeRect(0, y, 50, 18))
        view.addSubview_(method_label)

        self._method_popup = NSPopUpButton.alloc().initWithFrame_(NSMakeRect(55, y - 2, 100, 24))
        for method in ["POST", "GET", "PUT", "PATCH"]:
            self._method_popup.addItemWithTitle_(method)
        self._method_popup.selectItemWithTitle_(self.webhook.get("method", "POST"))
        view.addSubview_(self._method_popup)

        # Enabled
        self._enabled_checkbox = NSButton.alloc().initWithFrame_(NSMakeRect(170, y, 80, 20))
        self._enabled_checkbox.setButtonType_(NSButtonTypeSwitch)
        self._enabled_checkbox.setTitle_("Enabled")
        self._enabled_checkbox.setState_(NSControlStateValueOn if self.webhook.get("enabled", True) else NSControlStateValueOff)
        view.addSubview_(self._enabled_checkbox)
        y -= 30

        # Folders section
        folders_label = NSTextField.labelWithString_("Folders:")
        folders_label.setFrame_(NSMakeRect(0, y, 50, 18))
        view.addSubview_(folders_label)

        # "All folders" checkbox - no callback, just check state on save
        self._all_folders_checkbox = NSButton.alloc().initWithFrame_(NSMakeRect(55, y, 320, 20))
        self._all_folders_checkbox.setButtonType_(NSButtonTypeSwitch)
        self._all_folders_checkbox.setTitle_("All folders (leave unchecked to select specific folders)")
        self._all_folders_checkbox.setState_(NSControlStateValueOn if all_folders_mode else NSControlStateValueOff)
        view.addSubview_(self._all_folders_checkbox)
        y -= 22

        # Individual folder checkboxes - always enabled, user manually manages selection
        self._folder_checkboxes = {}
        if available_folders:
            for folder in available_folders:
                cb = NSButton.alloc().initWithFrame_(NSMakeRect(55, y, 320, 20))
                cb.setButtonType_(NSButtonTypeSwitch)
                cb.setTitle_(folder)
                # Only check if explicitly in current_folders (not in all_folders_mode)
                is_selected = folder in current_folders
                cb.setState_(NSControlStateValueOn if is_selected else NSControlStateValueOff)
                view.addSubview_(cb)
                self._folder_checkboxes[folder] = cb
                y -= 22
        else:
            no_folders_label = NSTextField.labelWithString_("(No folders found in Granola)")
            no_folders_label.setFont_(NSFont.systemFontOfSize_(11))
            no_folders_label.setTextColor_(NSColor.secondaryLabelColor())
            no_folders_label.setFrame_(NSMakeRect(55, y, 300, 18))
            view.addSubview_(no_folders_label)

        alert.setAccessoryView_(view)

        if alert.runModal() == NSAlertFirstButtonReturn:
            name = self._name_field.stringValue()
            url = self._url_field.stringValue()

            if not name or not url:
                errorAlert = NSAlert.alloc().init()
                errorAlert.setMessageText_("Missing Information")
                errorAlert.setInformativeText_("Please enter both a name and URL for the webhook.")
                errorAlert.addButtonWithTitle_("OK")
                errorAlert.runModal()
                return None

            # Get selected folders (empty list = all folders)
            if self._all_folders_checkbox.state() == NSControlStateValueOn:
                selected_folders = []
            else:
                selected_folders = [
                    folder for folder, cb in self._folder_checkboxes.items()
                    if cb.state() == NSControlStateValueOn
                ]
                # Require at least one folder if "All folders" is unchecked
                if not selected_folders and self._folder_checkboxes:
                    errorAlert = NSAlert.alloc().init()
                    errorAlert.setMessageText_("No Folders Selected")
                    errorAlert.setInformativeText_("Please select at least one folder, or check 'All folders'.")
                    errorAlert.addButtonWithTitle_("OK")
                    errorAlert.runModal()
                    return None

            self.result = {
                "name": name,
                "url": url,
                "method": self._method_popup.titleOfSelectedItem(),
                "enabled": self._enabled_checkbox.state() == NSControlStateValueOn,
                "folders": selected_folders,
            }
            return self.result

        return None



def show_preferences_window():
    """Show the preferences window."""
    controller = PreferencesWindowController.shared()
    controller.showWindow_(None)
