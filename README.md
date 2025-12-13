# Granola Sync

```text
                                       _
                             _        | |
  __ _ _ __ __ _ _ __   ___ | | __ _  | |
 / _` | '__/ _` | '_ \ / _ \| |/ _` | | |
| (_| | | | (_| | | | | (_) | | (_| | | |
 \__, |_|  \__,_|_| |_|\___/|_|\__,_| | |
 |___/                                |_|
```

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/github/license/theantichris/granola)](LICENSE)

Automatically sync your [Granola](https://granola.ai) meeting notes to a local folder. Perfect for backing up to Google Drive, Dropbox, or any folder on your Mac.

## Features

- **Menu Bar App** - Lives in your menu bar (🥣) for easy access
- **Auto Sync** - Automatically syncs on a schedule (5/15/30/60 minutes)
- **Folder Organization** - Notes organized by your Granola folders
- **Exclude Folders** - Skip private or sensitive folders from syncing
- **Shared Notes** - Includes notes shared with you by teammates
- **Smart Updates** - Only syncs changed files, removes deleted notes
- **Start at Login** - Optionally start the app when you log in

## Quick Start

### 1. Install

```bash
# Install Homebrew (if needed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python
brew install python@3.12

# Clone and install
git clone https://github.com/theantichris/granola.git
cd granola
pip3 install -e .
```

### 2. Run the Menu Bar App

```bash
granola-menubar
```

A 🥣 icon appears in your menu bar.

### 3. Configure

1. Click 🥣 → **Settings...** → Select your sync folder (e.g., Google Drive)
2. Click 🥣 → **Manage Excluded Folders...** → Select folders to skip
3. Click 🥣 → **Auto Sync** → Choose sync frequency
4. Click 🥣 → **Start at Login** → Enable to run at startup
5. Click 🥣 → **Sync Now** → Run your first sync!

## Menu Bar Options

| Option | Description |
|--------|-------------|
| **Sync Now** | Manually trigger a sync |
| **Settings...** | Choose destination folder |
| **Manage Excluded Folders...** | Select Granola folders to exclude |
| **Auto Sync** | Set sync interval (5/15/30/60 min or disabled) |
| **Start at Login** | Auto-start when you log in |
| **Quit** | Close the app |

## Command Line Usage

You can also use the CLI directly:

```bash
# Sync to a folder
granola export --output ~/Google\ Drive/My\ Drive/Granola\ Notes/

# Exclude specific folders
granola export --output ~/path/to/folder --exclude-folder "Private" --exclude-folder "Archive"

# Export just notes (as Markdown)
granola notes --output ~/Documents/GranolaNotes

# Export just transcripts
granola transcripts --output ~/Documents/Transcripts

# See all options
granola --help
```

### Environment Variables

Set these to avoid typing paths every time:

```bash
# Add to ~/.zshrc
export SUPABASE_FILE="$HOME/Library/Application Support/Granola/supabase.json"
export PATH="/opt/homebrew/opt/python@3.12/libexec/bin:$PATH"
```

## Output Format

### Combined Export (Default)

Files are named: `YYYY-MM-DD_Title_id.txt`

```
Google Drive/
└── Granola Notes/
    ├── Work/
    │   ├── 2025-01-15_Team Standup_abc123.txt
    │   └── 2025-01-14_Project Review_def456.txt
    ├── Personal/
    │   └── 2025-01-13_1-on-1 with Manager_ghi789.txt
    └── Uncategorized/
        └── 2025-01-12_Quick Call_jkl012.txt
```

Each file contains:
- Header with title, ID, timestamps, and folder info
- AI-generated notes (formatted as Markdown)
- Full transcript with timestamps (if recording was enabled)

### Notes Export (Markdown)

```markdown
---
id: abc-123
created: "2025-01-15T14:00:00Z"
updated: "2025-01-15T15:00:00Z"
---

# Team Standup

## Key Points

- Sprint progress on track
- New feature launching next week
```

### Transcripts Export (Text)

```
================================================================================
Team Standup
ID: abc-123
Created: 2025-01-15T14:00:00.000Z
================================================================================

[14:00:04] System: Good morning everyone
[14:00:06] You: Morning! Let's get started
[14:00:10] System: I'll share my screen
```

## Configuration

Settings are stored in `~/.config/granola/settings.json`:

```json
{
  "output_folder": "/Users/you/Google Drive/My Drive/Granola Notes",
  "excluded_folders": ["Private", "Archive"],
  "sync_interval_minutes": 15,
  "start_at_login": true
}
```

## Troubleshooting

### "command not found: granola-menubar"

Add Python to your PATH:

```bash
echo 'export PATH="/opt/homebrew/opt/python@3.12/libexec/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### "supabase.json not found"

Make sure Granola is installed and you've signed in. The app looks for:
```
~/Library/Application Support/Granola/supabase.json
```

### Sync not working

Check the logs:
```bash
cat ~/.config/granola/sync.log
cat ~/.config/granola/sync.error.log
```

### App won't start at login

Toggle "Start at Login" off and on again, or check:
```bash
launchctl list | grep granola
```

## Uninstalling

```bash
# Quit the app (click 🥣 → Quit)

# Disable start at login (click 🥣 → Start at Login to uncheck)

# Remove the package
pip3 uninstall granola-cli

# Remove config files (optional)
rm -rf ~/.config/granola
rm ~/Library/LaunchAgents/com.granola.menubar.plist
```

---

## For Developers

### Project Structure

```
granola/
├── src/granola/
│   ├── cli/              # CLI commands (Typer)
│   │   ├── main.py       # Root command
│   │   ├── notes.py      # Notes export
│   │   ├── transcripts.py # Transcripts export
│   │   └── export.py     # Combined export
│   ├── menubar/          # Menu bar app (rumps)
│   │   ├── app.py        # Main app
│   │   ├── settings.py   # Settings management
│   │   └── launchd.py    # launchd helpers
│   ├── api/              # Granola API client
│   ├── cache/            # Cache file reader
│   ├── formatters/       # Output formatters
│   ├── prosemirror/      # ProseMirror parser
│   └── writers/          # File sync logic
├── tests/
├── pyproject.toml
└── README.md
```

### Development Setup

```bash
git clone https://github.com/theantichris/granola.git
cd granola
pip install -e ".[dev]"
```

### Commands

```bash
# Run tests
pytest

# Run linter
ruff check .

# Type check
mypy src/granola
```

### Key Dependencies

- [Typer](https://typer.tiangolo.com/) - CLI framework
- [rumps](https://github.com/jaredks/rumps) - macOS menu bar apps
- [Pydantic](https://docs.pydantic.dev/) - Data validation
- [httpx](https://www.python-httpx.org/) - HTTP client

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Granola](https://granola.ai) - The note-taking app this syncs from
- [rumps](https://github.com/jaredks/rumps) - Menu bar framework
- [Typer](https://typer.tiangolo.com/) - CLI framework
