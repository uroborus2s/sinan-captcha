package preset

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"sinan-captcha/generator/internal/config"
)

type Preset struct {
	Name     string
	Task     string
	FileName string
	Config   config.Config
}

func Resolve(task string, name string) (Preset, error) {
	task = normalizeTask(task)
	name = normalizePreset(name)

	switch {
	case task == "group1" && name == "firstpass":
		return group1FirstpassPreset(), nil
	case task == "group2" && name == "firstpass":
		return group2FirstpassPreset(), nil
	case task == "group1" && name == "hard":
		return group1HardPreset(), nil
	case task == "group2" && name == "hard":
		return group2HardPreset(), nil
	case name == "smoke":
		return smokePreset(task), nil
	default:
		return Preset{}, fmt.Errorf("unsupported preset %q for task %q", name, task)
	}
}

func ResolveForWorkspace(dir string, task string, name string) (Preset, error) {
	selected, err := Resolve(task, name)
	if err != nil {
		return Preset{}, err
	}
	if strings.TrimSpace(dir) == "" {
		return selected, nil
	}

	path := filepath.Join(dir, selected.FileName)
	cfg, err := config.LoadWithDefaults(path, selected.Config)
	if err != nil {
		if os.IsNotExist(err) {
			return selected, nil
		}
		return Preset{}, err
	}
	selected.Config = cfg
	return selected, nil
}

func WriteWorkspaceCopies(dir string) error {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	for _, preset := range builtInPresets() {
		path := filepath.Join(dir, preset.FileName)
		if _, err := os.Stat(path); err == nil {
			continue
		} else if !os.IsNotExist(err) {
			return err
		}
		if err := os.WriteFile(path, []byte(config.Format(preset.Config)), 0o644); err != nil {
			return err
		}
	}
	return nil
}

func smokePreset(task string) Preset {
	cfg := baseConfig(
		normalizeTask(task),
		fmt.Sprintf("sinan_%s_smoke", normalizeTask(task)),
		"smoke",
		20,
		"smoke_0001",
		20260402,
		defaultEffects(),
	)
	cfg.Sampling = config.SamplingConfig{
		TargetCountMin:     2,
		TargetCountMax:     2,
		DistractorCountMin: 2,
		DistractorCountMax: 3,
	}
	return Preset{
		Name:     "smoke",
		Task:     normalizeTask(task),
		FileName: "smoke.yaml",
		Config:   cfg,
	}
}

func group1FirstpassPreset() Preset {
	return Preset{
		Name:     "firstpass",
		Task:     "group1",
		FileName: "group1.firstpass.yaml",
		Config:   baseConfig("group1", "sinan_group1_firstpass", "train", 200, "group1_fp_0001", 20260403, defaultEffects()),
	}
}

func group2FirstpassPreset() Preset {
	return Preset{
		Name:     "firstpass",
		Task:     "group2",
		FileName: "group2.firstpass.yaml",
		Config:   baseConfig("group2", "sinan_group2_firstpass", "train", 200, "group2_fp_0001", 20260403, defaultEffects()),
	}
}

func group1HardPreset() Preset {
	return Preset{
		Name:     "hard",
		Task:     "group1",
		FileName: "group1.hard.yaml",
		Config:   baseConfig("group1", "sinan_group1_hard", "train", 200, "group1_hd_0001", 20260404, hardEffects()),
	}
}

func group2HardPreset() Preset {
	return Preset{
		Name:     "hard",
		Task:     "group2",
		FileName: "group2.hard.yaml",
		Config:   baseConfig("group2", "sinan_group2_hard", "train", 200, "group2_hd_0001", 20260404, hardEffects()),
	}
}

func builtInPresets() []Preset {
	return []Preset{
		smokePreset("group1"),
		group1FirstpassPreset(),
		group2FirstpassPreset(),
		group1HardPreset(),
		group2HardPreset(),
	}
}

func baseConfig(task string, datasetName string, split string, sampleCount int, batchID string, seed int64, effects config.EffectsConfig) config.Config {
	return config.Config{
		Project: config.ProjectConfig{
			DatasetName: datasetName,
			Split:       split,
			SampleCount: sampleCount,
			BatchID:     batchID,
			Seed:        seed,
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
		Effects: effects,
	}
}

func defaultEffects() config.EffectsConfig {
	return config.EffectsConfig{
		Common: config.CommonEffectsConfig{
			SceneVeilStrength:       1.00,
			BackgroundBlurRadiusMin: 0,
			BackgroundBlurRadiusMax: 0,
		},
		Click: config.ClickEffectsConfig{
			IconShadowAlphaMin:              0.24,
			IconShadowAlphaMax:              0.24,
			IconShadowOffsetXMin:            2,
			IconShadowOffsetXMax:            2,
			IconShadowOffsetYMin:            3,
			IconShadowOffsetYMax:            3,
			IconEdgeBlurRadiusMin:           0,
			IconEdgeBlurRadiusMax:           0,
			QueryBackgroundTransparentRatio: 0.90,
		},
		Slide: config.SlideEffectsConfig{
			GapShadowAlphaMin:     0.00,
			GapShadowAlphaMax:     0.00,
			GapShadowOffsetXMin:   0,
			GapShadowOffsetXMax:   0,
			GapShadowOffsetYMin:   0,
			GapShadowOffsetYMax:   0,
			TileEdgeBlurRadiusMin: 0,
			TileEdgeBlurRadiusMax: 0,
		},
	}
}

func hardEffects() config.EffectsConfig {
	return config.EffectsConfig{
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
	}
}

func normalizeTask(task string) string {
	task = strings.ToLower(strings.TrimSpace(task))
	if task == "" {
		return "group1"
	}
	return task
}

func normalizePreset(name string) string {
	name = strings.ToLower(strings.TrimSpace(name))
	if name == "" {
		return "firstpass"
	}
	return name
}
