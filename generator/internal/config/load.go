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
	Effects  EffectsConfig  `yaml:"effects"`
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

type EffectsConfig struct {
	Common CommonEffectsConfig `yaml:"common"`
	Click  ClickEffectsConfig  `yaml:"click"`
	Slide  SlideEffectsConfig  `yaml:"slide"`
}

type CommonEffectsConfig struct {
	SceneVeilStrength       float64 `yaml:"scene_veil_strength"`
	BackgroundBlurRadiusMin int     `yaml:"background_blur_radius_min"`
	BackgroundBlurRadiusMax int     `yaml:"background_blur_radius_max"`
}

type ClickEffectsConfig struct {
	IconShadowAlphaMin    float64 `yaml:"icon_shadow_alpha_min"`
	IconShadowAlphaMax    float64 `yaml:"icon_shadow_alpha_max"`
	IconShadowOffsetXMin  int     `yaml:"icon_shadow_offset_x_min"`
	IconShadowOffsetXMax  int     `yaml:"icon_shadow_offset_x_max"`
	IconShadowOffsetYMin  int     `yaml:"icon_shadow_offset_y_min"`
	IconShadowOffsetYMax  int     `yaml:"icon_shadow_offset_y_max"`
	IconEdgeBlurRadiusMin int     `yaml:"icon_edge_blur_radius_min"`
	IconEdgeBlurRadiusMax int     `yaml:"icon_edge_blur_radius_max"`
}

type SlideEffectsConfig struct {
	GapShadowAlphaMin     float64 `yaml:"gap_shadow_alpha_min"`
	GapShadowAlphaMax     float64 `yaml:"gap_shadow_alpha_max"`
	GapShadowOffsetXMin   int     `yaml:"gap_shadow_offset_x_min"`
	GapShadowOffsetXMax   int     `yaml:"gap_shadow_offset_x_max"`
	GapShadowOffsetYMin   int     `yaml:"gap_shadow_offset_y_min"`
	GapShadowOffsetYMax   int     `yaml:"gap_shadow_offset_y_max"`
	TileEdgeBlurRadiusMin int     `yaml:"tile_edge_blur_radius_min"`
	TileEdgeBlurRadiusMax int     `yaml:"tile_edge_blur_radius_max"`
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
	case c.Effects.Common.SceneVeilStrength < 0:
		return errors.New("effects.common.scene_veil_strength cannot be negative")
	default:
		if err := validateIntRange("effects.common.background_blur_radius", c.Effects.Common.BackgroundBlurRadiusMin, c.Effects.Common.BackgroundBlurRadiusMax); err != nil {
			return err
		}
		if err := validateFloatRange("effects.click.icon_shadow_alpha", c.Effects.Click.IconShadowAlphaMin, c.Effects.Click.IconShadowAlphaMax, 0, 1); err != nil {
			return err
		}
		if err := validateIntRange("effects.click.icon_shadow_offset_x", c.Effects.Click.IconShadowOffsetXMin, c.Effects.Click.IconShadowOffsetXMax); err != nil {
			return err
		}
		if err := validateIntRange("effects.click.icon_shadow_offset_y", c.Effects.Click.IconShadowOffsetYMin, c.Effects.Click.IconShadowOffsetYMax); err != nil {
			return err
		}
		if err := validateIntRange("effects.click.icon_edge_blur_radius", c.Effects.Click.IconEdgeBlurRadiusMin, c.Effects.Click.IconEdgeBlurRadiusMax); err != nil {
			return err
		}
		if err := validateFloatRange("effects.slide.gap_shadow_alpha", c.Effects.Slide.GapShadowAlphaMin, c.Effects.Slide.GapShadowAlphaMax, 0, 1); err != nil {
			return err
		}
		if err := validateIntRange("effects.slide.gap_shadow_offset_x", c.Effects.Slide.GapShadowOffsetXMin, c.Effects.Slide.GapShadowOffsetXMax); err != nil {
			return err
		}
		if err := validateIntRange("effects.slide.gap_shadow_offset_y", c.Effects.Slide.GapShadowOffsetYMin, c.Effects.Slide.GapShadowOffsetYMax); err != nil {
			return err
		}
		if err := validateIntRange("effects.slide.tile_edge_blur_radius", c.Effects.Slide.TileEdgeBlurRadiusMin, c.Effects.Slide.TileEdgeBlurRadiusMax); err != nil {
			return err
		}
		return nil
	}
}

