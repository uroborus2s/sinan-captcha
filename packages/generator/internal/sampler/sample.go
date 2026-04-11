package sampler

import (
	"fmt"
	"math"
	"math/rand"
	"path/filepath"
	"strings"

	"sinan-captcha/generator/internal/config"
	"sinan-captcha/generator/internal/export"
	"sinan-captcha/generator/internal/layout"
	"sinan-captcha/generator/internal/material"
)

type PlacedObject struct {
	export.ObjectRecord
	IconPath   string
	BaseWidth  int
	BaseHeight int
}

type SamplePlan struct {
	Record         export.SampleRecord
	BackgroundPath string
	Targets        []PlacedObject
	Distractors    []PlacedObject
}

func BuildPlan(index int, cfg config.Config, catalog material.Catalog) (SamplePlan, error) {
	plan := SamplePlan{}
	if len(catalog.Group1Templates) == 0 {
		return plan, fmt.Errorf("material catalog has no group1 templates")
	}
	if len(catalog.Backgrounds) == 0 {
		return plan, fmt.Errorf("material catalog has no backgrounds")
	}

	maxTargets := min(cfg.Sampling.TargetCountMax, len(catalog.Group1Templates))
	if maxTargets < cfg.Sampling.TargetCountMin {
		return plan, fmt.Errorf("not enough templates for target count: have %d need at least %d", len(catalog.Group1Templates), cfg.Sampling.TargetCountMin)
	}

	sampleSeed := cfg.Project.Seed + int64(index)
	rng := rand.New(rand.NewSource(sampleSeed))
	sampleID := fmt.Sprintf("g1_%06d", index+1)
	targetCount := between(rng, cfg.Sampling.TargetCountMin, maxTargets)
	distractorCount := between(rng, cfg.Sampling.DistractorCountMin, cfg.Sampling.DistractorCountMax)
	background := catalog.Backgrounds[rng.Intn(len(catalog.Backgrounds))]

	targetTemplates := selectUniqueTemplates(rng, catalog.Group1Templates, targetCount)
	targets := make([]PlacedObject, 0, len(targetTemplates))
	sizes := make([]layout.Size, 0, targetCount+distractorCount)

	for order, templateAssets := range targetTemplates {
		variant := templateAssets.Variants[rng.Intn(len(templateAssets.Variants))]
		scale := round2(0.88 + rng.Float64()*0.26)
		alpha := round2(0.90 + rng.Float64()*0.08)
		rotationDeg := round1(-14 + rng.Float64()*28)
		baseSize := iconSize(material.ImageAsset{Path: variant.Path, Width: variant.Width, Height: variant.Height}, cfg.Canvas.SceneHeight, scale, rng)
		size := rotatedBounds(baseSize.Width, baseSize.Height, rotationDeg)
		targets = append(targets, PlacedObject{
			ObjectRecord: export.ObjectRecord{
				Order:       order + 1,
				AssetID:     variant.AssetID,
				TemplateID:  variant.TemplateID,
				VariantID:   variant.VariantID,
				Class:       templateAssets.TemplateID,
				ClassID:     templateAssets.Index,
				RotationDeg: rotationDeg,
				Alpha:       alpha,
				Scale:       scale,
			},
			IconPath:   variant.Path,
			BaseWidth:  baseSize.Width,
			BaseHeight: baseSize.Height,
		})
		sizes = append(sizes, size)
	}

	distractors := make([]PlacedObject, 0, distractorCount)
	distractorPool := buildDistractorPool(catalog.Group1Templates, targetTemplates)
	if len(distractorPool) < distractorCount {
		distractorCount = len(distractorPool)
		distractors = make([]PlacedObject, 0, distractorCount)
	}
	for index := 0; index < distractorCount; index++ {
		templateAssets := distractorPool[rng.Intn(len(distractorPool))]
		variant := templateAssets.Variants[rng.Intn(len(templateAssets.Variants))]
		scale := round2(0.84 + rng.Float64()*0.28)
		alpha := round2(0.88 + rng.Float64()*0.08)
		rotationDeg := round1(-16 + rng.Float64()*32)
		baseSize := iconSize(material.ImageAsset{Path: variant.Path, Width: variant.Width, Height: variant.Height}, cfg.Canvas.SceneHeight, scale, rng)
		size := rotatedBounds(baseSize.Width, baseSize.Height, rotationDeg)
		distractors = append(distractors, PlacedObject{
			ObjectRecord: export.ObjectRecord{
				AssetID:     variant.AssetID,
				TemplateID:  variant.TemplateID,
				VariantID:   variant.VariantID,
				Class:       templateAssets.TemplateID,
				ClassID:     templateAssets.Index,
				RotationDeg: rotationDeg,
				Alpha:       alpha,
				Scale:       scale,
			},
			IconPath:   variant.Path,
			BaseWidth:  baseSize.Width,
			BaseHeight: baseSize.Height,
		})
		sizes = append(sizes, size)
	}

	rects, finalSizes, err := placeObjects(cfg, sizes, rng)
	if err != nil {
		return plan, err
	}

	allObjects := make([]*PlacedObject, 0, len(targets)+len(distractors))
	for index := range targets {
		allObjects = append(allObjects, &targets[index])
	}
	for index := range distractors {
		allObjects = append(allObjects, &distractors[index])
	}
	for index, object := range allObjects {
		rescalePlacedObject(object, sizes[index], finalSizes[index])
		assignRect(object, rects[index])
	}

	plan = SamplePlan{
		Record: export.SampleRecord{
			SampleID:        sampleID,
			CaptchaType:     "group1_multi_icon_match",
			QueryImage:      filepath.ToSlash(filepath.Join("query", sampleID+".png")),
			SceneImage:      filepath.ToSlash(filepath.Join("scene", sampleID+".png")),
			SceneTargets:    recordsFromPlaced(targets),
			Distractors:     recordsFromPlaced(distractors),
			BackgroundID:    background.ID,
			StyleID:         "default",
			SourceSignature: buildClickSourceSignature(background.ID, targets, distractors),
			LabelSource:     "gold",
			SourceBatch:     cfg.Project.BatchID,
			Seed:            sampleSeed,
		},
		BackgroundPath: background.Path,
		Targets:        targets,
		Distractors:    distractors,
	}

	return plan, nil
}

