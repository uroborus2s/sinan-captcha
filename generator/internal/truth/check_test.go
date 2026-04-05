package truth

import (
	"testing"

	"sinan-captcha/generator/internal/backend"
	"sinan-captcha/generator/internal/config"
	"sinan-captcha/generator/internal/export"
)

func TestValidateClickTruth(t *testing.T) {
	record := export.SampleRecord{
		SampleID:    "g1_000001",
		CaptchaType: "group1_multi_icon_match",
		Mode:        "click",
		Backend:     "native",
		QueryImage:  "query/g1_000001.png",
		SceneImage:  "scene/g1_000001.png",
		QueryTargets: []export.ObjectRecord{
			{
				Order:   1,
				Class:   "icon_house",
				ClassID: 0,
				BBox:    [4]int{6, 6, 24, 24},
				Center:  [2]int{15, 15},
			},
		},
		SceneTargets: []export.ObjectRecord{
			{
				Order:   1,
				Class:   "icon_house",
				ClassID: 0,
				BBox:    [4]int{10, 10, 30, 28},
				Center:  [2]int{20, 19},
			},
		},
		Distractors: []export.ObjectRecord{
			{
				Class:   "icon_leaf",
				ClassID: 1,
				BBox:    [4]int{40, 10, 60, 28},
				Center:  [2]int{50, 19},
			},
		},
		LabelSource: "gold",
		SourceBatch: "batch_0001",
		Seed:        1,
	}

	checks, err := Validate(
		record,
		backend.Spec{Mode: backend.ModeClick, Backend: backend.KindNative},
		config.CanvasConfig{SceneWidth: 100, SceneHeight: 50, QueryWidth: 36, QueryHeight: 36},
		func() (export.SampleRecord, error) { return record, nil },
	)
	if err != nil {
		t.Fatalf("expected click truth validation to pass: %v", err)
	}
	if checks.Consistency != "passed" || checks.Replay != "passed" || checks.NegativeCheck != "passed" {
		t.Fatalf("unexpected truth checks: %+v", checks)
	}
}

func TestValidateSlideTruth(t *testing.T) {
	offsetX := 72
	offsetY := 0
	tileBBox := [4]int{0, 24, 44, 60}
	record := export.SampleRecord{
		SampleID:    "g2_000001",
		CaptchaType: "group2_slider_gap_locate",
		Mode:        "slide",
		Backend:     "native",
		MasterImage: "master/g2_000001.png",
		TileImage:   "tile/g2_000001.png",
		TargetGap: &export.ObjectRecord{
			Class:   "slider_gap",
			ClassID: 0,
			BBox:    [4]int{72, 24, 116, 60},
			Center:  [2]int{94, 42},
		},
		TileBBox:    &tileBBox,
		OffsetX:     &offsetX,
		OffsetY:     &offsetY,
		LabelSource: "gold",
		SourceBatch: "batch_0001",
		Seed:        2,
	}

	checks, err := Validate(
		record,
		backend.Spec{Mode: backend.ModeSlide, Backend: backend.KindNative},
		config.CanvasConfig{SceneWidth: 180, SceneHeight: 100},
		func() (export.SampleRecord, error) { return record, nil },
	)
	if err != nil {
		t.Fatalf("expected slide truth validation to pass: %v", err)
	}
	if checks.Consistency != "passed" || checks.Replay != "passed" || checks.NegativeCheck != "passed" {
		t.Fatalf("unexpected truth checks: %+v", checks)
	}
}
