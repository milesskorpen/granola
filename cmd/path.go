package cmd

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// resolvePath expands environment variables and leading tildes in user-provided paths.
func resolvePath(input string) (string, error) {
	trimmed := strings.TrimSpace(input)
	if trimmed == "" {
		return "", nil
	}

	expanded := os.ExpandEnv(trimmed)

	if expanded == "~" || strings.HasPrefix(expanded, "~/") || strings.HasPrefix(expanded, "~\\") {
		home, err := os.UserHomeDir()
		if err != nil {
			return "", fmt.Errorf("failed to resolve home directory: %w", err)
		}

		remainder := strings.TrimPrefix(expanded, "~")
		remainder = strings.TrimLeft(remainder, `/\`)
		if remainder == "" {
			return filepath.Clean(home), nil
		}

		return filepath.Clean(filepath.Join(home, remainder)), nil
	}

	return filepath.Clean(expanded), nil
}