func buildDistractorPool(templates []material.Group1TemplateAssets, targets []material.Group1TemplateAssets) []material.Group1TemplateAssets {
	targetNames := make(map[string]struct{}, len(targets))
	for _, target := range targets {
		targetNames[target.TemplateID] = struct{}{}
	}

	pool := make([]material.Group1TemplateAssets, 0, len(templates))
	for _, templateAssets := range templates {
		if _, exists := targetNames[templateAssets.TemplateID]; exists {
			continue
		}
		pool = append(pool, templateAssets)
	}
	return pool
}

func selectUniqueTemplates(rng *rand.Rand, templates []material.Group1TemplateAssets, count int) []material.Group1TemplateAssets {
	permutation := rng.Perm(len(templates))
	selected := make([]material.Group1TemplateAssets, 0, count)
	for _, index := range permutation[:count] {
		selected = append(selected, templates[index])
	}
	return selected
}

func iconSize(icon material.ImageAsset, sceneHeight int, scale float64, rng *rand.Rand) layout.Size {
	baseHeight := float64(sceneHeight) * (0.16 + rng.Float64()*0.08)
	height := max(18, int(math.Round(baseHeight*scale)))
	width := max(18, int(math.Round(float64(icon.Width)*float64(height)/float64(icon.Height))))
	return layout.Size{
		Width:  width,
		Height: height,
	}
}

func rotatedBounds(width int, height int, rotationDeg float64) layout.Size {
	if rotationDeg == 0 {
		return layout.Size{Width: width, Height: height}
	}

	radians := math.Abs(rotationDeg) * math.Pi / 180
	sinValue := math.Abs(math.Sin(radians))
	cosValue := math.Abs(math.Cos(radians))
	return layout.Size{
		Width:  max(1, int(math.Ceil(float64(width)*cosValue+float64(height)*sinValue))),
		Height: max(1, int(math.Ceil(float64(width)*sinValue+float64(height)*cosValue))),
	}
}

func placeObjects(cfg config.Config, sizes []layout.Size, rng *rand.Rand) ([]layout.Rect, []layout.Size, error) {
	current := append([]layout.Size(nil), sizes...)
	for attempt := 0; attempt < 4; attempt++ {
		rects, err := layout.Place(cfg.Canvas.SceneWidth, cfg.Canvas.SceneHeight, current, rng)
		if err == nil {
			return rects, current, nil
		}
		for index := range current {
			current[index].Width = max(14, int(math.Round(float64(current[index].Width)*0.9)))
			current[index].Height = max(14, int(math.Round(float64(current[index].Height)*0.9)))
		}
	}
	return nil, nil, fmt.Errorf("could not place sampled objects on the scene canvas")
}

func assignRect(object *PlacedObject, rect layout.Rect) {
	object.BBox = [4]int{rect.X1, rect.Y1, rect.X2, rect.Y2}
	object.Center = [2]int{rect.X1 + rect.Width()/2, rect.Y1 + rect.Height()/2}
}

func rescalePlacedObject(object *PlacedObject, original layout.Size, placed layout.Size) {
	if original.Width <= 0 || original.Height <= 0 {
		return
	}
	scaleX := float64(placed.Width) / float64(original.Width)
	scaleY := float64(placed.Height) / float64(original.Height)
	scale := math.Min(scaleX, scaleY)
	if scale >= 0.999 {
		return
	}
	object.BaseWidth = max(12, int(math.Round(float64(object.BaseWidth)*scale)))
	object.BaseHeight = max(12, int(math.Round(float64(object.BaseHeight)*scale)))
	object.Scale = round2(object.Scale * scale)
}

func recordsFromPlaced(objects []PlacedObject) []export.ObjectRecord {
	records := make([]export.ObjectRecord, 0, len(objects))
	for _, object := range objects {
		records = append(records, object.ObjectRecord)
	}
	return records
}

func buildClickSourceSignature(backgroundID string, targets []PlacedObject, distractors []PlacedObject) string {
	parts := []string{backgroundID}
	for _, target := range targets {
		parts = append(parts, fmt.Sprintf("t:%s:%s", target.TemplateID, target.VariantID))
	}
	for _, distractor := range distractors {
		parts = append(parts, fmt.Sprintf("d:%s:%s", distractor.TemplateID, distractor.VariantID))
	}
	return strings.Join(parts, "|")
}

func between(rng *rand.Rand, minValue int, maxValue int) int {
	if maxValue <= minValue {
		return minValue
	}
	return minValue + rng.Intn(maxValue-minValue+1)
}

func round2(value float64) float64 {
	return math.Round(value*100) / 100
}

func round1(value float64) float64 {
	return math.Round(value*10) / 10
}

func min(left int, right int) int {
	if left < right {
		return left
	}
	return right
}

func max(left int, right int) int {
	if left > right {
		return left
	}
	return right
}
