# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
 code in this repository.

## Project Overview

Granola CLI is a Python command-line tool for exporting notes and transcripts from the Granola
note-taking application. It provides three export capabilities:

1. **Notes Export**: Connects to the Granola API, authenticates using bearer tokens,
   fetches AI-generated notes in JSON format, and converts them to clean Markdown files
2. **Transcripts Export**: Reads the local Granola cache file, extracts raw meeting transcripts
   with timestamps and speaker identification, and exports them to plain text files
3. **Combined Export**: Merges notes and transcripts with folder organization

## Common Commands

### Install

```bash
pip install -e .           # Install in editable mode
pip install -e ".[dev]"    # Install with dev dependencies
```

### Run

```bash
# Export notes (AI-generated from API)
granola notes --supabase ~/Library/Application\ Support/Granola/supabase.json

# Export transcripts (raw from cache file)
granola transcripts

# Export combined with folder structure
granola export --supabase ~/Library/Application\ Support/Granola/supabase.json
```

### Test

```bash
pytest                    # Run all tests
pytest -v                 # Verbose output
pytest --cov=granola      # With coverage
```

### Lint and Format

```bash
ruff check .              # Run linter
ruff format .             # Format code
mypy src/granola          # Type checking
```

## Architecture

The project follows a modular Python CLI application structure:

- **Entry Point**: `src/granola/__main__.py` - Allows `python -m granola`
- **CLI Layer**: `src/granola/cli/` - Typer command definitions
  - `main.py` - Root app with global options (--debug, --supabase, --config)
  - `notes.py` - Notes export command (--timeout, --output)
  - `transcripts.py` - Transcripts export command (--cache, --output)
  - `export.py` - Combined export command (--timeout, --cache, --output)
- **Internal Packages**:
  - `api/` - Granola API client with bearer token auth and Pydantic models
  - `cache/` - Cache file reader for transcript data
  - `config/` - Pydantic Settings for configuration management
  - `prosemirror/` - ProseMirror JSON to Markdown/plain text conversion
  - `formatters/` - Document formatters (markdown, transcript, combined)
  - `writers/` - File writers with sanitization and sync capabilities
  - `utils/` - Utility functions (paths, filenames)
- **Configuration**: Supports multiple configuration sources:
  - Environment variables via `.env` file (using python-dotenv)
  - Command-line flags via Typer
  - Environment variable: `SUPABASE_FILE`

## Key Dependencies

- **typer**: CLI framework with rich terminal support
- **pydantic**: Data validation and models
- **pydantic-settings**: Configuration management (env vars, .env files)
- **httpx**: HTTP client for API communication
- **pyyaml**: YAML frontmatter generation
- **python-dotenv**: .env file support
- **rich**: Terminal formatting (via typer[all])

## Development Notes

- The root command is "granola" with "notes", "transcripts", and "export" subcommands
- Debug logging is available via the `--debug` flag
- Configuration precedence: flags > env vars > defaults
- Logger is configured based on debug flag
- Python 3.11+ required for modern type hints

## Testing Approach

- **Test Framework**: pytest
- **Test Isolation**: All tests should be independent
- **Mock HTTP**: Use respx for mocking httpx requests
- **Temp Files**: Use pytest's `tmp_path` fixture for filesystem tests
- **Test Focus**: Write focused tests for each function

## Granola-Specific Implementation Notes

### API Integration

- Bearer token authentication required for all API calls
- Token extracted from supabase.json file (WorkOS tokens)
- Token file path configured via `--supabase` flag or `SUPABASE_FILE` environment variable
- API endpoint: `https://api.granola.ai/v2/get-documents` (POST request)
- Request body includes: `limit: 100`, `offset: 0`, `include_last_viewed_panel: true`
- Required headers:
  - `Authorization: Bearer <token>`
  - `User-Agent: Granola/5.354.0`
  - `X-Client-Version: 5.354.0`
  - `Content-Type: application/json`
  - `Accept: */*`
- HTTP client with configurable timeout (default 2 minutes)
- Content is returned in ProseMirror JSON format in `last_viewed_panel.content`

### Notes Export Process (API-Based)

1. Load supabase.json file from configured path
2. Extract access token from WorkOS tokens in supabase.json
3. Authenticate with Granola API using bearer token (POST request with include_last_viewed_panel)
4. Fetch all documents from the API (returns JSON with `docs` array)
5. Parse JSON response into Pydantic models (Document with custom validators)
6. For each document:
   - Check if file exists and compare `updated_at` timestamp with file modification time
   - Skip if file is up-to-date (incremental export)
   - Convert ProseMirror JSON content to Markdown (supports headings, paragraphs, bullet lists, nested lists)
   - Add YAML frontmatter with metadata
   - Sanitize filenames and handle duplicates
   - Save/update file in output directory (default: ~/My Drive/z. Granola Notes/Markdown)

### Transcript Export Process (Cache-Based)

1. Locate Granola cache file (default: `~/Library/Application Support/Granola/cache-v3.json`)
2. Read and parse double-JSON encoded cache structure:
   - Outer JSON: `{"cache": "<json-string>"}`
   - Inner JSON: Contains `state.documents` and `state.transcripts` maps
3. Extract document metadata (ID, Title, CreatedAt, UpdatedAt) from documents map
4. Extract transcript segments from transcripts map (keyed by document ID)
5. For each document with transcript segments:
   - Check if file exists and compare `updated_at` timestamp with file modification time
   - Skip if file is up-to-date (incremental export)
   - Format segments with timestamps and speaker identification:
     - Parse RFC3339 timestamps to HH:MM:SS format
     - Map "system" source to "System" speaker
     - Map "microphone" source to "You" speaker
   - Create text file with metadata header and formatted transcript
   - Sanitize filenames and handle duplicates
   - Save/update file in output directory (default: ./transcripts)

**Important Notes:**

- Notes are available for ALL meetings (AI-generated from various sources)
- Transcripts are ONLY available for meetings where audio recording was enabled
- The Granola API does NOT provide raw transcript data - it must be read from the local cache
- Speaker identification is limited to "System" (other participants/system audio) and "You" (user's microphone)
- Granola does not provide named speaker labels as it doesn't join meetings as a participant

### File Naming

- Use note title as filename, fallback to ID if title is empty
- Sanitize filenames by removing invalid characters (regex: `[<>:"/\\|?*\x00-\x1f]`)
- Handle duplicate names by appending `_2`, `_3`, etc.
- Limit filename length to 100 characters for compatibility

### Error Handling

- Validate API token before making requests
- Handle network errors and timeouts
- Provide clear error messages for users
- Use Typer's Exit for graceful error handling
- Internal packages raise exceptions; CLI layer handles user display
