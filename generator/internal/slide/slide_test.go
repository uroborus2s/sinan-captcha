package slide

import (
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"testing"

	"sinan-captcha/generator/internal/config"
	"sinan-captcha/generator/internal/material"
)

func TestGenerateBuildsConsistentSlideRecord(t *testing.T) {
	backgroundPath := filepath.Join(t.TempDir(), "background.png")
	writeTestPNG(t, backgroundPath, 240, 140)

	record, assets, err := Generate(
		0,
		config.Config{
			Project: config.ProjectConfig{
				BatchID: "batch_0001",
				Seed:    20260402,
			},
			Canvas: config.CanvasConfig{
				SceneWidth:  180,
				SceneHeight: 100,
				QueryWidth:  120,
				QueryHeight: 36,
			},
			Slide: config.SlideConfig{
				GapWidth:          44,
				GapHeight:         36,
				MaxVerticalJitter: 2,
			},
		},
		material.Catalog{
			Backgrounds: []material.BackgroundAsset{
				{ID: "bg_1", Path: backgroundPath, Width: 240, Height: 140},
			},
		},
	)
	if err != nil {
		t.Fatalf("expected slide record to be generated: %v", err)
	}
	if record.Mode != "slide" || record.Backend != "native" {
		t.Fatalf("unexpected slide metadata: %+v", record)
	}
	if record.TargetGap == nil || record.TileBBox == nil || record.OffsetX == nil || record.OffsetY == nil {
		t.Fatalf("expected slide truth fields to be populated: %+v", record)
	}
	if got, want := *record.OffsetX, record.TargetGap.BBox[0]-record.TileBBox[0]; got != want {
		t.Fatalf("unexpected offset_x: got %d want %d", got, want)
	}
	if got, want := *record.OffsetY, record.TargetGap.BBox[1]-record.TileBBox[1]; got != want {
		t.Fatalf("unexpected offset_y: got %d want %d", got, want)
	}
	if len(assets) != 2 {
		t.Fatalf("expected master and tile assets, got %d", len(assets))
	}
}

func writeTestPNG(t *testing.T, path string, width int, height int) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, width, height))
	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			img.SetRGBA(x, y, color.RGBA{R: uint8(30 + x%60), G: uint8(80 + y%80), B: 160, A: 255})
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
