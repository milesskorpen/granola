package cmd

import (
	"errors"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/charmbracelet/log"
	"github.com/spf13/afero"
	"github.com/spf13/cobra"
	"github.com/spf13/viper"
	"github.com/theantichris/granola/internal/api"
	"github.com/theantichris/granola/internal/cache"
	"github.com/theantichris/granola/internal/formatter"
	"github.com/theantichris/granola/internal/prosemirror"
	"github.com/theantichris/granola/internal/sync"
)

var (
	ErrExportCmdInit = errors.New("failed to initialize the export command")
	ErrExportFailed  = errors.New("failed to export documents")
)

func defaultExportOutput() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return "./export"
	}

	return filepath.Join(home, "My Drive", "z. Granola Notes")
}

// NewExportCmd creates a new export command that combines notes and transcripts.
func NewExportCmd(logger *log.Logger) *cobra.Command {
	cmd := &cobra.Command{
		Use:   "export",
		Short: "Export combined notes and transcripts with folder structure.",
		Long: `Export Granola notes and transcripts to a single directory with folder structure.

This command fetches notes from the Granola API, reads transcripts from the local cache,
and combines them into .txt files organized by Granola folder structure.

Documents in multiple folders will be duplicated into each folder.
Documents not in any folder will be placed in the root directory.
Files are synced incrementally - only updated when the source changes.
Deleted documents are removed from the output directory.`,
		PreRunE: func(cmd *cobra.Command, args []string) error {
			if err := viper.BindPFlag("export_timeout", cmd.Flags().Lookup("timeout")); err != nil {
				return fmt.Errorf("%w: %s", ErrExportCmdInit, err)
			}
			if err := viper.BindPFlag("export_output", cmd.Flags().Lookup("output")); err != nil {
				return fmt.Errorf("%w: %s", ErrExportCmdInit, err)
			}
			if err := viper.BindPFlag("export_cache", cmd.Flags().Lookup("cache")); err != nil {
				return fmt.Errorf("%w: %s", ErrExportCmdInit, err)
			}

			return nil
		},
		RunE: func(cmd *cobra.Command, args []string) error {
			return runExport(logger)
		},
	}

	var timeout time.Duration
	cmd.Flags().DurationVar(&timeout, "timeout", 2*time.Minute, "HTTP timeout for API requests")

	var output string
	cmd.Flags().StringVar(&output, "output", defaultExportOutput(), "Output directory for exported files")

	var cacheFile string
	cmd.Flags().StringVar(&cacheFile, "cache", cache.GetDefaultCachePath(), "Path to Granola cache file")

	return cmd
}

