# go-template

[![Go Version](https://img.shields.io/github/go-mod/go-version/theantichris/go-template)](https://go.dev/)
[![Go Reference](https://pkg.go.dev/badge/github.com/theantichris/go-template.svg)](https://pkg.go.dev/github.com/theantichris/go-template)
[![Go Report Card](https://goreportcard.com/badge/github.com/theantichris/go-template)](https://goreportcard.com/report/github.com/theantichris/go-template)
[![Go](https://github.com/theantichris/go-template/actions/workflows/go.yml/badge.svg)](https://github.com/theantichris/go-template/actions/workflows/go.yml)
[![Markdown Lint](https://github.com/theantichris/go-template/actions/workflows/markdown.yml/badge.svg)](https://github.com/theantichris/go-template/actions/workflows/markdown.yml)
[![License](https://img.shields.io/github/license/theantichris/go-template)](LICENSE)
[![Release](https://img.shields.io/github/v/release/theantichris/go-template)](https://github.com/theantichris/go-template/releases)

A modern Go template for building CLI and TUI applications with best
practices and powerful tools.

## Features

- 🎯 **Cobra Command Framework** - Build powerful CLI applications with ease
- ⚙️ **Viper Configuration** - Flexible configuration management with TOML,
  environment variables, and flags
- 📝 **Structured Logging** - Beautiful logging with Charmbracelet's log package
- 🎨 **Charmbracelet Tools** - Modern terminal UI capabilities
- 🔧 **Environment Support** - `.env` file support for local development
- 📦 **Modular Structure** - Clean, organized project layout
- 🚀 **Automated Releases** - GoReleaser integration for multi-platform builds

## Installation

### From Release

Download the latest release from the [releases page](https://github.com/theantichris/go-template/releases).

### From Source

```bash
git clone https://github.com/theantichris/go-template.git
cd go-template
go build -o go-template
```

### Using Go Install

```bash
go install github.com/theantichris/go-template@latest
```

## Quick Start

1. **Clone and rename the template:**

   ```bash
   git clone https://github.com/theantichris/go-template.git my-app
   cd my-app
   rm -rf .git
   git init
   ```

2. **Update module name:**

   ```bash
   go mod edit -module github.com/yourusername/my-app
   go mod tidy
   ```

3. **Customize the application:**
   - Edit `cmd/root.go` to change the command name and description
   - Add new commands in the `cmd/` directory
   - Update configuration options as needed

## Usage

### Basic Commands

```bash
# Run the application
go run main.go

# Build the application
go build

# Run with debug logging
./go-template --debug

# Use custom config file
./go-template --config /path/to/config.toml

# Display help
./go-template --help
```

### Configuration

The application supports multiple configuration sources with the following
precedence:

1. Command-line flags
2. Environment variables
3. Configuration file
4. Default values

#### Configuration File

Create a `.config.toml` file in your home directory or current directory:

```toml
debug = true
envVar = "some-value"
```

#### Environment Variables

Create a `.env` file for local development:

```bash
DEBUG=true
ENV_VAR=some-value
```

Or set environment variables directly:

```bash
export DEBUG=true
export ENV_VAR=some-value
```

## Project Structure

```text
go-template/
├── cmd/
│   └── root.go         # Root command and configuration
├── main.go             # Application entry point
├── go.mod              # Go module dependencies
├── go.sum              # Dependency checksums
├── README.md           # Project documentation
├── CLAUDE.md           # Claude AI assistant guide
├── SPEC.md             # Project specification template
└── LICENSE             # License file
```

## Development

### Prerequisites

- Go 1.23.1 or higher
- Git

### Building

```bash
# Build for current platform
go build

# Build for specific platforms
GOOS=linux GOARCH=amd64 go build -o go-template-linux
GOOS=darwin GOARCH=amd64 go build -o go-template-darwin
GOOS=windows GOARCH=amd64 go build -o go-template.exe
```

### Releasing

This project uses [GoReleaser](https://goreleaser.com/) for automated releases.

```bash
# Create a new tag
git tag v0.1.0
git push origin v0.1.0

# For local testing (requires GoReleaser installed)
goreleaser release --snapshot --clean
```

Releases are automatically built and published when a new tag is pushed to
GitHub.

### Testing

```bash
# Run all tests
go test ./...

# Run tests with coverage
go test -cover ./...

# Run tests with verbose output
go test -v ./...
```

### Linting

```bash
# Install Go linter
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest

# Run Go linter
golangci-lint run

# Install Markdown linter
brew install markdownlint-cli2

# Run Markdown linter
markdownlint-cli2 "**/*.md"
```

## Dependencies

- [Cobra](https://github.com/spf13/cobra) - CLI framework
- [Viper](https://github.com/spf13/viper) - Configuration management
- [Charmbracelet Log](https://github.com/charmbracelet/log) - Structured logging
- [Charmbracelet Fang](https://github.com/charmbracelet/fang) - Enhanced
  command execution
- [Godotenv](https://github.com/joho/godotenv) - .env file support

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE)
file for details.

## Acknowledgments

- The Go team for the amazing language and tools
- The Cobra and Viper teams for excellent CLI libraries
- The Charmbracelet team for beautiful terminal tools

## Support

For issues, questions, or suggestions, please [open an issue](https://github.com/theantichris/go-template/issues).

---

Built with ❤️ using Go
