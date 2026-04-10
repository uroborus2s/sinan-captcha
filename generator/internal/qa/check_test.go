package qa

import (
	"encoding/json"
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"testing"

	"sinan-captcha/generator/internal/config"
	"sinan-captcha/generator/internal/export"
	"sinan-captcha/generator/internal/material"
)

func TestInspectBatchValidatesClickBatch(t *testing.T) {
	batchRoot := t.TempDir()
	writeTestPNG(t, filepath.Join(batchRoot, "query", "g1_000001.png"), 120, 36)
	writeTestPNG(t, filepath.Join(batchRoot, "scene", "g1_000001.png"), 300, 150)
	writeManifest(t, batchRoot, export.BatchManifest{
		BatchID:         "batch_0001",
		Mode:            "click",
		Backend:         "native",
		AssetDirs:       map[string]string{"query": "query", "scene": "scene"},
		ConfigSnapshot:  config.Config{Canvas: config.CanvasConfig{SceneWidth: 300, SceneHeight: 150, QueryWidth: 120, QueryHeight: 36}},
		MaterialSummary: material.ValidationSummary{SchemaVersion: 3, Group1TemplateCount: 2, Group1VariantCount: 2, Group2ShapeCount: 2},
	})
	writeLabels(t, filepath.Join(batchRoot, "labels.jsonl"), []export.SampleRecord{
		{
			SampleID:    "g1_000001",
			CaptchaType: "group1_multi_icon_match",
			Mode:        "click",
			Backend:     "native",
			QueryImage:  "query/g1_000001.png",
			SceneImage:  "scene/g1_000001.png",
			QueryTargets: []export.ObjectRecord{
				{Order: 1, Class: "icon_house", ClassID: 0, BBox: [4]int{10, 8, 34, 30}, Center: [2]int{22, 19}},
			},
			SceneTargets: []export.ObjectRecord{
				{Order: 1, Class: "icon_house", ClassID: 0, BBox: [4]int{10, 10, 40, 40}, Center: [2]int{25, 25}},
			},
			Distractors: []export.ObjectRecord{
				{Class: "icon_leaf", ClassID: 1, BBox: [4]int{80, 20, 110, 50}, Center: [2]int{95, 35}},
			},
			LabelSource: "gold",
			TruthChecks: &export.TruthChecks{Consistency: "passed", Replay: "passed", NegativeCheck: "passed"},
			SourceBatch: "batch_0001",
			Seed:        1,
		},
	})

	summary, err := InspectBatch(batchRoot)
	if err != nil {
		t.Fatalf("expected click batch qa to pass: %v", err)
	}
	if summary.ValidatedSampleCount != 1 {
		t.Fatalf("expected one validated sample, got %d", summary.ValidatedSampleCount)
	}
	if summary.AssetCounts["query"] != 1 || summary.AssetCounts["scene"] != 1 {
		t.Fatalf("unexpected asset counts: %#v", summary.AssetCounts)
	}
}

func TestInspectBatchValidatesSlideBatch(t *testing.T) {
	batchRoot := t.TempDir()
	writeTestPNG(t, filepath.Join(batchRoot, "master", "g2_000001.png"), 300, 150)
	writeTestPNG(t, filepath.Join(batchRoot, "tile", "g2_000001.png"), 52, 52)
	offsetX := 148
	offsetY := 0
	tileBBox := [4]int{0, 56, 52, 108}
	writeManifest(t, batchRoot, export.BatchManifest{
		BatchID:   "batch_0002",
		Mode:      "slide",
		Backend:   "native",
		AssetDirs: map[string]string{"master": "master", "tile": "tile"},
		ConfigSnapshot: config.Config{
			Canvas: config.CanvasConfig{SceneWidth: 300, SceneHeight: 150, QueryWidth: 120, QueryHeight: 36},
		},
	})
	writeLabels(t, filepath.Join(batchRoot, "labels.jsonl"), []export.SampleRecord{
		{
			SampleID:    "g2_000001",
			CaptchaType: "group2_slider_gap_locate",
			Mode:        "slide",
			Backend:     "native",
			MasterImage: "master/g2_000001.png",
			TileImage:   "tile/g2_000001.png",
			TargetGap: &export.ObjectRecord{
				Class:   "slider_gap",
				ClassID: 0,
				BBox:    [4]int{148, 56, 200, 108},
				Center:  [2]int{174, 82},
			},
			TileBBox:    &tileBBox,
			OffsetX:     &offsetX,
			OffsetY:     &offsetY,
			LabelSource: "gold",
			TruthChecks: &export.TruthChecks{Consistency: "passed", Replay: "passed", NegativeCheck: "passed"},
			SourceBatch: "batch_0002",
			Seed:        2,
		},
	})

	summary, err := InspectBatch(batchRoot)
	if err != nil {
		t.Fatalf("expected slide batch qa to pass: %v", err)
	}
	if summary.ValidatedSampleCount != 1 {
		t.Fatalf("expected one validated sample, got %d", summary.ValidatedSampleCount)
	}
	if summary.AssetCounts["master"] != 1 || summary.AssetCounts["tile"] != 1 {
		t.Fatalf("unexpected asset counts: %#v", summary.AssetCounts)
	}
}