// runExport performs the combined export of notes and transcripts.
func runExport(logger *log.Logger) error {
	// 1. Load supabase configuration
	supabasePath := viper.GetString("supabase")
	supabasePath, err := resolvePath(supabasePath)
	if err != nil {
		return fmt.Errorf("%w: %s", ErrExportFailed, err)
	}

	if strings.TrimSpace(supabasePath) == "" {
		return fmt.Errorf("%w: set the path to supabase.json via --supabase flag, config file, or SUPABASE_FILE env", ErrSupabaseEmpty)
	}

	logger.Info("Reading supabase configuration", "file", supabasePath)
	supabaseContent, err := afero.ReadFile(appFS, supabasePath)
	if err != nil {
		return fmt.Errorf("%w: failed to read supabase.json: %s", ErrExportFailed, err)
	}

	// 2. Fetch documents from API
	timeout := viper.GetDuration("export_timeout")
	if timeout == 0 {
		timeout = 2 * time.Minute
	}

	fmt.Println("Fetching documents from Granola API...")
	logger.Info("Fetching documents from Granola API", "timeout", timeout)
	httpClient := http.Client{Timeout: timeout}
	apiDocs, err := api.GetDocuments("https://api.granola.ai/v2/get-documents", supabaseContent, &httpClient)
	if err != nil {
		return fmt.Errorf("%w: %s", ErrExportFailed, err)
	}

	logger.Info("Retrieved documents from API", "count", len(apiDocs))

	// 3. Read cache for transcripts and folders
	cachePath := viper.GetString("export_cache")
	if cachePath == "" {
		cachePath = cache.GetDefaultCachePath()
	}
	cachePath, err = resolvePath(cachePath)
	if err != nil {
		return fmt.Errorf("%w: %s", ErrExportFailed, err)
	}

	logger.Info("Reading cache file", "file", cachePath)
	cacheData, err := cache.ReadCache(cachePath)
	if err != nil {
		return fmt.Errorf("%w: failed to read cache: %s", ErrExportFailed, err)
	}

	logger.Info("Loaded cache data",
		"transcripts", len(cacheData.Transcripts),
		"folders", len(cacheData.Folders))

	// 4. Build export documents by merging API docs with cache data
	allDocIDs := make(map[string]bool)
	exportDocs := make([]sync.ExportDoc, 0, len(apiDocs))

	for _, apiDoc := range apiDocs {
		allDocIDs[apiDoc.ID] = true

		// Get folder names for this document
		folders := cacheData.GetFolderNames(apiDoc.ID)

		// Get transcript segments
		segments := cacheData.Transcripts[apiDoc.ID]

		// Get notes content (convert ProseMirror to plain text)
		notesContent := getNotesContent(apiDoc)

		// Format the combined content
		content := formatter.FormatCombined(
			apiDoc.Title,
			apiDoc.ID,
			apiDoc.CreatedAt,
			apiDoc.UpdatedAt,
			notesContent,
			segments,
			folders,
		)

		// Parse updated_at timestamp
		updatedAt, err := time.Parse(time.RFC3339, apiDoc.UpdatedAt)
		if err != nil {
			updatedAt = time.Now() // Default to now if parsing fails
		}

		exportDocs = append(exportDocs, sync.ExportDoc{
			ID:        apiDoc.ID,
			Title:     apiDoc.Title,
			UpdatedAt: updatedAt,
			Content:   content,
			Folders:   folders,
		})
	}

	// 5. Resolve output directory
	outputDir := viper.GetString("export_output")
	if outputDir == "" {
		outputDir = defaultExportOutput()
	}
	outputDir, err = resolvePath(outputDir)
	if err != nil {
		return fmt.Errorf("%w: %s", ErrExportFailed, err)
	}

	fmt.Printf("Syncing %d documents to %s...\n", len(exportDocs), outputDir)
	logger.Info("Starting sync", "output", outputDir, "documents", len(exportDocs))

	// 6. Sync to filesystem
	syncWriter := sync.NewWriter(appFS, outputDir, logger)
	stats, err := syncWriter.Sync(exportDocs, allDocIDs)
	if err != nil {
		return fmt.Errorf("%w: %s", ErrExportFailed, err)
	}

	// 7. Print results
	fmt.Printf("Export completed: %d added, %d updated, %d moved, %d deleted, %d skipped\n",
		stats.Added, stats.Updated, stats.Moved, stats.Deleted, stats.Skipped)
	logger.Info("Export completed",
		"added", stats.Added,
		"updated", stats.Updated,
		"moved", stats.Moved,
		"deleted", stats.Deleted,
		"skipped", stats.Skipped)

	return nil
}

// getNotesContent extracts plain text notes from an API document.
func getNotesContent(doc api.Document) string {
	// Try NotesPlain first (already plain text)
	if doc.NotesPlain != "" {
		return doc.NotesPlain
	}

	// Try Notes (ProseMirror)
	if doc.Notes != nil {
		return prosemirror.ConvertToPlainText(doc.Notes)
	}

	// Try LastViewedPanel.Content (ProseMirror)
	if doc.LastViewedPanel != nil && doc.LastViewedPanel.Content != nil {
		return prosemirror.ConvertToPlainText(doc.LastViewedPanel.Content)
	}

	// Try LastViewedPanel.OriginalContent (HTML - return as-is for now)
	if doc.LastViewedPanel != nil && doc.LastViewedPanel.OriginalContent != "" {
		return doc.LastViewedPanel.OriginalContent
	}

	// Fallback to Content field
	return doc.Content
}
