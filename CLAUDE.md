# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
 code in this repository.

## Project Overview

A Go CLI/TUI template project using the Cobra command framework with
 Charmbracelet tools for terminal UI.

## Common Commands

### Build

```bash
go build
```

### Run

```bash
go run main.go
# Or after building:
./go-template
```

### Test

```bash
go test ./...
go test -v ./...  # verbose output
```

### Module Management

```bash
go mod tidy       # clean up dependencies
go mod download   # download dependencies
```

### Releases

```bash
# Create a new release (automated via GitHub Actions)
git tag v0.1.0
git push origin v0.1.0

# Test release locally (requires GoReleaser)
goreleaser release --snapshot --clean

# Check GoReleaser configuration
goreleaser check
```

### Linting

```bash
# Markdown linting (runs in GitHub Actions, installed via brew)
markdownlint-cli2 "**/*.md"

# Go linting (if golangci-lint is installed)
golangci-lint run
```

## Architecture

The project follows a standard Go CLI application structure:

- **Entry Point**: `main.go` - Uses Charmbracelet's fang for execution context
- **Command Structure**: `cmd/` directory contains Cobra command definitions
  - `cmd/root.go` - Defines the root command with configuration initialization
- **Configuration**: Supports multiple configuration sources:
  - Environment variables via `.env` file (using godotenv)
  - Config file (`.config.toml` in home directory or current directory)
  - Command-line flags (e.g., `--debug`, `--config`)
- **Logging**: Uses Charmbracelet's log package for structured logging
  - Debug mode can be enabled via `--debug` flag or config
  - Logger includes timestamp and caller information
  - Log levels: Debug, Info, Warn, Error (defaults to Warn, Debug with debug flag)

## Key Dependencies

- **cobra**: Command-line interface framework
- **viper**: Configuration management (env vars, config files, flags)
- **charmbracelet/fang**: Enhanced command execution with context
- **charmbracelet/log**: Structured logging with customizable output formats
- **godotenv**: .env file support

## Build and Release

- **GoReleaser**: Automated release management configured in `.goreleaser.yaml`
  - Builds for Linux, macOS (Darwin), and Windows
  - Creates tar.gz archives (zip for Windows)
  - Automatically generates changelog from commit messages
  - Triggered by pushing version tags (e.g., v1.0.0)

## Development Notes

- The root command is named "example" and should be renamed for your application
- Debug logging is available via the `--debug` flag
- Configuration precedence: flags > env vars > config file > defaults
- Logger instance is globally available as `cmd.Logger`
- Releases are automated via GoReleaser when tags are pushed to GitHub
- Binary builds have CGO disabled for maximum portability
