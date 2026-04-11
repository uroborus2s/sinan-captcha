package qa

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"image"
	_ "image/jpeg"
	_ "image/png"
	"os"
	"path/filepath"
	"strings"

	"sinan-captcha/generator/internal/backend"
	"sinan-captcha/generator/internal/export"
	"sinan-captcha/generator/internal/truth"
)

type Summary struct {
	BatchRoot            string         `json:"batch_root"`
	Mode                 string         `json:"mode,omitempty"`
	Backend              string         `json:"backend,omitempty"`
	AssetCounts          map[string]int `json:"asset_counts"`
	LabelLineCount       int            `json:"label_line_count"`
	ValidatedSampleCount int            `json:"validated_sample_count"`
	LabelsExists         bool           `json:"labels_exists"`
}

func InspectBatch(batchRoot string) (Summary, error) {
	summary := Summary{
		BatchRoot:   batchRoot,
		AssetCounts: map[string]int{},
	}

	labelsPath := filepath.Join(batchRoot, "labels.jsonl")
	manifestPath := filepath.Join(batchRoot, "manifest.json")

	manifest, err := readManifest(manifestPath)
	if err != nil {
		return summary, err
	}
	summary.Mode = manifest.Mode
	summary.Backend = manifest.Backend
	if _, err := os.Stat(labelsPath); err != nil {
		return summary, err
	}

	expectedCount := -1
	for name, relativeDir := range manifest.AssetDirs {
		count, err := countFiles(filepath.Join(batchRoot, filepath.FromSlash(relativeDir)))
		if err != nil {
			return summary, err
		}
		summary.AssetCounts[name] = count
		if expectedCount == -1 {
			expectedCount = count
			continue
		}
		if count != expectedCount {
			return summary, errors.New("asset directory file counts do not match")
		}
	}
	records, err := readRecords(labelsPath)
	if err != nil {
		return summary, err
	}
	summary.LabelLineCount = len(records)
	summary.LabelsExists = true

	if expectedCount == -1 {
		return summary, errors.New("manifest has no asset directories")
	}
	if expectedCount != summary.LabelLineCount {
		return summary, errors.New("image counts and labels.jsonl line count do not match")
	}
	if err := validateRecords(batchRoot, manifest, records, &summary); err != nil {
		return summary, err
	}

	return summary, nil
}

func countFiles(dir string) (int, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return 0, err
	}

	count := 0
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		ext := strings.ToLower(filepath.Ext(entry.Name()))
		if ext == ".png" || ext == ".jpg" || ext == ".jpeg" || ext == ".jsonl" {
			count++
		}
	}
	return count, nil
}

func readManifest(path string) (export.BatchManifest, error) {
	var manifest export.BatchManifest
	content, err := os.ReadFile(path)
	if err != nil {
		return manifest, err
	}
	err = json.Unmarshal(content, &manifest)
	return manifest, err
}

func readRecords(path string) ([]export.SampleRecord, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	records := []export.SampleRecord{}
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var record export.SampleRecord
		if err := json.Unmarshal([]byte(line), &record); err != nil {
			return nil, fmt.Errorf("invalid labels.jsonl row: %w", err)
		}
		records = append(records, record)
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	return records, nil
}

func validateRecords(batchRoot string, manifest export.BatchManifest, records []export.SampleRecord, summary *Summary) error {
	mode, err := backend.ParseMode(manifest.Mode)
	if err != nil {
		return err
	}
	backendKind, err := backend.ParseBackend(manifest.Backend)
	if err != nil {
		return err
	}
	spec := backend.Spec{Mode: mode, Backend: backendKind}
	seenSampleIDs := map[string]struct{}{}

	for index, record := range records {
		if _, exists := seenSampleIDs[record.SampleID]; exists {
			return fmt.Errorf("duplicate sample_id found in labels.jsonl: %s", record.SampleID)
		}
		seenSampleIDs[record.SampleID] = struct{}{}
		if err := validateRecord(batchRoot, manifest, spec, record); err != nil {
			return fmt.Errorf("sample %d (%s): %w", index+1, record.SampleID, err)
		}
		summary.ValidatedSampleCount++
	}
	return nil
}

