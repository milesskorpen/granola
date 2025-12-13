// Package sync provides functionality for syncing export files with folder structure.
package sync

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/charmbracelet/log"
	"github.com/spf13/afero"
)

var invalidFileChars = regexp.MustCompile(`[<>:"/\\|?*\x00-\x1f]`)

// ExportDoc represents a document to be exported with its folder assignments.
type ExportDoc struct {
	ID        string
	Title     string
	UpdatedAt time.Time
	Content   string   // formatted content
	Folders   []string // folder names (empty = root)
}

// SyncStats contains statistics about the sync operation.
type SyncStats struct {
	Added    int
	Updated  int
	Moved    int
	Deleted  int
	Skipped  int
}

// Writer handles syncing documents to the filesystem with folder structure.
type Writer struct {
	fs        afero.Fs
	outputDir string
	logger    *log.Logger
}

// NewWriter creates a new sync writer.
func NewWriter(fs afero.Fs, outputDir string, logger *log.Logger) *Writer {
	return &Writer{
		fs:        fs,
		outputDir: outputDir,
		logger:    logger,
	}
}

// Sync synchronizes documents to the output directory with folder structure.
// It handles adding, updating, moving, and deleting files as needed.
func (w *Writer) Sync(docs []ExportDoc, allDocIDs map[string]bool) (SyncStats, error) {
	var stats SyncStats

	// Create output directory if it doesn't exist
	if err := w.fs.MkdirAll(w.outputDir, 0755); err != nil {
		return stats, fmt.Errorf("failed to create output directory: %w", err)
	}

	// Step 1: Scan existing files and build ID -> paths mapping
	existingFiles, err := w.scanExistingFiles()
	if err != nil {
		return stats, fmt.Errorf("failed to scan existing files: %w", err)
	}

	// Track which files we've processed (to detect orphans)
	processedIDs := make(map[string]bool)

	// Step 2: Process each document
	for _, doc := range docs {
		processedIDs[doc.ID] = true

		docStats, err := w.processDocument(doc, existingFiles)
		if err != nil {
			return stats, fmt.Errorf("failed to process document %s: %w", doc.ID, err)
		}

		stats.Added += docStats.Added
		stats.Updated += docStats.Updated
		stats.Moved += docStats.Moved
		stats.Deleted += docStats.Deleted
		stats.Skipped += docStats.Skipped
	}

	// Step 3: Delete orphaned files (files whose doc IDs are not in allDocIDs)
	for id, paths := range existingFiles {
		if !allDocIDs[id] {
			for _, path := range paths {
				w.logger.Debug("deleting orphan", "path", path, "id", id)
				if err := w.fs.Remove(path); err != nil {
					return stats, fmt.Errorf("failed to delete orphan file %s: %w", path, err)
				}
				stats.Deleted++
			}
		}
	}

	// Step 4: Clean up empty folders
	if err := w.cleanEmptyFolders(); err != nil {
		w.logger.Warn("failed to clean empty folders", "error", err)
	}

	return stats, nil
}

// scanExistingFiles walks the output directory and builds a map of doc ID -> file paths.
// It extracts the ID from filenames in the format: title_shortid.txt
func (w *Writer) scanExistingFiles() (map[string][]string, error) {
	existingFiles := make(map[string][]string)

	err := afero.Walk(w.fs, w.outputDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		if info.IsDir() {
			return nil
		}

		// Only process .txt files
		if !strings.HasSuffix(path, ".txt") {
			return nil
		}

		// Extract ID from filename (format: title_shortid.txt)
		id := extractIDFromFilename(filepath.Base(path))
		if id != "" {
			existingFiles[id] = append(existingFiles[id], path)
		}

		return nil
	})

	return existingFiles, err
}

