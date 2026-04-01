package sampler

import (
	"fmt"
	"math"
	"math/rand"
	"path/filepath"

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
	if len(catalog.Classes) == 0 {
		return plan, fmt.Errorf("material catalog has no classes")
	}
	if len(catalog.Backgrounds) == 0 {
		return plan, fmt.Errorf("material catalog has no backgrounds")
	}

	maxTargets := min(cfg.Sampling.TargetCountMax, len(catalog.Classes))
	if maxTargets < cfg.Sampling.TargetCountMin {
		return plan, fmt.Errorf("not enough classes for target count: have %d need at least %d", len(catalog.Classes), cfg.Sampling.TargetCountMin)
	}

	sampleSeed := cfg.Project.Seed + int64(index)
	rng := rand.New(rand.NewSource(sampleSeed))
	sampleID := fmt.Sprintf("g1_%06d", index+1)
	targetCount := between(rng, cfg.Sampling.TargetCountMin, maxTargets)
	distractorCount := between(rng, cfg.Sampling.DistractorCountMin, cfg.Sampling.DistractorCountMax)
	background := catalog.Backgrounds[rng.Intn(len(catalog.Backgrounds))]

	targetClasses := selectUniqueClasses(rng, catalog.Classes, targetCount)
	targets := make([]PlacedObject, 0, len(targetClasses))
	sizes := make([]layout.Size, 0, targetCount+distractorCount)

	for order, classAssets := range targetClasses {
		icon := classAssets.Icons[rng.Intn(len(classAssets.Icons))]
		scale := round2(0.88 + rng.Float64()*0.26)
		alpha := round2(0.90 + rng.Float64()*0.08)
		rotationDeg := round1(-14 + rng.Float64()*28)
		baseSize := iconSize(icon, cfg.Canvas.SceneHeight, scale, rng)
		size := rotatedBounds(baseSize.Width, baseSize.Height, rotationDeg)
		targets = append(targets, PlacedObject{
			ObjectRecord: export.ObjectRecord{
				Order:       order + 1,
				Class:       classAssets.Name,
				ClassID:     classAssets.ID,
				RotationDeg: rotationDeg,
				Alpha:       alpha,
				Scale:       scale,
			},
			IconPath:   icon.Path,
			BaseWidth:  baseSize.Width,
			BaseHeight: baseSize.Height,
		})
		sizes = append(sizes, size)
	}

	distractors := make([]PlacedObject, 0, distractorCount)
	distractorPool := buildDistractorPool(catalog.Classes, targetClasses)
	for index := 0; index < distractorCount; index++ {
		classAssets := distractorPool[rng.Intn(len(distractorPool))]
		icon := classAssets.Icons[rng.Intn(len(classAssets.Icons))]
		scale := round2(0.84 + rng.Float64()*0.28)
		alpha := round2(0.88 + rng.Float64()*0.08)
		rotationDeg := round1(-16 + rng.Float64()*32)
		baseSize := iconSize(icon, cfg.Canvas.SceneHeight, scale, rng)
		size := rotatedBounds(baseSize.Width, baseSize.Height, rotationDeg)
		distractors = append(distractors, PlacedObject{
			ObjectRecord: export.ObjectRecord{
				Class:       classAssets.Name,
				ClassID:     classAssets.ID,
				RotationDeg: rotationDeg,
				Alpha:       alpha,
				Scale:       scale,
			},
			IconPath:   icon.Path,
			BaseWidth:  baseSize.Width,
			BaseHeight: baseSize.Height,
		})
		sizes = append(sizes, size)
	}

	rects, err := placeObjects(cfg, sizes, rng)
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
		assignRect(object, rects[index])
	}

	plan = SamplePlan{
		Record: export.SampleRecord{
			SampleID:     sampleID,
			CaptchaType:  "group1_multi_icon_match",
			QueryImage:   filepath.ToSlash(filepath.Join("query", sampleID+".png")),
			SceneImage:   filepath.ToSlash(filepath.Join("scene", sampleID+".png")),
			Targets:      recordsFromPlaced(targets),
			Distractors:  recordsFromPlaced(distractors),
			BackgroundID: background.ID,
			StyleID:      "default",
			LabelSource:  "gold",
			SourceBatch:  cfg.Project.BatchID,
			Seed:         sampleSeed,
		},
		BackgroundPath: background.Path,
		Targets:        targets,
		Distractors:    distractors,
	}

	return plan, nil
}

func buildDistractorPool(classes []material.ClassAssets, targets []material.ClassAssets) []material.ClassAssets {
	targetNames := make(map[string]struct{}, len(targets))
	for _, target := range targets {
		targetNames[target.Name] = struct{}{}
	}

	pool := make([]material.ClassAssets, 0, len(classes))
	for _, classAssets := range classes {
		if _, exists := targetNames[classAssets.Name]; exists {
			continue
		}
		pool = append(pool, classAssets)
	}
	if len(pool) == 0 {
		return classes
	}
	return pool
}

func selectUniqueClasses(rng *rand.Rand, classes []material.ClassAssets, count int) []material.ClassAssets {
	permutation := rng.Perm(len(classes))
	selected := make([]material.ClassAssets, 0, count)
	for _, index := range permutation[:count] {
		selected = append(selected, classes[index])
	}
	return selected
}

func iconSize(icon material.IconAsset, sceneHeight int, scale float64, rng *rand.Rand) layout.Size {
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

func placeObjects(cfg config.Config, sizes []layout.Size, rng *rand.Rand) ([]layout.Rect, error) {
	current := append([]layout.Size(nil), sizes...)
	for attempt := 0; attempt < 4; attempt++ {
		rects, err := layout.Place(cfg.Canvas.SceneWidth, cfg.Canvas.SceneHeight, current, rng)
		if err == nil {
			return rects, nil
		}
		for index := range current {
			current[index].Width = max(14, int(math.Round(float64(current[index].Width)*0.9)))
			current[index].Height = max(14, int(math.Round(float64(current[index].Height)*0.9)))
		}
	}
	return nil, fmt.Errorf("could not place sampled objects on the scene canvas")
}

func assignRect(object *PlacedObject, rect layout.Rect) {
	object.BBox = [4]int{rect.X1, rect.Y1, rect.X2, rect.Y2}
	object.Center = [2]int{rect.X1 + rect.Width()/2, rect.Y1 + rect.Height()/2}
}

func recordsFromPlaced(objects []PlacedObject) []export.ObjectRecord {
	records := make([]export.ObjectRecord, 0, len(objects))
	for _, object := range objects {
		records = append(records, object.ObjectRecord)
	}
	return records
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
