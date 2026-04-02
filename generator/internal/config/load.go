package config

import (
	"errors"
	"fmt"
	"os"
	"strconv"
	"strings"
)

type Config struct {
	Project  ProjectConfig  `yaml:"project"`
	Canvas   CanvasConfig   `yaml:"canvas"`
	Sampling SamplingConfig `yaml:"sampling"`
	Slide    SlideConfig    `yaml:"slide"`
}

type ProjectConfig struct {
	DatasetName string `yaml:"dataset_name"`
	Split       string `yaml:"split"`
	SampleCount int    `yaml:"sample_count"`
	BatchID     string `yaml:"batch_id"`
	Seed        int64  `yaml:"seed"`
}

type CanvasConfig struct {
	SceneWidth  int `yaml:"scene_width"`
	SceneHeight int `yaml:"scene_height"`
	QueryWidth  int `yaml:"query_width"`
	QueryHeight int `yaml:"query_height"`
}

type SamplingConfig struct {
	TargetCountMin     int `yaml:"target_count_min"`
	TargetCountMax     int `yaml:"target_count_max"`
	DistractorCountMin int `yaml:"distractor_count_min"`
	DistractorCountMax int `yaml:"distractor_count_max"`
}

type SlideConfig struct {
	GapWidth          int `yaml:"gap_width"`
	GapHeight         int `yaml:"gap_height"`
	MaxVerticalJitter int `yaml:"max_vertical_jitter"`
}

func Load(path string) (Config, error) {
	var cfg Config
	content, err := os.ReadFile(path)
	if err != nil {
		return cfg, err
	}
	if err := parseConfig(content, &cfg); err != nil {
		return cfg, err
	}
	if err := cfg.Validate(); err != nil {
		return cfg, err
	}
	return cfg, nil
}

func (c Config) Validate() error {
	switch {
	case c.Project.BatchID == "":
		return errors.New("project.batch_id is required")
	case c.Project.SampleCount < 0:
		return errors.New("project.sample_count cannot be negative")
	case c.Canvas.SceneWidth <= 0 || c.Canvas.SceneHeight <= 0:
		return errors.New("canvas.scene_width and canvas.scene_height must be positive")
	case c.Canvas.QueryWidth <= 0 || c.Canvas.QueryHeight <= 0:
		return errors.New("canvas.query_width and canvas.query_height must be positive")
	case c.Sampling.TargetCountMin <= 0 || c.Sampling.TargetCountMax < c.Sampling.TargetCountMin:
		return errors.New("sampling target count range is invalid")
	case c.Sampling.DistractorCountMin < 0 || c.Sampling.DistractorCountMax < c.Sampling.DistractorCountMin:
		return errors.New("sampling distractor count range is invalid")
	case c.Slide.GapWidth < 0 || c.Slide.GapHeight < 0 || c.Slide.MaxVerticalJitter < 0:
		return errors.New("slide config values cannot be negative")
	default:
		return nil
	}
}

func parseConfig(content []byte, cfg *Config) error {
	section := ""
	for lineNumber, rawLine := range strings.Split(string(content), "\n") {
		line := strings.TrimSpace(rawLine)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if strings.HasSuffix(line, ":") && !strings.Contains(line, " ") {
			section = strings.TrimSuffix(line, ":")
			continue
		}

		key, value, err := splitYAMLField(line)
		if err != nil {
			return fmt.Errorf("invalid config line %d: %w", lineNumber+1, err)
		}

		switch section {
		case "project":
			if err := assignProjectField(&cfg.Project, key, value); err != nil {
				return fmt.Errorf("invalid project field on line %d: %w", lineNumber+1, err)
			}
		case "canvas":
			if err := assignCanvasField(&cfg.Canvas, key, value); err != nil {
				return fmt.Errorf("invalid canvas field on line %d: %w", lineNumber+1, err)
			}
		case "sampling":
			if err := assignSamplingField(&cfg.Sampling, key, value); err != nil {
				return fmt.Errorf("invalid sampling field on line %d: %w", lineNumber+1, err)
			}
		case "slide":
			if err := assignSlideField(&cfg.Slide, key, value); err != nil {
				return fmt.Errorf("invalid slide field on line %d: %w", lineNumber+1, err)
			}
		default:
			return fmt.Errorf("unknown config section %q on line %d", section, lineNumber+1)
		}
	}
	return nil
}

func assignProjectField(project *ProjectConfig, key string, value string) error {
	switch key {
	case "dataset_name":
		project.DatasetName = value
	case "split":
		project.Split = value
	case "sample_count":
		parsed, err := strconv.Atoi(value)
		if err != nil {
			return err
		}
		project.SampleCount = parsed
	case "batch_id":
		project.BatchID = value
	case "seed":
		parsed, err := strconv.ParseInt(value, 10, 64)
		if err != nil {
			return err
		}
		project.Seed = parsed
	default:
		return fmt.Errorf("unsupported key: %s", key)
	}
	return nil
}

func assignCanvasField(canvas *CanvasConfig, key string, value string) error {
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return err
	}
	switch key {
	case "scene_width":
		canvas.SceneWidth = parsed
	case "scene_height":
		canvas.SceneHeight = parsed
	case "query_width":
		canvas.QueryWidth = parsed
	case "query_height":
		canvas.QueryHeight = parsed
	default:
		return fmt.Errorf("unsupported key: %s", key)
	}
	return nil
}

func assignSamplingField(sampling *SamplingConfig, key string, value string) error {
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return err
	}
	switch key {
	case "target_count_min":
		sampling.TargetCountMin = parsed
	case "target_count_max":
		sampling.TargetCountMax = parsed
	case "distractor_count_min":
		sampling.DistractorCountMin = parsed
	case "distractor_count_max":
		sampling.DistractorCountMax = parsed
	default:
		return fmt.Errorf("unsupported key: %s", key)
	}
	return nil
}

func assignSlideField(slide *SlideConfig, key string, value string) error {
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return err
	}
	switch key {
	case "gap_width":
		slide.GapWidth = parsed
	case "gap_height":
		slide.GapHeight = parsed
	case "max_vertical_jitter":
		slide.MaxVerticalJitter = parsed
	default:
		return fmt.Errorf("unsupported key: %s", key)
	}
	return nil
}

func splitYAMLField(line string) (string, string, error) {
	parts := strings.SplitN(line, ":", 2)
	if len(parts) != 2 {
		return "", "", fmt.Errorf("expected key: value")
	}
	key := strings.TrimSpace(parts[0])
	value := strings.TrimSpace(parts[1])
	value = strings.Trim(value, "\"'")
	if key == "" || value == "" {
		return "", "", fmt.Errorf("expected non-empty key and value")
	}
	return key, value, nil
}