// processDocument handles a single document: writes to appropriate folders,
// removes from folders it no longer belongs to.
func (w *Writer) processDocument(doc ExportDoc, existingFiles map[string][]string) (SyncStats, error) {
	var stats SyncStats

	filename := w.generateFilename(doc.Title, doc.ID)
	existingPaths := existingFiles[doc.ID]

	// Determine target paths based on folders
	targetPaths := w.getTargetPaths(doc.Folders, filename)

	// Build set of existing paths for quick lookup
	existingPathSet := make(map[string]bool)
	for _, p := range existingPaths {
		existingPathSet[p] = true
	}

	// Build set of target paths for quick lookup
	targetPathSet := make(map[string]bool)
	for _, p := range targetPaths {
		targetPathSet[p] = true
	}

	// Write to each target path
	for _, targetPath := range targetPaths {
		// Create folder if needed
		dir := filepath.Dir(targetPath)
		if err := w.fs.MkdirAll(dir, 0755); err != nil {
			return stats, fmt.Errorf("failed to create folder %s: %w", dir, err)
		}

		if existingPathSet[targetPath] {
			// File exists at this path - check if we need to update
			shouldWrite, err := w.shouldUpdateFile(targetPath, doc.UpdatedAt)
			if err != nil {
				return stats, err
			}

			if shouldWrite {
				if err := afero.WriteFile(w.fs, targetPath, []byte(doc.Content), 0644); err != nil {
					return stats, fmt.Errorf("failed to write file %s: %w", targetPath, err)
				}
				w.logger.Debug("updated", "path", targetPath)
				stats.Updated++
			} else {
				stats.Skipped++
			}
		} else {
			// New path - write the file
			if err := afero.WriteFile(w.fs, targetPath, []byte(doc.Content), 0644); err != nil {
				return stats, fmt.Errorf("failed to write file %s: %w", targetPath, err)
			}
			w.logger.Debug("added", "path", targetPath)
			stats.Added++
		}
	}

	// Remove files from folders they no longer belong to
	for _, existingPath := range existingPaths {
		if !targetPathSet[existingPath] {
			w.logger.Debug("removing from old folder", "path", existingPath)
			if err := w.fs.Remove(existingPath); err != nil {
				return stats, fmt.Errorf("failed to remove old file %s: %w", existingPath, err)
			}
			stats.Moved++
		}
	}

	// Clear processed paths from existingFiles to avoid double-deletion
	delete(existingFiles, doc.ID)

	return stats, nil
}

// getTargetPaths returns the full paths where the document should be written.
func (w *Writer) getTargetPaths(folders []string, filename string) []string {
	if len(folders) == 0 {
		// No folders - place in root
		return []string{filepath.Join(w.outputDir, filename)}
	}

	paths := make([]string, len(folders))
	for i, folder := range folders {
		sanitizedFolder := sanitizeFolderName(folder)
		paths[i] = filepath.Join(w.outputDir, sanitizedFolder, filename)
	}
	return paths
}

// generateFilename creates a filename from title and ID.
// Format: {sanitized_title}_{short_id}.txt
func (w *Writer) generateFilename(title, id string) string {
	name := strings.TrimSpace(title)
	if name == "" {
		name = "untitled"
	}

	// Sanitize the title
	name = invalidFileChars.ReplaceAllString(name, "_")
	name = regexp.MustCompile(`_+`).ReplaceAllString(name, "_")
	name = strings.Trim(name, "_")

	if name == "" {
		name = "untitled"
	}

	// Limit title length to leave room for ID
	if len(name) > 80 {
		name = name[:80]
	}

	// Use first 8 chars of ID
	shortID := id
	if len(id) >= 8 {
		shortID = id[:8]
	}

	return fmt.Sprintf("%s_%s.txt", name, shortID)
}

// extractIDFromFilename extracts the document ID from a filename.
// Expected format: title_shortid.txt
func extractIDFromFilename(filename string) string {
	// Remove .txt extension
	name := strings.TrimSuffix(filename, ".txt")

	// Find the last underscore
	lastUnderscore := strings.LastIndex(name, "_")
	if lastUnderscore == -1 || lastUnderscore == len(name)-1 {
		return ""
	}

	// Extract the ID portion (should be 8 chars for short ID)
	id := name[lastUnderscore+1:]
	if len(id) >= 8 {
		return id[:8] // Return just the short ID for matching
	}

	return ""
}

// shouldUpdateFile checks if a file should be updated based on timestamps.
func (w *Writer) shouldUpdateFile(filePath string, docUpdatedAt time.Time) (bool, error) {
	info, err := w.fs.Stat(filePath)
	if err != nil {
		// If we can't stat, assume we should write
		return true, nil
	}

	return docUpdatedAt.After(info.ModTime()), nil
}

// sanitizeFolderName sanitizes a folder name for use as a directory name.
func sanitizeFolderName(name string) string {
	name = strings.TrimSpace(name)
	name = invalidFileChars.ReplaceAllString(name, "_")
	name = regexp.MustCompile(`_+`).ReplaceAllString(name, "_")
	name = strings.Trim(name, "_")

	if name == "" {
		name = "unnamed_folder"
	}

	// Limit length
	if len(name) > 100 {
		name = name[:100]
	}

	return name
}

// cleanEmptyFolders removes empty directories from the output directory.
func (w *Writer) cleanEmptyFolders() error {
	return afero.Walk(w.fs, w.outputDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		if !info.IsDir() || path == w.outputDir {
			return nil
		}

		// Check if directory is empty
		entries, err := afero.ReadDir(w.fs, path)
		if err != nil {
			return nil // Ignore errors
		}

		if len(entries) == 0 {
			w.logger.Debug("removing empty folder", "path", path)
			_ = w.fs.Remove(path)
		}

		return nil
	})
}
