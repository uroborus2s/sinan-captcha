package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadParsesEffectsSections(t *testing.T) {
	root := t.TempDir()
	path := filepath.Join(root, "group1.hard.yaml")

	content := "" +
		"project:\n" +
		"  dataset_name: sinan_group1_hard\n" +
		"  split: train\n" +
		"  sample_count: 200\n" +
		"  batch_id: group1_hard_0001\n" +
		"  seed: 20260404\n" +
		"\n" +
		"canvas:\n" +
		"  scene_width: 300\n" +
		"  scene_height: 150\n" +
		"  query_width: 120\n" +
		"  query_height: 36\n" +
		"\n" +
		"sampling:\n" +
		"  target_count_min: 2\n" +
		"  target_count_max: 4\n" +
		"  distractor_count_min: 3\n" +
		"  distractor_count_max: 6\n" +
		"\n" +
		"slide:\n" +
		"  gap_width: 52\n" +
		"  gap_height: 52\n" +
		"  max_vertical_jitter: 4\n" +
		"\n" +
		"effects:\n" +
		"  common:\n" +
		"    scene_veil_strength: 1.35\n" +
		"    background_blur_radius_min: 1\n" +
		"    background_blur_radius_max: 2\n" +
		"  click:\n" +
		"    icon_shadow_alpha_min: 0.22\n" +
		"    icon_shadow_alpha_max: 0.34\n" +
		"    icon_shadow_offset_x_min: 1\n" +
		"    icon_shadow_offset_x_max: 3\n" +
		"    icon_shadow_offset_y_min: 2\n" +
		"    icon_shadow_offset_y_max: 4\n" +
		"    icon_edge_blur_radius_min: 1\n" +
		"    icon_edge_blur_radius_max: 2\n" +
		"  slide:\n" +
		"    gap_shadow_alpha_min: 0.14\n" +
		"    gap_shadow_alpha_max: 0.24\n" +
		"    gap_shadow_offset_x_min: 1\n" +
		"    gap_shadow_offset_x_max: 3\n" +
		"    gap_shadow_offset_y_min: 1\n" +
		"    gap_shadow_offset_y_max: 3\n" +
		"    tile_edge_blur_radius_min: 1\n" +
		"    tile_edge_blur_radius_max: 2\n"
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write config: %v", err)
	}

	cfg, err := Load(path)
	if err != nil {
		t.Fatalf("load config: %v", err)
	}

	if got, want := cfg.Effects.Common.SceneVeilStrength, 1.35; got != want {
		t.Fatalf("unexpected scene veil strength: got %.2f want %.2f", got, want)
	}
	if got, want := cfg.Effects.Common.BackgroundBlurRadiusMax, 2; got != want {
		t.Fatalf("unexpected background blur radius max: got %d want %d", got, want)
	}
	if got, want := cfg.Effects.Click.IconShadowAlphaMin, 0.22; got != want {
		t.Fatalf("unexpected click shadow alpha min: got %.2f want %.2f", got, want)
	}
	if got, want := cfg.Effects.Click.IconEdgeBlurRadiusMax, 2; got != want {
		t.Fatalf("unexpected click edge blur radius max: got %d want %d", got, want)
	}
	if got, want := cfg.Effects.Slide.GapShadowOffsetYMax, 3; got != want {
		t.Fatalf("unexpected slide shadow offset y max: got %d want %d", got, want)
	}
	if got, want := cfg.Effects.Slide.TileEdgeBlurRadiusMin, 1; got != want {
		t.Fatalf("unexpected tile edge blur radius min: got %d want %d", got, want)
	}
}

func TestValidateRejectsInvalidEffectsRanges(t *testing.T) {
	cfg := Config{
		Project: ProjectConfig{
			DatasetName: "sinan_group1_firstpass",
			Split:       "train",
			SampleCount: 10,
			BatchID:     "group1_fp_0001",
			Seed:        20260404,
		},
		Canvas: CanvasConfig{
			SceneWidth:  300,
			SceneHeight: 150,
			QueryWidth:  120,
			QueryHeight: 36,
		},
		Sampling: SamplingConfig{
			TargetCountMin:     2,
			TargetCountMax:     4,
			DistractorCountMin: 2,
			DistractorCountMax: 4,
		},
		Slide: SlideConfig{
			GapWidth:          52,
			GapHeight:         52,
			MaxVerticalJitter: 4,
		},
		Effects: EffectsConfig{
			Common: CommonEffectsConfig{
				SceneVeilStrength:       1.0,
				BackgroundBlurRadiusMin: 2,
				BackgroundBlurRadiusMax: 1,
			},
		},
	}

	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid effects range to fail validation")
	}
}
