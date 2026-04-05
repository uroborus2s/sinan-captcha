package export

import (
	"encoding/json"
	"image"
	"image/png"
	"os"
	"path/filepath"
	"sort"
	"time"

	"sinan-captcha/generator/internal/config"
	"sinan-captcha/generator/internal/material"
)

type ObjectRecord struct {
	Order       int     `json:"order,omitempty"`
	Class       string  `json:"class"`
	ClassID     int     `json:"class_id"`
	BBox        [4]int  `json:"bbox"`
	Center      [2]int  `json:"center"`
	RotationDeg float64 `json:"rotation_deg"`
	Alpha       float64 `json:"alpha"`
	Scale       float64 `json:"scale"`
}

type TruthChecks struct {
	Consistency   string `json:"consistency"`
	Replay        string `json:"replay"`
	NegativeCheck string `json:"negative_check"`
}

type SampleRecord struct {
	SampleID     string         `json:"sample_id"`
	CaptchaType  string         `json:"captcha_type"`
	Mode         string         `json:"mode"`
	Backend      string         `json:"backend"`
	QueryImage   string         `json:"query_image,omitempty"`
	SceneImage   string         `json:"scene_image,omitempty"`
	MasterImage  string         `json:"master_image,omitempty"`
	TileImage    string         `json:"tile_image,omitempty"`
	QueryTargets []ObjectRecord `json:"query_targets,omitempty"`
	SceneTargets []ObjectRecord `json:"scene_targets,omitempty"`
	Distractors  []ObjectRecord `json:"distractors,omitempty"`
	TargetGap    *ObjectRecord  `json:"target_gap,omitempty"`
	TileBBox     *[4]int        `json:"tile_bbox,omitempty"`
	OffsetX      *int           `json:"offset_x,omitempty"`
	OffsetY      *int           `json:"offset_y,omitempty"`
	BackgroundID string         `json:"background_id"`
	StyleID      string         `json:"style_id"`
	LabelSource  string         `json:"label_source"`
	TruthChecks  *TruthChecks   `json:"truth_checks,omitempty"`
	SourceBatch  string         `json:"source_batch"`
	Seed         int64          `json:"seed"`
}

type BatchLayout struct {
	Mode      string            `json:"mode"`
	Backend   string            `json:"backend"`
	AssetDirs map[string]string `json:"asset_dirs"`
}

type BatchManifest struct {
	BatchID              string                     `json:"batch_id"`
	GeneratedAt          string                     `json:"generated_at"`
	Mode                 string                     `json:"mode"`
	Backend              string                     `json:"backend"`
	AssetDirs            map[string]string          `json:"asset_dirs"`
	ConfigPath           string                     `json:"config_path"`
	PlannedSampleCount   int                        `json:"planned_sample_count"`
	GeneratedSampleCount int                        `json:"generated_sample_count"`
	ConfigSnapshot       config.Config              `json:"config_snapshot"`
	MaterialSummary      material.ValidationSummary `json:"material_summary"`
}

type Result struct {
	BatchRoot      string            `json:"batch_root"`
	Mode           string            `json:"mode"`
	Backend        string            `json:"backend"`
	AssetDirs      map[string]string `json:"asset_dirs"`
	Labels         string            `json:"labels"`
	Manifest       string            `json:"manifest"`
	GeneratedCount int               `json:"generated_count"`
}

type BatchWriter struct {
	result   Result
	labels   *os.File
	manifest BatchManifest
}

func NewBatchWriter(outputRoot string, configPath string, cfg config.Config, summary material.ValidationSummary, layout BatchLayout) (*BatchWriter, error) {
	batchRoot := filepath.Join(outputRoot, cfg.Project.BatchID)
	result := Result{
		BatchRoot: batchRoot,
		Mode:      layout.Mode,
		Backend:   layout.Backend,
		AssetDirs: make(map[string]string, len(layout.AssetDirs)),
		Labels:    filepath.Join(batchRoot, "labels.jsonl"),
		Manifest:  filepath.Join(batchRoot, "manifest.json"),
	}

	for name, relativeDir := range layout.AssetDirs {
		absoluteDir := filepath.Join(batchRoot, filepath.FromSlash(relativeDir))
		if err := os.MkdirAll(absoluteDir, 0o755); err != nil {
			return nil, err
		}
		result.AssetDirs[name] = absoluteDir
	}
	labelsFile, err := os.Create(result.Labels)
	if err != nil {
		return nil, err
	}

	writer := &BatchWriter{
		result: result,
		labels: labelsFile,
		manifest: BatchManifest{
			BatchID:              cfg.Project.BatchID,
			GeneratedAt:          time.Now().UTC().Format(time.RFC3339),
			Mode:                 layout.Mode,
			Backend:              layout.Backend,
			AssetDirs:            cloneStringMap(layout.AssetDirs),
			ConfigPath:           configPath,
			PlannedSampleCount:   cfg.Project.SampleCount,
			GeneratedSampleCount: 0,
			ConfigSnapshot:       cfg,
			MaterialSummary:      summary,
		},
	}
	return writer, nil
}

func (w *BatchWriter) WriteSample(record SampleRecord, assets map[string]image.Image) error {
	for _, path := range sortedPaths(assets) {
		if err := w.writePNG(path, assets[path]); err != nil {
			return err
		}
	}
	content, err := json.Marshal(record)
	if err != nil {
		return err
	}
	if _, err := w.labels.Write(append(content, '\n')); err != nil {
		return err
	}
	w.manifest.GeneratedSampleCount++
	w.result.GeneratedCount++
	return nil
}

func (w *BatchWriter) Finalize() (Result, error) {
	if err := w.labels.Close(); err != nil {
		return w.result, err
	}

	content, err := json.MarshalIndent(w.manifest, "", "  ")
	if err != nil {
		return w.result, err
	}
	if err := os.WriteFile(w.result.Manifest, content, 0o644); err != nil {
		return w.result, err
	}
	return w.result, nil
}

func (w *BatchWriter) writePNG(relativePath string, imageData image.Image) error {
	absolutePath := filepath.Join(w.result.BatchRoot, filepath.FromSlash(relativePath))
	if err := os.MkdirAll(filepath.Dir(absolutePath), 0o755); err != nil {
		return err
	}
	file, err := os.Create(absolutePath)
	if err != nil {
		return err
	}
	defer file.Close()
	return png.Encode(file, imageData)
}

func cloneStringMap(values map[string]string) map[string]string {
	cloned := make(map[string]string, len(values))
	for key, value := range values {
		cloned[key] = value
	}
	return cloned
}

func sortedPaths(assets map[string]image.Image) []string {
	paths := make([]string, 0, len(assets))
	for path := range assets {
		paths = append(paths, path)
	}
	sort.Strings(paths)
	return paths
}
