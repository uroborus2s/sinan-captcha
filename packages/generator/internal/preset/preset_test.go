package preset

import (
	"os"
	"path/filepath"
	"testing"

	"sinan-captcha/generator/internal/config"
)

func TestResolveReturnsBuiltInHardPresets(t *testing.T) {
	group1, err := Resolve("group1", "hard")
	if err != nil {
		t.Fatalf("resolve group1 hard: %v", err)
	}
	group2, err := Resolve("group2", "hard")
	if err != nil {
		t.Fatalf("resolve group2 hard: %v", err)
	}

	if got, want := group1.FileName, "group1.hard.yaml"; got != want {
		t.Fatalf("unexpected group1 hard filename: got %s want %s", got, want)
	}
	if got := group1.Config.Effects.Click.IconEdgeBlurRadiusMax; got == 0 {
		t.Fatalf("expected group1 hard preset to enable click edge blur")
	}
	if got := group1.Config.Effects.Click.QueryBackgroundTransparentRatio; got <= 0.5 {
		t.Fatalf("expected group1 hard preset to stay transparent-majority, got %.2f", got)
	}
	if got, want := group2.FileName, "group2.hard.yaml"; got != want {
		t.Fatalf("unexpected group2 hard filename: got %s want %s", got, want)
	}
	if got := group2.Config.Effects.Slide.TileEdgeBlurRadiusMax; got == 0 {
		t.Fatalf("expected group2 hard preset to enable slide tile blur")
	}
}

func TestResolveReturnsBuiltInV1Presets(t *testing.T) {
	group1, err := Resolve("group1", "v1")
	if err != nil {
		t.Fatalf("resolve group1 v1: %v", err)
	}
	group2, err := Resolve("group2", "v1")
	if err != nil {
		t.Fatalf("resolve group2 v1: %v", err)
	}

	if got, want := group1.FileName, "group1.v1.yaml"; got != want {
		t.Fatalf("unexpected group1 v1 filename: got %s want %s", got, want)
	}
	if got, want := group1.Config.Project.SampleCount, 10000; got != want {
		t.Fatalf("unexpected group1 v1 sample count: got %d want %d", got, want)
	}
	if got, want := group1.Config.Sampling.TargetCountMin, 3; got != want {
		t.Fatalf("unexpected group1 v1 target_count_min: got %d want %d", got, want)
	}
	if got, want := group1.Config.Sampling.TargetCountMax, 3; got != want {
		t.Fatalf("unexpected group1 v1 target_count_max: got %d want %d", got, want)
	}
	if got, want := group2.FileName, "group2.v1.yaml"; got != want {
		t.Fatalf("unexpected group2 v1 filename: got %s want %s", got, want)
	}
	if got, want := group2.Config.Project.SampleCount, 10000; got != want {
		t.Fatalf("unexpected group2 v1 sample count: got %d want %d", got, want)
	}
}

func TestResolveStillSupportsLegacyFirstpassPreset(t *testing.T) {
	group1, err := Resolve("group1", "firstpass")
	if err != nil {
		t.Fatalf("resolve group1 firstpass: %v", err)
	}

	if got, want := group1.FileName, "group1.firstpass.yaml"; got != want {
		t.Fatalf("unexpected group1 firstpass filename: got %s want %s", got, want)
	}
	if got, want := group1.Config.Project.SampleCount, 200; got != want {
		t.Fatalf("unexpected group1 firstpass sample count: got %d want %d", got, want)
	}
}

func TestResolveForWorkspaceUsesOverrideFile(t *testing.T) {
	dir := t.TempDir()
	override := builtInGroup1HardConfig()
	override.Project.SampleCount = 12
	override.Effects.Common.SceneVeilStrength = 1.55
	override.Effects.Click.IconEdgeBlurRadiusMin = 2
	override.Effects.Click.IconEdgeBlurRadiusMax = 2
	override.Effects.Click.QueryBackgroundTransparentRatio = 0.93

	path := filepath.Join(dir, "group1.hard.yaml")
	if err := os.WriteFile(path, []byte(config.Format(override)), 0o644); err != nil {
		t.Fatalf("write override preset: %v", err)
	}

	resolved, err := ResolveForWorkspace(dir, "group1", "hard")
	if err != nil {
		t.Fatalf("resolve workspace preset: %v", err)
	}

	if got, want := resolved.Config.Project.SampleCount, 12; got != want {
		t.Fatalf("expected workspace preset sample count to win, got %d want %d", got, want)
	}
	if got, want := resolved.Config.Effects.Common.SceneVeilStrength, 1.55; got != want {
		t.Fatalf("expected workspace preset veil strength to win, got %.2f want %.2f", got, want)
	}
	if got, want := resolved.Config.Effects.Click.IconEdgeBlurRadiusMin, 2; got != want {
		t.Fatalf("expected workspace preset click blur min to win, got %d want %d", got, want)
	}
	if got, want := resolved.Config.Effects.Click.QueryBackgroundTransparentRatio, 0.93; got != want {
		t.Fatalf("expected workspace preset transparent ratio to win, got %.2f want %.2f", got, want)
	}
}

