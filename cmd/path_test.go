package cmd

import (
	"os"
	"path/filepath"
	"testing"
)

func TestResolvePath(t *testing.T) {
	home := filepath.Join(string(os.PathSeparator), "home", "tester")
	t.Setenv("HOME", home)
	t.Setenv("USERPROFILE", home)

	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{
			name:     "empty path",
			input:    "",
			expected: "",
		},
		{
			name:     "tilde path",
			input:    "~/My Drive/z. Granola Notes/Markdown",
			expected: filepath.Join(home, "My Drive", "z. Granola Notes", "Markdown"),
		},
		{
			name:     "env variable",
			input:    "$HOME/Documents",
			expected: filepath.Join(home, "Documents"),
		},
		{
			name:     "plain relative",
			input:    "./notes",
			expected: filepath.Clean("./notes"),
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			actual, err := resolvePath(tt.input)
			if err != nil {
				t.Fatalf("resolvePath returned error: %v", err)
			}

			if actual != tt.expected {
				t.Fatalf("expected %q, got %q", tt.expected, actual)
			}
		})
	}
}
