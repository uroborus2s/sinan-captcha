package slide

import (
	"hash/fnv"
	"image"
	"image/color"
	"image/draw"
	"image/png"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"sinan-captcha/generator/internal/config"
	"sinan-captcha/generator/internal/material"
)

func TestGenerateBuildsConsistentSlideRecord(t *testing.T) {
	root := t.TempDir()
	backgroundPath := filepath.Join(root, "background.png")
	writeTestPNG(t, backgroundPath, 240, 140)
	iconPath := filepath.Join(root, "icon.png")
	writeMaskIconPNG(t, iconPath, 48, 48)

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
			Classes: []material.ClassAssets{
				{
					ID:   0,
					Name: "icon_flag",
					Icons: []material.IconAsset{
						{Path: iconPath, Width: 48, Height: 48},
					},
				},
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

	tile := mustRGBA(t, assets[record.TileImage])
	master := mustRGBA(t, assets[record.MasterImage])
	sceneSource, err := loadImage(backgroundPath)
	if err != nil {
		t.Fatalf("load background: %v", err)
	}
	scene := coverResize(sceneSource, 180, 100)

	if tile.RGBAAt(0, 0).A != 0 {
		t.Fatalf("expected tile to preserve mask transparency at top-left corner")
	}
	gapTopLeft := image.Point{X: record.TargetGap.BBox[0], Y: record.TargetGap.BBox[1]}
	if got, want := master.RGBAAt(gapTopLeft.X, gapTopLeft.Y), scene.RGBAAt(gapTopLeft.X, gapTopLeft.Y); got != want {
		t.Fatalf("expected transparent mask corner to leave master unchanged: got %#v want %#v", got, want)
	}

	centerX := tile.Bounds().Dx() / 2
	centerY := tile.Bounds().Dy() / 2
	if tile.RGBAAt(centerX, centerY).A == 0 {
		t.Fatalf("expected tile center to stay opaque inside shaped mask")
	}
	if got, want := master.RGBAAt(record.TargetGap.Center[0], record.TargetGap.Center[1]), scene.RGBAAt(record.TargetGap.Center[0], record.TargetGap.Center[1]); got == want {
		t.Fatalf("expected carved gap center to differ from original scene")
	}
}

func TestGenerateAppliesEffectsWithoutChangingGapTruth(t *testing.T) {
	root := t.TempDir()
	backgroundPath := filepath.Join(root, "background.png")
	writeTestPNG(t, backgroundPath, 240, 140)
	iconPath := filepath.Join(root, "icon.png")
	writeMaskIconPNG(t, iconPath, 48, 48)

	baseCfg := config.Config{
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
		Effects: config.EffectsConfig{
			Common: config.CommonEffectsConfig{
				SceneVeilStrength:       1.0,
				BackgroundBlurRadiusMin: 0,
				BackgroundBlurRadiusMax: 0,
			},
			Slide: config.SlideEffectsConfig{
				GapShadowAlphaMin:     0,
				GapShadowAlphaMax:     0,
				GapShadowOffsetXMin:   0,
				GapShadowOffsetXMax:   0,
				GapShadowOffsetYMin:   0,
				GapShadowOffsetYMax:   0,
				TileEdgeBlurRadiusMin: 0,
				TileEdgeBlurRadiusMax: 0,
			},
		},
	}
	hardCfg := baseCfg
	hardCfg.Effects.Common.SceneVeilStrength = 1.4
	hardCfg.Effects.Common.BackgroundBlurRadiusMin = 1
	hardCfg.Effects.Common.BackgroundBlurRadiusMax = 1
	hardCfg.Effects.Slide.GapShadowAlphaMin = 0.22
	hardCfg.Effects.Slide.GapShadowAlphaMax = 0.22
	hardCfg.Effects.Slide.GapShadowOffsetXMin = 2
	hardCfg.Effects.Slide.GapShadowOffsetXMax = 2
	hardCfg.Effects.Slide.GapShadowOffsetYMin = 2
	hardCfg.Effects.Slide.GapShadowOffsetYMax = 2
	hardCfg.Effects.Slide.TileEdgeBlurRadiusMin = 1
	hardCfg.Effects.Slide.TileEdgeBlurRadiusMax = 1

	catalog := material.Catalog{
		Backgrounds: []material.BackgroundAsset{
			{ID: "bg_1", Path: backgroundPath, Width: 240, Height: 140},
		},
		Classes: []material.ClassAssets{
			{
				ID:   0,
				Name: "icon_flag",
				Icons: []material.IconAsset{
					{Path: iconPath, Width: 48, Height: 48},
				},
			},
		},
	}

	baseRecord, baseAssets, err := Generate(0, baseCfg, catalog)
	if err != nil {
		t.Fatalf("generate base slide: %v", err)
	}
	hardRecord, hardAssets, err := Generate(0, hardCfg, catalog)
	if err != nil {
		t.Fatalf("generate hard slide: %v", err)
	}

	if !reflect.DeepEqual(baseRecord, hardRecord) {
		t.Fatalf("effects should not change slide truth record")
	}
	if imageChecksum(baseAssets[baseRecord.MasterImage]) == imageChecksum(hardAssets[hardRecord.MasterImage]) {
		t.Fatalf("expected hard effects to change master image rendering")
	}
	if imageChecksum(baseAssets[baseRecord.TileImage]) == imageChecksum(hardAssets[hardRecord.TileImage]) {
		t.Fatalf("expected hard effects to change tile image rendering")
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

func writeMaskIconPNG(t *testing.T, path string, width int, height int) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, width, height))
	draw.Draw(img, img.Bounds(), image.Transparent, image.Point{}, draw.Src)

	for y := 6; y < height-6; y++ {
		for x := 6; x < width-10; x++ {
			if x < width/3 {
				if y < height/3 || y > height-height/3 {
					continue
				}
			}
			if x >= width/3 {
				slopeTop := height/2 - (x-width/3)/2
				slopeBottom := height/2 + (x-width/3)/3
				if y < slopeTop || y > slopeBottom {
					continue
				}
			}
			img.SetRGBA(x, y, color.RGBA{R: 255, G: 255, B: 255, A: 255})
		}
	}

	file, err := os.Create(path)
	if err != nil {
		t.Fatalf("create icon png: %v", err)
	}
	defer file.Close()

	if err := png.Encode(file, img); err != nil {
		t.Fatalf("encode icon png: %v", err)
	}
}

func mustRGBA(t *testing.T, img image.Image) *image.RGBA {
	t.Helper()
	rgba, ok := img.(*image.RGBA)
	if !ok {
		t.Fatalf("expected RGBA image, got %T", img)
	}
	return rgba
}

func imageChecksum(img image.Image) uint64 {
	hasher := fnv.New64a()
	bounds := img.Bounds()
	for y := bounds.Min.Y; y < bounds.Max.Y; y++ {
		for x := bounds.Min.X; x < bounds.Max.X; x++ {
			red, green, blue, alpha := img.At(x, y).RGBA()
			_, _ = hasher.Write([]byte{
				byte(red >> 8),
				byte(green >> 8),
				byte(blue >> 8),
				byte(alpha >> 8),
			})
		}
	}
	return hasher.Sum64()
}