func TestResolveForWorkspaceFallsBackToBuiltInWhenOverrideMissing(t *testing.T) {
	resolved, err := ResolveForWorkspace(t.TempDir(), "group2", "hard")
	if err != nil {
		t.Fatalf("resolve built-in fallback: %v", err)
	}

	if got, want := resolved.FileName, "group2.hard.yaml"; got != want {
		t.Fatalf("unexpected fallback filename: got %s want %s", got, want)
	}
	if got := resolved.Config.Effects.Slide.TileEdgeBlurRadiusMax; got == 0 {
		t.Fatalf("expected built-in hard preset to remain available when workspace override is missing")
	}
}

func TestResolveForWorkspaceKeepsBuiltInDefaultsForMissingNewFields(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "group1.hard.yaml")
	content := "" +
		"project:\n" +
		"  dataset_name: legacy_group1_hard\n" +
		"  split: train\n" +
		"  sample_count: 180\n" +
		"  batch_id: legacy_hd_0001\n" +
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
		t.Fatalf("write legacy override: %v", err)
	}

	resolved, err := ResolveForWorkspace(dir, "group1", "hard")
	if err != nil {
		t.Fatalf("resolve legacy override: %v", err)
	}

	if got, want := resolved.Config.Effects.Click.QueryBackgroundTransparentRatio, 0.82; got != want {
		t.Fatalf("expected legacy override to inherit built-in transparent ratio, got %.2f want %.2f", got, want)
	}
}

func TestResolveForWorkspaceUsesSharedSmokeOverride(t *testing.T) {
	dir := t.TempDir()
	override := builtInGroup1HardConfig()
	override.Project.DatasetName = "sinan_shared_smoke"
	override.Project.SampleCount = 7
	override.Project.BatchID = "smoke_override_0001"
	override.Effects.Common.SceneVeilStrength = 1.18

	path := filepath.Join(dir, "smoke.yaml")
	if err := os.WriteFile(path, []byte(config.Format(override)), 0o644); err != nil {
		t.Fatalf("write smoke override: %v", err)
	}

	resolved, err := ResolveForWorkspace(dir, "group2", "smoke")
	if err != nil {
		t.Fatalf("resolve smoke override: %v", err)
	}

	if got, want := resolved.FileName, "smoke.yaml"; got != want {
		t.Fatalf("unexpected smoke filename: got %s want %s", got, want)
	}
	if got, want := resolved.Config.Project.SampleCount, 7; got != want {
		t.Fatalf("expected smoke override sample count to win, got %d want %d", got, want)
	}
	if got, want := resolved.Config.Effects.Common.SceneVeilStrength, 1.18; got != want {
		t.Fatalf("expected smoke override veil strength to win, got %.2f want %.2f", got, want)
	}
}

func TestResolveForWorkspaceReturnsErrorWhenOverrideInvalid(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "group1.hard.yaml")
	content := []byte("project:\n  dataset_name: broken\neffects:\n  common:\n    background_blur_radius_min: 3\n    background_blur_radius_max: 1\n")
	if err := os.WriteFile(path, content, 0o644); err != nil {
		t.Fatalf("write invalid override: %v", err)
	}

	if _, err := ResolveForWorkspace(dir, "group1", "hard"); err == nil {
		t.Fatalf("expected invalid workspace override to return error")
	}
}

func builtInGroup1HardConfig() config.Config {
	return config.Config{
		Project: config.ProjectConfig{
			DatasetName: "sinan_group1_hard",
			Split:       "train",
			SampleCount: 200,
			BatchID:     "group1_hd_0001",
			Seed:        20260404,
		},
		Canvas: config.CanvasConfig{
			SceneWidth:  300,
			SceneHeight: 150,
			QueryWidth:  120,
			QueryHeight: 36,
		},
		Sampling: config.SamplingConfig{
			TargetCountMin:     2,
			TargetCountMax:     4,
			DistractorCountMin: 3,
			DistractorCountMax: 6,
		},
		Slide: config.SlideConfig{
			GapWidth:          52,
			GapHeight:         52,
			MaxVerticalJitter: 4,
		},
		Effects: config.EffectsConfig{
			Common: config.CommonEffectsConfig{
				SceneVeilStrength:       1.35,
				BackgroundBlurRadiusMin: 1,
				BackgroundBlurRadiusMax: 2,
			},
			Click: config.ClickEffectsConfig{
				IconShadowAlphaMin:              0.22,
				IconShadowAlphaMax:              0.34,
				IconShadowOffsetXMin:            1,
				IconShadowOffsetXMax:            3,
				IconShadowOffsetYMin:            2,
				IconShadowOffsetYMax:            4,
				IconEdgeBlurRadiusMin:           1,
				IconEdgeBlurRadiusMax:           2,
				QueryBackgroundTransparentRatio: 0.82,
			},
			Slide: config.SlideEffectsConfig{
				GapShadowAlphaMin:     0.14,
				GapShadowAlphaMax:     0.24,
				GapShadowOffsetXMin:   1,
				GapShadowOffsetXMax:   3,
				GapShadowOffsetYMin:   1,
				GapShadowOffsetYMax:   3,
				TileEdgeBlurRadiusMin: 1,
				TileEdgeBlurRadiusMax: 2,
			},
		},
	}
}
