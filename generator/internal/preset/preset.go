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
	case name == "smoke":
		return smokePreset(task), nil
	default:
		return Preset{}, fmt.Errorf("unsupported preset %q for task %q", name, task)
	}
}

func WriteWorkspaceCopies(dir string) error {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	presets := []Preset{
		smokePreset("group1"),
		group1FirstpassPreset(),
		group2FirstpassPreset(),
	}
	for _, preset := range presets {
		path := filepath.Join(dir, preset.FileName)
		if err := os.WriteFile(path, []byte(config.Format(preset.Config)), 0o644); err != nil {
			return err
		}
	}
	return nil
}

func smokePreset(task string) Preset {
	cfg := config.Config{
		Project: config.ProjectConfig{
			DatasetName: fmt.Sprintf("sinan_%s_smoke", normalizeTask(task)),
			Split:       "smoke",
			SampleCount: 20,
			BatchID:     "smoke_0001",
			Seed:        20260402,
		},
		Canvas: config.CanvasConfig{
			SceneWidth:  300,
			SceneHeight: 150,
			QueryWidth:  120,
			QueryHeight: 36,
		},
		Sampling: config.SamplingConfig{
			TargetCountMin:     2,
			TargetCountMax:     2,
			DistractorCountMin: 2,
			DistractorCountMax: 3,
		},
		Slide: config.SlideConfig{
			GapWidth:          52,
			GapHeight:         52,
			MaxVerticalJitter: 4,
		},
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
		Config: config.Config{
			Project: config.ProjectConfig{
				DatasetName: "sinan_group1_firstpass",
				Split:       "train",
				SampleCount: 200,
				BatchID:     "group1_fp_0001",
				Seed:        20260403,
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
		},
	}
}

func group2FirstpassPreset() Preset {
	return Preset{
		Name:     "firstpass",
		Task:     "group2",
		FileName: "group2.firstpass.yaml",
		Config: config.Config{
			Project: config.ProjectConfig{
				DatasetName: "sinan_group2_firstpass",
				Split:       "train",
				SampleCount: 200,
				BatchID:     "group2_fp_0001",
				Seed:        20260403,
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
