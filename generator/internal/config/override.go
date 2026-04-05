package config

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"os"
)

type Override struct {
	Project  *ProjectOverride  `json:"project,omitempty"`
	Sampling *SamplingOverride `json:"sampling,omitempty"`
	Effects  *EffectsOverride  `json:"effects,omitempty"`
}

type ProjectOverride struct {
	SampleCount *int `json:"sample_count,omitempty"`
}

type SamplingOverride struct {
	TargetCountMin     *int `json:"target_count_min,omitempty"`
	TargetCountMax     *int `json:"target_count_max,omitempty"`
	DistractorCountMin *int `json:"distractor_count_min,omitempty"`
	DistractorCountMax *int `json:"distractor_count_max,omitempty"`
}

type EffectsOverride struct {
	Common *CommonEffectsOverride `json:"common,omitempty"`
	Click  *ClickEffectsOverride  `json:"click,omitempty"`
	Slide  *SlideEffectsOverride  `json:"slide,omitempty"`
}

type CommonEffectsOverride struct {
	SceneVeilStrength       *float64 `json:"scene_veil_strength,omitempty"`
	BackgroundBlurRadiusMin *int     `json:"background_blur_radius_min,omitempty"`
	BackgroundBlurRadiusMax *int     `json:"background_blur_radius_max,omitempty"`
}

type ClickEffectsOverride struct {
	IconShadowAlphaMin    *float64 `json:"icon_shadow_alpha_min,omitempty"`
	IconShadowAlphaMax    *float64 `json:"icon_shadow_alpha_max,omitempty"`
	IconShadowOffsetXMin  *int     `json:"icon_shadow_offset_x_min,omitempty"`
	IconShadowOffsetXMax  *int     `json:"icon_shadow_offset_x_max,omitempty"`
	IconShadowOffsetYMin  *int     `json:"icon_shadow_offset_y_min,omitempty"`
	IconShadowOffsetYMax  *int     `json:"icon_shadow_offset_y_max,omitempty"`
	IconEdgeBlurRadiusMin *int     `json:"icon_edge_blur_radius_min,omitempty"`
	IconEdgeBlurRadiusMax *int     `json:"icon_edge_blur_radius_max,omitempty"`
}

type SlideEffectsOverride struct {
	GapShadowAlphaMin     *float64 `json:"gap_shadow_alpha_min,omitempty"`
	GapShadowAlphaMax     *float64 `json:"gap_shadow_alpha_max,omitempty"`
	GapShadowOffsetXMin   *int     `json:"gap_shadow_offset_x_min,omitempty"`
	GapShadowOffsetXMax   *int     `json:"gap_shadow_offset_x_max,omitempty"`
	GapShadowOffsetYMin   *int     `json:"gap_shadow_offset_y_min,omitempty"`
	GapShadowOffsetYMax   *int     `json:"gap_shadow_offset_y_max,omitempty"`
	TileEdgeBlurRadiusMin *int     `json:"tile_edge_blur_radius_min,omitempty"`
	TileEdgeBlurRadiusMax *int     `json:"tile_edge_blur_radius_max,omitempty"`
}

func LoadOverride(path string) (Override, error) {
	var override Override
	content, err := os.ReadFile(path)
	if err != nil {
		return override, err
	}
	decoder := json.NewDecoder(bytes.NewReader(content))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&override); err != nil {
		return override, err
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		if err == nil {
			return override, errors.New("override file must contain exactly one JSON object")
		}
		return override, err
	}
	return override, nil
}

func ApplyOverride(base Config, override Override) Config {
	cfg := base
	if override.Project != nil {
		applyInt(&cfg.Project.SampleCount, override.Project.SampleCount)
	}
	if override.Sampling != nil {
		applyInt(&cfg.Sampling.TargetCountMin, override.Sampling.TargetCountMin)
		applyInt(&cfg.Sampling.TargetCountMax, override.Sampling.TargetCountMax)
		applyInt(&cfg.Sampling.DistractorCountMin, override.Sampling.DistractorCountMin)
		applyInt(&cfg.Sampling.DistractorCountMax, override.Sampling.DistractorCountMax)
	}
	if override.Effects != nil {
		if override.Effects.Common != nil {
			applyFloat(&cfg.Effects.Common.SceneVeilStrength, override.Effects.Common.SceneVeilStrength)
			applyInt(&cfg.Effects.Common.BackgroundBlurRadiusMin, override.Effects.Common.BackgroundBlurRadiusMin)
			applyInt(&cfg.Effects.Common.BackgroundBlurRadiusMax, override.Effects.Common.BackgroundBlurRadiusMax)
		}
		if override.Effects.Click != nil {
			applyFloat(&cfg.Effects.Click.IconShadowAlphaMin, override.Effects.Click.IconShadowAlphaMin)
			applyFloat(&cfg.Effects.Click.IconShadowAlphaMax, override.Effects.Click.IconShadowAlphaMax)
			applyInt(&cfg.Effects.Click.IconShadowOffsetXMin, override.Effects.Click.IconShadowOffsetXMin)
			applyInt(&cfg.Effects.Click.IconShadowOffsetXMax, override.Effects.Click.IconShadowOffsetXMax)
			applyInt(&cfg.Effects.Click.IconShadowOffsetYMin, override.Effects.Click.IconShadowOffsetYMin)
			applyInt(&cfg.Effects.Click.IconShadowOffsetYMax, override.Effects.Click.IconShadowOffsetYMax)
			applyInt(&cfg.Effects.Click.IconEdgeBlurRadiusMin, override.Effects.Click.IconEdgeBlurRadiusMin)
			applyInt(&cfg.Effects.Click.IconEdgeBlurRadiusMax, override.Effects.Click.IconEdgeBlurRadiusMax)
		}
		if override.Effects.Slide != nil {
			applyFloat(&cfg.Effects.Slide.GapShadowAlphaMin, override.Effects.Slide.GapShadowAlphaMin)
			applyFloat(&cfg.Effects.Slide.GapShadowAlphaMax, override.Effects.Slide.GapShadowAlphaMax)
			applyInt(&cfg.Effects.Slide.GapShadowOffsetXMin, override.Effects.Slide.GapShadowOffsetXMin)
			applyInt(&cfg.Effects.Slide.GapShadowOffsetXMax, override.Effects.Slide.GapShadowOffsetXMax)
			applyInt(&cfg.Effects.Slide.GapShadowOffsetYMin, override.Effects.Slide.GapShadowOffsetYMin)
			applyInt(&cfg.Effects.Slide.GapShadowOffsetYMax, override.Effects.Slide.GapShadowOffsetYMax)
			applyInt(&cfg.Effects.Slide.TileEdgeBlurRadiusMin, override.Effects.Slide.TileEdgeBlurRadiusMin)
			applyInt(&cfg.Effects.Slide.TileEdgeBlurRadiusMax, override.Effects.Slide.TileEdgeBlurRadiusMax)
		}
	}
	return cfg
}

func applyInt(target *int, value *int) {
	if value != nil {
		*target = *value
	}
}

func applyFloat(target *float64, value *float64) {
	if value != nil {
		*target = *value
	}
}
