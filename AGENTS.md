# Repository Guidelines

## Project Structure & Modules

- `src/granola/`: main package (CLI, API, formatters, writers, config, menubar).
  - `cli/`: Typer commands exposed via `granola`.
  - `api/`: HTTPX client, models, auth.
  - `formatters/`, `writers/`, `utils/`, `cache/`, `prosemirror/`: export and helpers.
  - `menubar/`: macOS menu bar app (see `src/granola/menubar/README.md`).
- `tests/`: pytest tests.
- `pyproject.toml`: tooling (ruff, mypy, pytest) and entry points.

## Build, Test, and Dev Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]

# Run (CLI)
granola --help
granola export --output ~/path/to/folder

# Run (menu bar)
granola-menubar

# Lint & format
ruff check . && ruff format .

# Type check
mypy src

# Tests
pytest -q
pytest --cov=granola

# Optional pre-commit hooks
pre-commit install && pre-commit run -a
```

## Coding Style & Naming

- Python 3.11+, 4-space indents, max line length 100 (see `tool.ruff`).
- Use type hints throughout; keep mypy strict clean.
- Names: `snake_case` for functions/vars, `PascalCase` for classes, `UPPER_SNAKE` for constants.
- Keep modules under `src/granola/...`; new CLI commands live in `src/granola/cli/` using Typer.

## Testing Guidelines

- Framework: pytest (`tests/` as configured via `pyproject.toml`).
- Name tests `test_*.py`; mirror package paths where practical.
- Mock HTTP using `respx` for `httpx` clients; avoid network in tests.
- Add coverage for new logic; prefer fast, deterministic tests.

## Commit & Pull Request Guidelines

- Commits: concise, imperative subject (e.g., "Add transcript formatter"); include context in body if needed; reference issues like `#123`.
- PRs: clear description, linked issues, test plan/steps, screenshots or logs for CLI/menubar UX changes.
- Keep diffs focused; include docs updates when behavior or commands change.

## Security & Configuration

- Do not commit secrets. Use `.env` (see `.env.example`) and environment vars like `SUPABASE_FILE` (see README) for local runs.
- macOS app writes config/logs under `~/.config/granola/`; avoid hardcoding user paths.

## Notes for Contributors

- Entry points: `granola`, `granola-menubar` (declared in `pyproject.toml`).
- Prefer small PRs; align new modules with existing package layout and naming.
