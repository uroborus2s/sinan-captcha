package export

import (
	"encoding/json"
	"image"
	"image/png"
	"os"
	"path/filepath"
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

type SampleRecord struct {
	SampleID     string         `json:"sample_id"`
	CaptchaType  string         `json:"captcha_type"`
	QueryImage   string         `json:"query_image"`
	SceneImage   string         `json:"scene_image"`
	Targets      []ObjectRecord `json:"targets"`
	Distractors  []ObjectRecord `json:"distractors"`
	BackgroundID string         `json:"background_id"`
	StyleID      string         `json:"style_id"`
	LabelSource  string         `json:"label_source"`
	SourceBatch  string         `json:"source_batch"`
	Seed         int64          `json:"seed"`
}

type BatchManifest struct {
	BatchID              string                     `json:"batch_id"`
	GeneratedAt          string                     `json:"generated_at"`
	ConfigPath           string                     `json:"config_path"`
	PlannedSampleCount   int                        `json:"planned_sample_count"`
	GeneratedSampleCount int                        `json:"generated_sample_count"`
	ConfigSnapshot       config.Config              `json:"config_snapshot"`
	MaterialSummary      material.ValidationSummary `json:"material_summary"`
}

type Result struct {
	BatchRoot      string `json:"batch_root"`
	QueryDir       string `json:"query_dir"`
	SceneDir       string `json:"scene_dir"`
	Labels         string `json:"labels"`
	Manifest       string `json:"manifest"`
	GeneratedCount int    `json:"generated_count"`
}

type BatchWriter struct {
	result   Result
	labels   *os.File
	manifest BatchManifest
}

func NewBatchWriter(outputRoot string, configPath string, cfg config.Config, summary material.ValidationSummary) (*BatchWriter, error) {
	batchRoot := filepath.Join(outputRoot, cfg.Project.BatchID)
	result := Result{
		BatchRoot: batchRoot,
		QueryDir:  filepath.Join(batchRoot, "query"),
		SceneDir:  filepath.Join(batchRoot, "scene"),
		Labels:    filepath.Join(batchRoot, "labels.jsonl"),
		Manifest:  filepath.Join(batchRoot, "manifest.json"),
	}

	if err := os.MkdirAll(result.QueryDir, 0o755); err != nil {
		return nil, err
	}
	if err := os.MkdirAll(result.SceneDir, 0o755); err != nil {
		return nil, err
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
			ConfigPath:           configPath,
			PlannedSampleCount:   cfg.Project.SampleCount,
			GeneratedSampleCount: 0,
			ConfigSnapshot:       cfg,
			MaterialSummary:      summary,
		},
	}
	return writer, nil
}

func (w *BatchWriter) WriteSample(record SampleRecord, query image.Image, scene image.Image) error {
	if err := w.writePNG(record.QueryImage, query); err != nil {
		return err
	}
	if err := w.writePNG(record.SceneImage, scene); err != nil {
		return err
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
	file, err := os.Create(absolutePath)
	if err != nil {
		return err
	}
	defer file.Close()
	return png.Encode(file, imageData)
}
