# Granola Sync Menu Bar App

A macOS menu bar app that automatically syncs your Granola meeting notes to a local folder (e.g., Google Drive).

## Prerequisites

- macOS 12 or later
- [Granola](https://granola.ai) installed and signed in

## Installation

### 1. Install Python 3.11+

macOS doesn't include Python by default. Install it via Homebrew:

```bash
# Install Homebrew if you don't have it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python
brew install python@3.12
```

### 2. Install Granola CLI

```bash
# Clone the repository
git clone https://github.com/milesskorpen/granola.git
cd granola

# Install the package
pip3 install -e .
```

### 3. Add to PATH (if needed)

If you get "command not found" errors, add Python's bin directory to your PATH:

```bash
echo 'export PATH="/opt/homebrew/opt/python@3.12/libexec/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

## Running the App

```bash
granola-menubar
```

A 🥣 icon will appear in your menu bar.

## Packaging (macOS .app)

Create a standalone macOS app bundle using py2app.

1. Ensure Xcode Command Line Tools are installed:
   ```bash
   xcode-select --install
   ```
2. Generate the app icon and build the app:
   ```bash
   chmod +x scripts/make_icns.sh scripts/build_macos_app.sh
   ./scripts/build_macos_app.sh
   ```
   This writes `macos/Granola.icns` and builds `dist/Granola Sync.app`.
3. Run it:
   ```bash
   open "dist/Granola Sync.app"
   ```

### Distribute

- Zip:
  ```bash
  (cd dist && zip -r GranolaSync.zip "Granola Sync.app")
  ```
- DMG:
  ```bash
  hdiutil create -volname "Granola Sync" -srcfolder "dist/Granola Sync.app" -ov -format UDZO GranolaSync.dmg
  ```
- Optional codesign:
  ```bash
  codesign --force --deep --sign "Developer ID Application: Your Name (TEAMID)" "dist/Granola Sync.app"
  ```

## First-Time Setup

1. **Click the 🥣 icon** in your menu bar
2. **Click "Settings..."** and select your sync destination folder (e.g., `~/Google Drive/My Drive/Granola Notes`)
3. **Click "Manage Excluded Folders..."** to select any Granola folders you want to exclude from syncing
4. **Click "Auto Sync"** and choose how often to sync (recommended: every 15 minutes)
5. **Click "Start at Login"** to have the app start automatically when you log in
6. **Click "Sync Now"** to run your first sync

## Menu Options

| Option | Description |
|--------|-------------|
| **Sync Now** | Manually trigger a sync |
| **Settings...** | Choose the destination folder for synced notes |
| **Manage Excluded Folders...** | Select Granola folders to exclude from sync |
| **Auto Sync** | Set automatic sync interval (5/15/30/60 min or disabled) |
| **Start at Login** | Toggle whether app starts when you log in |
| **Quit** | Close the menu bar app |

## How It Works

- Notes are exported as `.txt` files with the format: `YYYY-MM-DD_Title_id.txt`
- Files are organized into folders matching your Granola folder structure
- Notes without a folder go into an "Uncategorized" folder
- Notes in excluded folders are completely skipped (even if they're also in other folders)
- Deleted notes are automatically removed from the sync folder
- Only changed files are updated (incremental sync)

## Configuration Files

Settings are stored in:
```
~/.config/granola/settings.json
```

The login item plist (if enabled) is stored in:
```
~/Library/LaunchAgents/com.granola.menubar.plist
```

## Troubleshooting

### "Command not found: granola-menubar"

Make sure Python's bin directory is in your PATH:

```bash
# Find where pip installed the script
pip3 show granola-cli | grep Location

# Add that path's bin directory to your PATH
echo 'export PATH="/path/to/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### "supabase.json not found"

Make sure Granola is installed and you've signed in at least once. The app looks for credentials at:
```
~/Library/Application Support/Granola/supabase.json
```

### Sync not working

1. Click the 🥣 icon and check the status message
2. Look at the sync logs:
   ```bash
   cat ~/.config/granola/sync.log
   cat ~/.config/granola/sync.error.log
   ```

### App won't start at login

Try removing and re-adding the login item:
1. Click "Start at Login" to uncheck it
2. Click "Start at Login" again to re-enable it

Or manually check:
```bash
launchctl list | grep granola
```

## Uninstalling

```bash
# Stop the app
# Click 🥣 → Quit

# Disable start at login (removes the plist)
# Click 🥣 → Start at Login (uncheck)

# Or manually remove:
launchctl unload ~/Library/LaunchAgents/com.granola.menubar.plist
rm ~/Library/LaunchAgents/com.granola.menubar.plist

# Remove the package
pip3 uninstall granola-cli

# Remove config files (optional)
rm -rf ~/.config/granola
```

## Command Line Usage

You can also run syncs from the command line:

```bash
# Basic sync
granola export --output ~/Google\ Drive/My\ Drive/Granola\ Notes/

# Exclude folders
granola export --output ~/path/to/folder --exclude-folder "Private" --exclude-folder "Archive"

# See all options
granola export --help
```
