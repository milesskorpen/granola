# Granola CLI

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

Export your [Granola](https://granola.ai) notes and transcripts to local files for backup, migration, or offline access.

## Why Use This?

- **Own Your Data** - Keep local copies of all your meeting notes
- **Full Transcripts** - Export complete, timestamped transcripts of your meetings
- **Backup & Migration** - Safeguard your notes or move them to other tools
- **Smart Updates** - Only exports new or changed content
- **Fast & Simple** - One command to export everything

## Installation

### Install with pip (Recommended)

```bash
pip install granola-cli
```

### Install from Source

```bash
git clone https://github.com/theantichris/granola.git
cd granola
pip install -e .
```

## Quick Start

### Export Your Notes

Your notes are the AI-generated summaries and formatted content from Granola.

**macOS/Linux:**

```bash
granola notes --supabase "$HOME/Library/Application Support/Granola/supabase.json"
```

**Windows (PowerShell):**

```powershell
granola notes --supabase "$env:APPDATA\Granola\supabase.json"
```

Notes will be exported to `~/My Drive/z. Granola Notes/Markdown` as Markdown files.

### Export Your Transcripts

Transcripts are the raw, timestamped recordings of everything said in your meetings.

**Note:** Transcripts are only available for meetings where you enabled audio recording.

**macOS:**

```bash
granola transcripts
```

**Linux:**

```bash
granola transcripts --cache "$HOME/.config/Granola/cache-v3.json"
```

**Windows (PowerShell):**

```powershell
granola transcripts --cache "$env:APPDATA\Granola\cache-v3.json"
```

Transcripts will be exported to a `transcripts/` directory as text files.

### Combined Export with Folder Structure

Export both notes and transcripts together, organized by your Granola folders:

```bash
granola export --supabase "$HOME/Library/Application Support/Granola/supabase.json"
```

## Where Granola Stores Your Data

### Supabase Credentials File

Granola uses a `supabase.json` file for API authentication:

- **macOS**: `~/Library/Application Support/Granola/supabase.json`
- **Linux**: `~/.config/Granola/supabase.json` or `~/.local/share/Granola/supabase.json`
- **Windows**: `%APPDATA%\Granola\supabase.json`

### Cache File (for Transcripts)

Granola stores raw transcripts in a local cache file:

- **macOS**: `~/Library/Application Support/Granola/cache-v3.json`
- **Linux**: `~/.config/Granola/cache-v3.json` or `~/.local/share/Granola/cache-v3.json`
- **Windows**: `%APPDATA%\Granola\cache-v3.json`

## Common Options

### Custom Output Directory

```bash
# Export notes to a specific location
granola notes --output ~/Documents/MyNotes

# Export transcripts to a specific location
granola transcripts --output ~/Documents/MyTranscripts

# Export combined to a specific location
granola export --output ~/Documents/GranolaNotes
```

### Set Default Configuration

Set the `SUPABASE_FILE` environment variable to avoid specifying the path every time:

```bash
export SUPABASE_FILE="$HOME/Library/Application Support/Granola/supabase.json"
```

Or create a `.env` file in your working directory:

```env
SUPABASE_FILE=/Users/yourname/Library/Application Support/Granola/supabase.json
```

Then simply run:

```bash
granola notes
granola transcripts
granola export
```

### Enable Debug Logging

```bash
granola notes --debug
granola transcripts --debug
granola export --debug
```

## Commands

### `granola notes`

Export AI-generated notes to Markdown files.

```bash
granola notes [OPTIONS]
```

**Options:**
- `--timeout INTEGER` - HTTP timeout in seconds (default: 120)
- `--output TEXT` - Output directory for exported Markdown files

### `granola transcripts`

Export raw transcripts to text files.

```bash
granola transcripts [OPTIONS]
```

**Options:**
- `--cache TEXT` - Path to Granola cache file
- `--output TEXT` - Output directory for exported transcript files

### `granola export`

Export combined notes and transcripts with folder structure.

```bash
granola export [OPTIONS]
```

**Options:**
- `--timeout INTEGER` - HTTP timeout in seconds (default: 120)
- `--cache TEXT` - Path to Granola cache file
- `--output TEXT` - Output directory for exported files

### Global Options

- `--debug` - Enable debug logging
- `--supabase TEXT` - Path to supabase.json file
- `--version` - Show version and exit
- `--help` - Show help and exit

## What Gets Exported

### Notes (Markdown Files)

Each note becomes a separate `.md` file with:

- **YAML frontmatter** - ID, timestamps, tags
- **Title** - As a top-level heading
- **Content** - Formatted as Markdown with headings, lists, etc.

Example:

```markdown
---
id: abc-123
created: "2024-01-01T00:00:00Z"
updated: "2024-01-02T00:00:00Z"
tags:
  - work
  - planning
---

# Meeting Notes

## Key Points

- First important point
- Second important point
```

### Transcripts (Text Files)

Each transcript becomes a `.txt` file with:

- **Header** - Title, ID, timestamps, segment count
- **Timestamped dialogue** - `[HH:MM:SS] Speaker: Text`
- **Speaker labels** - "System" (others) or "You" (your microphone)

Example:

```text
================================================================================
Team Sync Meeting
ID: abc-123
Created: 2024-01-01T14:00:00.000Z
Segments: 142
================================================================================

[14:00:04] System: Good morning everyone, how's it going?
[14:00:06] You: Good morning! Ready to start.
```

## Troubleshooting

### "Failed to read supabase file"

- Make sure Granola is installed and you've logged in at least once
- Check that the path to `supabase.json` is correct for your OS
- Try running Granola app first, then export

### "No transcripts found"

- Transcripts are only available for meetings where audio recording was enabled
- Check that the cache file path is correct
- Make sure you've had at least one meeting with recording enabled

### "Permission denied"

- Make sure you have read access to the Granola files
- Try running without `sudo` - it's not needed

### Need More Help?

- Check the `--help` output: `granola --help`
- [Open an issue](https://github.com/theantichris/granola/issues) on GitHub

---

## For Contributors & Developers

The sections below are for those who want to contribute to the project or build from source.

### Development Setup

**Requirements:**

- Python 3.11 or higher
- pip

**Clone and install in development mode:**

```bash
git clone https://github.com/theantichris/granola.git
cd granola
pip install -e ".[dev]"
```

### Project Structure

```text
granola/
├── src/
│   └── granola/
│       ├── cli/              # CLI commands (Typer)
│       │   ├── main.py       # Root command and configuration
│       │   ├── notes.py      # Notes export (API-based)
│       │   ├── transcripts.py # Transcripts export (cache-based)
│       │   └── export.py     # Combined export with folders
│       ├── api/              # Granola API client
│       ├── cache/            # Cache file reader
│       ├── config/           # Pydantic Settings
│       ├── formatters/       # Document formatters
│       ├── prosemirror/      # ProseMirror JSON parser
│       ├── writers/          # File system operations
│       └── utils/            # Utility functions
├── tests/                    # Test files
├── pyproject.toml            # Project configuration
├── README.md                 # This file
├── CLAUDE.md                 # AI assistant guidelines
└── LICENSE                   # MIT License
```

### Development Commands

```bash
# Run the CLI
granola --help
python -m granola --help

# Run tests
pytest

# Run tests with coverage
pytest --cov=granola

# Run linter
ruff check .

# Run type checker
mypy src/granola

# Format code
ruff format .
```

### Testing

The project uses pytest for testing:

```bash
pytest                    # All tests
pytest -v                 # Verbose output
pytest --cov=granola      # With coverage
```

### Key Dependencies

- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Pydantic](https://docs.pydantic.dev/) - Data validation
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) - Configuration management
- [httpx](https://www.python-httpx.org/) - HTTP client
- [Rich](https://rich.readthedocs.io/) - Terminal formatting

### Architecture

**Notes Export (API-based):**

1. Read Supabase credentials from local file
2. Authenticate with Granola API
3. Fetch all documents as JSON (with pagination)
4. Convert ProseMirror JSON to Markdown
5. Write files with YAML frontmatter

**Transcripts Export (Cache-based):**

1. Read local cache file (double-JSON encoded)
2. Extract transcript segments by document ID
3. Format segments with timestamps and speakers
4. Write text files with metadata headers

**Combined Export:**

1. Fetch notes from API and transcripts from cache
2. Merge data and organize by folder structure
3. Sync to filesystem with incremental updates

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Granola](https://granola.so) - The amazing note-taking app this tool exports from
- [Typer](https://typer.tiangolo.com/) - For the excellent CLI framework
- [Pydantic](https://docs.pydantic.dev/) - For data validation and settings

## Support

For issues, questions, or feature requests:

- [Open an issue](https://github.com/theantichris/granola/issues) on GitHub
- Check existing issues for solutions
- Include debug output (`--debug`) when reporting problems

---

Built with love by the community