func TestInspectBatchRejectsMissingTruthChecks(t *testing.T) {
	batchRoot := t.TempDir()
	writeTestPNG(t, filepath.Join(batchRoot, "query", "g1_000001.png"), 120, 36)
	writeTestPNG(t, filepath.Join(batchRoot, "scene", "g1_000001.png"), 300, 150)
	writeManifest(t, batchRoot, export.BatchManifest{
		BatchID:   "batch_0003",
		Mode:      "click",
		Backend:   "native",
		AssetDirs: map[string]string{"query": "query", "scene": "scene"},
		ConfigSnapshot: config.Config{
			Canvas: config.CanvasConfig{SceneWidth: 300, SceneHeight: 150, QueryWidth: 120, QueryHeight: 36},
		},
	})
	writeLabels(t, filepath.Join(batchRoot, "labels.jsonl"), []export.SampleRecord{
		{
			SampleID:    "g1_000001",
			CaptchaType: "group1_multi_icon_match",
			Mode:        "click",
			Backend:     "native",
			QueryImage:  "query/g1_000001.png",
			SceneImage:  "scene/g1_000001.png",
			QueryTargets: []export.ObjectRecord{
				{Order: 1, Class: "icon_house", ClassID: 0, BBox: [4]int{10, 8, 34, 30}, Center: [2]int{22, 19}},
			},
			SceneTargets: []export.ObjectRecord{
				{Order: 1, Class: "icon_house", ClassID: 0, BBox: [4]int{10, 10, 40, 40}, Center: [2]int{25, 25}},
			},
			LabelSource: "gold",
			SourceBatch: "batch_0003",
			Seed:        3,
		},
	})

	if _, err := InspectBatch(batchRoot); err == nil {
		t.Fatalf("expected batch qa to reject records without truth_checks")
	}
}

func writeManifest(t *testing.T, batchRoot string, manifest export.BatchManifest) {
	t.Helper()
	content, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		t.Fatalf("marshal manifest: %v", err)
	}
	if err := os.WriteFile(filepath.Join(batchRoot, "manifest.json"), content, 0o644); err != nil {
		t.Fatalf("write manifest: %v", err)
	}
}

func writeLabels(t *testing.T, path string, records []export.SampleRecord) {
	t.Helper()
	file, err := os.Create(path)
	if err != nil {
		t.Fatalf("create labels: %v", err)
	}
	defer file.Close()
	for _, record := range records {
		content, err := json.Marshal(record)
		if err != nil {
			t.Fatalf("marshal record: %v", err)
		}
		if _, err := file.Write(append(content, '\n')); err != nil {
			t.Fatalf("write labels: %v", err)
		}
	}
}

func writeTestPNG(t *testing.T, path string, width int, height int) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir asset dir: %v", err)
	}
	img := image.NewRGBA(image.Rect(0, 0, width, height))
	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			img.SetRGBA(x, y, color.RGBA{R: uint8(32 + x%64), G: uint8(96 + y%64), B: 180, A: 255})
		}
	}
	file, err := os.Create(path)
	if err != nil {
		t.Fatalf("create png: %v", err)
	}
	defer file.Close()
	if err := png.Encode(file, img); err != nil {
		t.Fatalf("encode png: %v", err)
	}
}
