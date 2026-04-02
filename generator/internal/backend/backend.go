package backend

import (
	"fmt"
	"image"
	"strings"

	"sinan-captcha/generator/internal/config"
	"sinan-captcha/generator/internal/export"
	"sinan-captcha/generator/internal/material"
	"sinan-captcha/generator/internal/render"
	"sinan-captcha/generator/internal/sampler"
	"sinan-captcha/generator/internal/slide"
)

type Mode string

const (
	ModeClick Mode = "click"
	ModeSlide Mode = "slide"
)

type Kind string

const (
	KindNative    Kind = "native"
	KindGoCaptcha Kind = "gocaptcha"
)

type Spec struct {
	Mode    Mode
	Backend Kind
}

type Generator interface {
	Generate(index int, cfg config.Config, catalog material.Catalog) (export.SampleRecord, map[string]image.Image, error)
}

func ParseMode(raw string) (Mode, error) {
	switch Mode(strings.ToLower(strings.TrimSpace(raw))) {
	case "", ModeClick:
		return ModeClick, nil
	case ModeSlide:
		return ModeSlide, nil
	default:
		return "", fmt.Errorf("unsupported mode: %s", raw)
	}
}

func ParseBackend(raw string) (Kind, error) {
	switch Kind(strings.ToLower(strings.TrimSpace(raw))) {
	case "", KindNative:
		return KindNative, nil
	case KindGoCaptcha:
		return KindGoCaptcha, nil
	default:
		return "", fmt.Errorf("unsupported backend: %s", raw)
	}
}

func Resolve(modeRaw string, backendRaw string) (Spec, Generator, error) {
	mode, err := ParseMode(modeRaw)
	if err != nil {
		return Spec{}, nil, err
	}
	backend, err := ParseBackend(backendRaw)
	if err != nil {
		return Spec{}, nil, err
	}

	spec := Spec{Mode: mode, Backend: backend}
	switch backend {
	case KindNative:
		return spec, nativeGenerator{mode: mode}, nil
	case KindGoCaptcha:
		return spec, nil, fmt.Errorf("backend %s for mode %s is not implemented", backend, mode)
	default:
		return Spec{}, nil, fmt.Errorf("unsupported backend: %s", backend)
	}
}

func (s Spec) AssetDirs() map[string]string {
	switch s.Mode {
	case ModeSlide:
		return map[string]string{
			"master": "master",
			"tile":   "tile",
		}
	default:
		return map[string]string{
			"query": "query",
			"scene": "scene",
		}
	}
}

type nativeGenerator struct {
	mode Mode
}

func (g nativeGenerator) Generate(index int, cfg config.Config, catalog material.Catalog) (export.SampleRecord, map[string]image.Image, error) {
	switch g.mode {
	case ModeClick:
		return generateClick(index, cfg, catalog)
	case ModeSlide:
		return slide.Generate(index, cfg, catalog)
	default:
		return export.SampleRecord{}, nil, fmt.Errorf("unsupported native mode: %s", g.mode)
	}
}

func generateClick(index int, cfg config.Config, catalog material.Catalog) (export.SampleRecord, map[string]image.Image, error) {
	plan, err := sampler.BuildPlan(index, cfg, catalog)
	if err != nil {
		return export.SampleRecord{}, nil, err
	}
	queryImage, sceneImage, err := render.Build(plan, cfg.Canvas)
	if err != nil {
		return export.SampleRecord{}, nil, err
	}
	record := plan.Record
	record.Mode = string(ModeClick)
	record.Backend = string(KindNative)
	return record, map[string]image.Image{
		record.QueryImage: queryImage,
		record.SceneImage: sceneImage,
	}, nil
}