func parseConfig(content []byte, cfg *Config) error {
	section := ""
	subsection := ""
	for lineNumber, rawLine := range strings.Split(string(content), "\n") {
		line := strings.TrimSpace(rawLine)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		indent := len(rawLine) - len(strings.TrimLeft(rawLine, " "))
		if strings.HasSuffix(line, ":") && !strings.Contains(line, " ") {
			switch indent {
			case 0:
				section = strings.TrimSuffix(line, ":")
				subsection = ""
			case 2:
				if section != "effects" {
					return fmt.Errorf("nested section %q on line %d is only supported under effects", strings.TrimSuffix(line, ":"), lineNumber+1)
				}
				subsection = strings.TrimSuffix(line, ":")
			default:
				return fmt.Errorf("unsupported indentation for section on line %d", lineNumber+1)
			}
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
		case "effects":
			switch subsection {
			case "common":
				if err := assignCommonEffectsField(&cfg.Effects.Common, key, value); err != nil {
					return fmt.Errorf("invalid effects.common field on line %d: %w", lineNumber+1, err)
				}
			case "click":
				if err := assignClickEffectsField(&cfg.Effects.Click, key, value); err != nil {
					return fmt.Errorf("invalid effects.click field on line %d: %w", lineNumber+1, err)
				}
			case "slide":
				if err := assignSlideEffectsField(&cfg.Effects.Slide, key, value); err != nil {
					return fmt.Errorf("invalid effects.slide field on line %d: %w", lineNumber+1, err)
				}
			default:
				return fmt.Errorf("effects subsection is required before fields on line %d", lineNumber+1)
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

func assignCommonEffectsField(common *CommonEffectsConfig, key string, value string) error {
	switch key {
	case "scene_veil_strength":
		parsed, err := strconv.ParseFloat(value, 64)
		if err != nil {
			return err
		}
		common.SceneVeilStrength = parsed
	case "background_blur_radius_min":
		parsed, err := strconv.Atoi(value)
		if err != nil {
			return err
		}
		common.BackgroundBlurRadiusMin = parsed
	case "background_blur_radius_max":
		parsed, err := strconv.Atoi(value)
		if err != nil {
			return err
		}
		common.BackgroundBlurRadiusMax = parsed
	default:
		return fmt.Errorf("unsupported key: %s", key)
	}
	return nil
}

func assignClickEffectsField(click *ClickEffectsConfig, key string, value string) error {
	switch key {
	case "icon_shadow_alpha_min":
		parsed, err := strconv.ParseFloat(value, 64)
		if err != nil {
			return err
		}
		click.IconShadowAlphaMin = parsed
	case "icon_shadow_alpha_max":
		parsed, err := strconv.ParseFloat(value, 64)
		if err != nil {
			return err
		}
		click.IconShadowAlphaMax = parsed
	case "icon_shadow_offset_x_min":
		parsed, err := strconv.Atoi(value)
		if err != nil {
			return err
		}
		click.IconShadowOffsetXMin = parsed
	case "icon_shadow_offset_x_max":
		parsed, err := strconv.Atoi(value)
		if err != nil {
			return err
		}
		click.IconShadowOffsetXMax = parsed
	case "icon_shadow_offset_y_min":
		parsed, err := strconv.Atoi(value)
		if err != nil {
			return err
		}
		click.IconShadowOffsetYMin = parsed
	case "icon_shadow_offset_y_max":
		parsed, err := strconv.Atoi(value)
		if err != nil {
			return err
		}
		click.IconShadowOffsetYMax = parsed
	case "icon_edge_blur_radius_min":
		parsed, err := strconv.Atoi(value)
		if err != nil {
			return err
		}
		click.IconEdgeBlurRadiusMin = parsed
	case "icon_edge_blur_radius_max":
		parsed, err := strconv.Atoi(value)
		if err != nil {
			return err
		}
		click.IconEdgeBlurRadiusMax = parsed
	default:
		return fmt.Errorf("unsupported key: %s", key)
	}
	return nil
}

func assignSlideEffectsField(slide *SlideEffectsConfig, key string, value string) error {
	switch key {
	case "gap_shadow_alpha_min":
		parsed, err := strconv.ParseFloat(value, 64)
		if err != nil {
			return err
		}
		slide.GapShadowAlphaMin = parsed
	case "gap_shadow_alpha_max":
		parsed, err := strconv.ParseFloat(value, 64)
		if err != nil {
			return err
		}
		slide.GapShadowAlphaMax = parsed
	case "gap_shadow_offset_x_min":
		parsed, err := strconv.Atoi(value)
		if err != nil {
			return err
		}
		slide.GapShadowOffsetXMin = parsed
	case "gap_shadow_offset_x_max":
		parsed, err := strconv.Atoi(value)
		if err != nil {
			return err
		}
		slide.GapShadowOffsetXMax = parsed
	case "gap_shadow_offset_y_min":
		parsed, err := strconv.Atoi(value)
		if err != nil {
			return err
		}
		slide.GapShadowOffsetYMin = parsed
	case "gap_shadow_offset_y_max":
		parsed, err := strconv.Atoi(value)
		if err != nil {
			return err
		}
		slide.GapShadowOffsetYMax = parsed
	case "tile_edge_blur_radius_min":
		parsed, err := strconv.Atoi(value)
		if err != nil {
			return err
		}
		slide.TileEdgeBlurRadiusMin = parsed
	case "tile_edge_blur_radius_max":
		parsed, err := strconv.Atoi(value)
		if err != nil {
			return err
		}
		slide.TileEdgeBlurRadiusMax = parsed
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

func Format(cfg Config) string {
	lines := []string{
		"project:",
		fmt.Sprintf("  dataset_name: %s", cfg.Project.DatasetName),
		fmt.Sprintf("  split: %s", cfg.Project.Split),
		fmt.Sprintf("  sample_count: %d", cfg.Project.SampleCount),
		fmt.Sprintf("  batch_id: %s", cfg.Project.BatchID),
		fmt.Sprintf("  seed: %d", cfg.Project.Seed),
		"",
		"canvas:",
		fmt.Sprintf("  scene_width: %d", cfg.Canvas.SceneWidth),
		fmt.Sprintf("  scene_height: %d", cfg.Canvas.SceneHeight),
		fmt.Sprintf("  query_width: %d", cfg.Canvas.QueryWidth),
		fmt.Sprintf("  query_height: %d", cfg.Canvas.QueryHeight),
		"",
		"sampling:",
		fmt.Sprintf("  target_count_min: %d", cfg.Sampling.TargetCountMin),
		fmt.Sprintf("  target_count_max: %d", cfg.Sampling.TargetCountMax),
		fmt.Sprintf("  distractor_count_min: %d", cfg.Sampling.DistractorCountMin),
		fmt.Sprintf("  distractor_count_max: %d", cfg.Sampling.DistractorCountMax),
		"",
		"slide:",
		fmt.Sprintf("  gap_width: %d", cfg.Slide.GapWidth),
		fmt.Sprintf("  gap_height: %d", cfg.Slide.GapHeight),
		fmt.Sprintf("  max_vertical_jitter: %d", cfg.Slide.MaxVerticalJitter),
		"",
		"effects:",
		"  common:",
		fmt.Sprintf("    scene_veil_strength: %.2f", cfg.Effects.Common.SceneVeilStrength),
		fmt.Sprintf("    background_blur_radius_min: %d", cfg.Effects.Common.BackgroundBlurRadiusMin),
		fmt.Sprintf("    background_blur_radius_max: %d", cfg.Effects.Common.BackgroundBlurRadiusMax),
		"  click:",
		fmt.Sprintf("    icon_shadow_alpha_min: %.2f", cfg.Effects.Click.IconShadowAlphaMin),
		fmt.Sprintf("    icon_shadow_alpha_max: %.2f", cfg.Effects.Click.IconShadowAlphaMax),
		fmt.Sprintf("    icon_shadow_offset_x_min: %d", cfg.Effects.Click.IconShadowOffsetXMin),
		fmt.Sprintf("    icon_shadow_offset_x_max: %d", cfg.Effects.Click.IconShadowOffsetXMax),
		fmt.Sprintf("    icon_shadow_offset_y_min: %d", cfg.Effects.Click.IconShadowOffsetYMin),
		fmt.Sprintf("    icon_shadow_offset_y_max: %d", cfg.Effects.Click.IconShadowOffsetYMax),
		fmt.Sprintf("    icon_edge_blur_radius_min: %d", cfg.Effects.Click.IconEdgeBlurRadiusMin),
		fmt.Sprintf("    icon_edge_blur_radius_max: %d", cfg.Effects.Click.IconEdgeBlurRadiusMax),
		"  slide:",
		fmt.Sprintf("    gap_shadow_alpha_min: %.2f", cfg.Effects.Slide.GapShadowAlphaMin),
		fmt.Sprintf("    gap_shadow_alpha_max: %.2f", cfg.Effects.Slide.GapShadowAlphaMax),
		fmt.Sprintf("    gap_shadow_offset_x_min: %d", cfg.Effects.Slide.GapShadowOffsetXMin),
		fmt.Sprintf("    gap_shadow_offset_x_max: %d", cfg.Effects.Slide.GapShadowOffsetXMax),
		fmt.Sprintf("    gap_shadow_offset_y_min: %d", cfg.Effects.Slide.GapShadowOffsetYMin),
		fmt.Sprintf("    gap_shadow_offset_y_max: %d", cfg.Effects.Slide.GapShadowOffsetYMax),
		fmt.Sprintf("    tile_edge_blur_radius_min: %d", cfg.Effects.Slide.TileEdgeBlurRadiusMin),
		fmt.Sprintf("    tile_edge_blur_radius_max: %d", cfg.Effects.Slide.TileEdgeBlurRadiusMax),
		"",
	}
	return strings.Join(lines, "\n")
}

func validateIntRange(name string, minValue int, maxValue int) error {
	switch {
	case minValue < 0:
		return fmt.Errorf("%s min cannot be negative", name)
	case maxValue < minValue:
		return fmt.Errorf("%s range is invalid", name)
	default:
		return nil
	}
}

func validateFloatRange(name string, minValue float64, maxValue float64, lower float64, upper float64) error {
	switch {
	case minValue < lower || minValue > upper:
		return fmt.Errorf("%s min must be between %.0f and %.0f", name, lower, upper)
	case maxValue < minValue || maxValue > upper:
		return fmt.Errorf("%s range is invalid", name)
	default:
		return nil
	}
}