func validateRecord(batchRoot string, manifest export.BatchManifest, spec backend.Spec, record export.SampleRecord) error {
	if record.TruthChecks == nil {
		return fmt.Errorf("truth_checks are required for qa")
	}
	if record.TruthChecks.Consistency != "passed" || record.TruthChecks.Replay != "passed" || record.TruthChecks.NegativeCheck != "passed" {
		return fmt.Errorf("truth_checks must all be passed")
	}
	if record.SourceBatch != manifest.BatchID {
		return fmt.Errorf("source_batch %q does not match manifest batch %q", record.SourceBatch, manifest.BatchID)
	}
	if err := truth.CheckConsistency(record, spec, manifest.ConfigSnapshot.Canvas); err != nil {
		return err
	}
	if err := truth.CheckNegative(record, spec, manifest.ConfigSnapshot.Canvas); err != nil {
		return err
	}
	switch spec.Mode {
	case backend.ModeClick:
		if err := validateAssetFile(batchRoot, manifest.AssetDirs["query"], record.QueryImage, manifest.ConfigSnapshot.Canvas.QueryWidth, manifest.ConfigSnapshot.Canvas.QueryHeight); err != nil {
			return fmt.Errorf("query_image: %w", err)
		}
		if err := validateAssetFile(batchRoot, manifest.AssetDirs["scene"], record.SceneImage, manifest.ConfigSnapshot.Canvas.SceneWidth, manifest.ConfigSnapshot.Canvas.SceneHeight); err != nil {
			return fmt.Errorf("scene_image: %w", err)
		}
	case backend.ModeSlide:
		if err := validateAssetFile(batchRoot, manifest.AssetDirs["master"], record.MasterImage, manifest.ConfigSnapshot.Canvas.SceneWidth, manifest.ConfigSnapshot.Canvas.SceneHeight); err != nil {
			return fmt.Errorf("master_image: %w", err)
		}
		if record.TileBBox == nil {
			return fmt.Errorf("tile_bbox is required")
		}
		tileWidth := record.TileBBox[2] - record.TileBBox[0]
		tileHeight := record.TileBBox[3] - record.TileBBox[1]
		if err := validateAssetFile(batchRoot, manifest.AssetDirs["tile"], record.TileImage, tileWidth, tileHeight); err != nil {
			return fmt.Errorf("tile_image: %w", err)
		}
	default:
		return fmt.Errorf("unsupported mode: %s", spec.Mode)
	}
	return nil
}

func validateAssetFile(batchRoot string, expectedDir string, relativePath string, width int, height int) error {
	if relativePath == "" {
		return fmt.Errorf("relative asset path is required")
	}
	if expectedDir == "" {
		return fmt.Errorf("expected asset dir is not configured")
	}
	cleanPath := filepath.ToSlash(filepath.Clean(relativePath))
	expectedPrefix := strings.TrimSuffix(filepath.ToSlash(expectedDir), "/") + "/"
	if !strings.HasPrefix(cleanPath, expectedPrefix) {
		return fmt.Errorf("asset path %q does not stay under %q", cleanPath, expectedDir)
	}
	absolutePath := filepath.Join(batchRoot, filepath.FromSlash(cleanPath))
	cfg, err := readImageConfig(absolutePath)
	if err != nil {
		return err
	}
	if width > 0 && cfg.Width != width {
		return fmt.Errorf("unexpected width: got %d want %d", cfg.Width, width)
	}
	if height > 0 && cfg.Height != height {
		return fmt.Errorf("unexpected height: got %d want %d", cfg.Height, height)
	}
	return nil
}

func readImageConfig(path string) (image.Config, error) {
	var cfg image.Config
	file, err := os.Open(path)
	if err != nil {
		return cfg, err
	}
	defer file.Close()
	cfg, _, err = image.DecodeConfig(file)
	return cfg, err
}
