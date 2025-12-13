// Package formatter provides functionality for formatting combined notes and transcripts.
package formatter

import (
	"fmt"
	"strings"
	"time"

	"github.com/theantichris/granola/internal/cache"
)

// FormatCombined formats notes and transcript into a single text file.
func FormatCombined(title, id, createdAt, updatedAt, notesContent string, segments []cache.TranscriptSegment, folders []string) string {
	var builder strings.Builder

	// Header
	builder.WriteString(strings.Repeat("=", 80))
	builder.WriteString("\n")

	if title != "" {
		builder.WriteString(title)
		builder.WriteString("\n")
	}

	builder.WriteString("ID: ")
	builder.WriteString(id)
	builder.WriteString("\n")

	if createdAt != "" {
		builder.WriteString("Created: ")
		builder.WriteString(createdAt)
		builder.WriteString("\n")
	}

	if updatedAt != "" {
		builder.WriteString("Updated: ")
		builder.WriteString(updatedAt)
		builder.WriteString("\n")
	}

	if len(folders) > 0 {
		builder.WriteString("Folders: ")
		builder.WriteString(strings.Join(folders, ", "))
		builder.WriteString("\n")
	}

	builder.WriteString(strings.Repeat("=", 80))
	builder.WriteString("\n")

	// Notes section
	builder.WriteString("\n## Notes\n\n")
	if strings.TrimSpace(notesContent) != "" {
		builder.WriteString(notesContent)
		builder.WriteString("\n")
	} else {
		builder.WriteString("(No notes)\n")
	}

	// Transcript section
	builder.WriteString("\n")
	builder.WriteString(strings.Repeat("=", 80))
	builder.WriteString("\n")
	builder.WriteString("\n## Transcript\n\n")

	if len(segments) > 0 {
		for _, segment := range segments {
			startTime := parseTimestamp(segment.StartTimestamp)
			speaker := "System"
			if segment.Source == "microphone" {
				speaker = "You"
			}
			builder.WriteString(fmt.Sprintf("[%s] %s: %s\n", startTime, speaker, segment.Text))
		}
	} else {
		builder.WriteString("(No transcript available)\n")
	}

	return builder.String()
}

// parseTimestamp converts ISO 8601 timestamp to HH:MM:SS format.
func parseTimestamp(timestamp string) string {
	t, err := time.Parse(time.RFC3339, timestamp)
	if err != nil {
		return timestamp
	}
	return t.Format("15:04:05")
}
