package render

import (
	"hash/fnv"
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"testing"

	"sinan-captcha/generator/internal/config"
	"sinan-captcha/generator/internal/export"
	"sinan-captcha/generator/internal/sampler"
)

func TestBuildAppliesEffectsWithoutChangingPlanTruth(t *testing.T) {
	root := t.TempDir()
	backgroundPath := filepath.Join(root, "background.png")
	iconPath := filepath.Join(root, "icon.png")
	writeScenePNG(t, backgroundPath, 240, 140)
	writeIconPNG(t, iconPath, 56, 56)

	plan := sampler.SamplePlan{
		Record: export.SampleRecord{
			SampleID:   "g1_000001",
			QueryImage: "query/g1_000001.png",
			SceneImage: "scene/g1_000001.png",
			Targets: []export.ObjectRecord{
				{Class: "icon_house", ClassID: 0, BBox: [4]int{40, 28, 88, 76}, Center: [2]int{64, 52}},
			},
			Seed: 20260404,
		},
		BackgroundPath: backgroundPath,
		Targets: []sampler.PlacedObject{
			{
				ObjectRecord: export.ObjectRecord{
					Class:       "icon_house",
					ClassID:     0,
					BBox:        [4]int{40, 28, 88, 76},
					Center:      [2]int{64, 52},
					RotationDeg: 0,
					Alpha:       1,
					Scale:       1,
				},
				IconPath:   iconPath,
				BaseWidth:  48,
				BaseHeight: 48,
			},
		},
	}

	baseCfg := config.Config{
		Canvas: config.CanvasConfig{
			SceneWidth:  180,
			SceneHeight: 100,
			QueryWidth:  120,
			QueryHeight: 36,
		},
		Effects: config.EffectsConfig{
			Common: config.CommonEffectsConfig{
				SceneVeilStrength:       1.0,
				BackgroundBlurRadiusMin: 0,
				BackgroundBlurRadiusMax: 0,
			},
			Click: config.ClickEffectsConfig{
				IconShadowAlphaMin:    0.0,
				IconShadowAlphaMax:    0.0,
				IconShadowOffsetXMin:  0,
				IconShadowOffsetXMax:  0,
				IconShadowOffsetYMin:  0,
				IconShadowOffsetYMax:  0,
				IconEdgeBlurRadiusMin: 0,
				IconEdgeBlurRadiusMax: 0,
			},
		},
	}
	hardCfg := baseCfg
	hardCfg.Effects.Common.SceneVeilStrength = 1.45
	hardCfg.Effects.Common.BackgroundBlurRadiusMin = 1
	hardCfg.Effects.Common.BackgroundBlurRadiusMax = 1
	hardCfg.Effects.Click.IconShadowAlphaMin = 0.32
	hardCfg.Effects.Click.IconShadowAlphaMax = 0.32
	hardCfg.Effects.Click.IconShadowOffsetXMin = 2
	hardCfg.Effects.Click.IconShadowOffsetXMax = 2
	hardCfg.Effects.Click.IconShadowOffsetYMin = 3
	hardCfg.Effects.Click.IconShadowOffsetYMax = 3
	hardCfg.Effects.Click.IconEdgeBlurRadiusMin = 1
	hardCfg.Effects.Click.IconEdgeBlurRadiusMax = 1

	_, baseScene, err := Build(plan, baseCfg)
	if err != nil {
		t.Fatalf("build base scene: %v", err)
	}
	_, hardScene, err := Build(plan, hardCfg)
	if err != nil {
		t.Fatalf("build hard scene: %v", err)
	}

	if got, want := imageChecksum(baseScene), imageChecksum(hardScene); got == want {
		t.Fatalf("expected hard effects to change scene rendering")
	}
	if got, want := plan.Targets[0].BBox, [4]int{40, 28, 88, 76}; got != want {
		t.Fatalf("render should not mutate plan truth, got %+v want %+v", got, want)
	}
}

func writeScenePNG(t *testing.T, path string, width int, height int) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, width, height))
	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			img.SetRGBA(x, y, color.RGBA{R: uint8(20 + x%90), G: uint8(70 + y%70), B: 170, A: 255})
		}
	}
	writePNG(t, path, img)
}

func writeIconPNG(t *testing.T, path string, width int, height int) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, width, height))
	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			if x < 4 || y < 4 || x >= width-4 || y >= height-4 {
				img.SetRGBA(x, y, color.RGBA{})
				continue
			}
			img.SetRGBA(x, y, color.RGBA{R: 255, G: 255, B: 255, A: 255})
		}
	}
	writePNG(t, path, img)
}

func writePNG(t *testing.T, path string, img image.Image) {
	t.Helper()
	file, err := os.Create(path)
	if err != nil {
		t.Fatalf("create png: %v", err)
	}
	defer file.Close()
	if err := png.Encode(file, img); err != nil {
		t.Fatalf("encode png: %v", err)
	}
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
