package truth

import (
	"fmt"
	"reflect"

	"sinan-captcha/generator/internal/backend"
	"sinan-captcha/generator/internal/config"
	"sinan-captcha/generator/internal/export"
)

func Validate(
	record export.SampleRecord,
	spec backend.Spec,
	canvas config.CanvasConfig,
	replay func() (export.SampleRecord, error),
) (*export.TruthChecks, error) {
	if err := CheckConsistency(record, spec, canvas); err != nil {
		return nil, fmt.Errorf("consistency check failed: %w", err)
	}

	replayed, err := replay()
	if err != nil {
		return nil, fmt.Errorf("replay check failed: %w", err)
	}
	if !reflect.DeepEqual(normalize(record), normalize(replayed)) {
		return nil, fmt.Errorf("replay output does not match original truth")
	}

	if err := CheckNegative(record, spec, canvas); err != nil {
		return nil, fmt.Errorf("negative check failed: %w", err)
	}

	return &export.TruthChecks{
		Consistency:   "passed",
		Replay:        "passed",
		NegativeCheck: "passed",
	}, nil
}

func CheckConsistency(record export.SampleRecord, spec backend.Spec, canvas config.CanvasConfig) error {
	switch {
	case record.SampleID == "":
		return fmt.Errorf("sample_id is required")
	case record.Mode != string(spec.Mode):
		return fmt.Errorf("record mode %q does not match requested mode %q", record.Mode, spec.Mode)
	case record.Backend != string(spec.Backend):
		return fmt.Errorf("record backend %q does not match requested backend %q", record.Backend, spec.Backend)
	case record.LabelSource != "gold":
		return fmt.Errorf("label_source must be gold")
	case record.SourceBatch == "":
		return fmt.Errorf("source_batch is required")
	}

	switch spec.Mode {
	case backend.ModeClick:
		if record.QueryImage == "" || record.SceneImage == "" {
			return fmt.Errorf("click mode requires query_image and scene_image")
		}
		if len(record.SceneTargets) == 0 {
			return fmt.Errorf("click mode requires at least one scene target")
		}
		if len(record.QueryTargets) != len(record.SceneTargets) {
			return fmt.Errorf("query_targets and scene_targets must have the same length")
		}
		for index, target := range record.QueryTargets {
			if target.Order != index+1 {
				return fmt.Errorf("query target order must be continuous starting at 1")
			}
			if err := validateObject(target, canvas.QueryWidth, canvas.QueryHeight); err != nil {
				return fmt.Errorf("query target %d: %w", index, err)
			}
			sceneTarget := record.SceneTargets[index]
			if !sameGroup1Identity(target, sceneTarget) || target.Order != sceneTarget.Order {
				return fmt.Errorf("query target %d does not align with scene target definition", index)
			}
		}
		for index, target := range record.SceneTargets {
			if target.Order != index+1 {
				return fmt.Errorf("scene target order must be continuous starting at 1")
			}
			if err := validateObject(target, canvas.SceneWidth, canvas.SceneHeight); err != nil {
				return fmt.Errorf("scene target %d: %w", index, err)
			}
		}
		for index, distractor := range record.Distractors {
			if err := validateObject(distractor, canvas.SceneWidth, canvas.SceneHeight); err != nil {
				return fmt.Errorf("distractor %d: %w", index, err)
			}
		}
	case backend.ModeSlide:
		if record.MasterImage == "" || record.TileImage == "" {
			return fmt.Errorf("slide mode requires master_image and tile_image")
		}
		if record.TargetGap == nil || record.TileBBox == nil || record.OffsetX == nil || record.OffsetY == nil {
			return fmt.Errorf("slide mode requires target_gap, tile_bbox, offset_x and offset_y")
		}
		if err := validateObject(*record.TargetGap, canvas.SceneWidth, canvas.SceneHeight); err != nil {
			return fmt.Errorf("target_gap: %w", err)
		}
		if err := validateBBox(*record.TileBBox, canvas.SceneWidth, canvas.SceneHeight); err != nil {
			return fmt.Errorf("tile_bbox: %w", err)
		}
		if expected := record.TargetGap.BBox[0] - record.TileBBox[0]; expected != *record.OffsetX {
			return fmt.Errorf("offset_x does not match target gap geometry")
		}
		if expected := record.TargetGap.BBox[1] - record.TileBBox[1]; expected != *record.OffsetY {
			return fmt.Errorf("offset_y does not match target gap geometry")
		}
	default:
		return fmt.Errorf("unsupported mode: %s", spec.Mode)
	}

	return nil
}

func CheckNegative(record export.SampleRecord, spec backend.Spec, canvas config.CanvasConfig) error {
	switch spec.Mode {
	case backend.ModeClick:
		if !verifyClick(record, clickAnswers(record)) {
			return fmt.Errorf("positive click verification did not pass")
		}
		negative := clickAnswers(record)
		target := record.SceneTargets[0]
		switch {
		case target.BBox[2]+1 < canvas.SceneWidth:
			negative[0][0] = target.BBox[2] + 1
		case target.BBox[0]-1 >= 0:
			negative[0][0] = target.BBox[0] - 1
		default:
			return fmt.Errorf("could not construct a negative click answer")
		}
		if verifyClick(record, negative) {
			return fmt.Errorf("negative click answer unexpectedly passed")
		}
	case backend.ModeSlide:
		if !verifySlide(record, *record.OffsetX, *record.OffsetY) {
			return fmt.Errorf("positive slide verification did not pass")
		}
		if verifySlide(record, *record.OffsetX+1, *record.OffsetY) {
			return fmt.Errorf("negative slide answer unexpectedly passed")
		}
	default:
		return fmt.Errorf("unsupported mode: %s", spec.Mode)
	}
	return nil
}

func validateObject(object export.ObjectRecord, width int, height int) error {
	if object.Class == "" {
		return fmt.Errorf("class is required")
	}
	if err := validateBBox(object.BBox, width, height); err != nil {
		return err
	}
	centerX := object.Center[0]
	centerY := object.Center[1]
	if centerX < object.BBox[0] || centerX >= object.BBox[2] || centerY < object.BBox[1] || centerY >= object.BBox[3] {
		return fmt.Errorf("center is outside bbox")
	}
	return nil
}

func validateBBox(bbox [4]int, sceneWidth int, sceneHeight int) error {
	x1, y1, x2, y2 := bbox[0], bbox[1], bbox[2], bbox[3]
	switch {
	case x1 < 0 || y1 < 0:
		return fmt.Errorf("bbox must stay within positive canvas coordinates")
	case x2 <= x1 || y2 <= y1:
		return fmt.Errorf("bbox must have positive size")
	case x2 > sceneWidth || y2 > sceneHeight:
		return fmt.Errorf("bbox exceeds scene bounds")
	default:
		return nil
	}
}

func clickAnswers(record export.SampleRecord) [][2]int {
	answers := make([][2]int, 0, len(record.SceneTargets))
	for _, target := range record.SceneTargets {
		answers = append(answers, target.Center)
	}
	return answers
}

func verifyClick(record export.SampleRecord, answers [][2]int) bool {
	if len(answers) != len(record.SceneTargets) {
		return false
	}
	for index, answer := range answers {
		target := record.SceneTargets[index]
		if answer[0] < target.BBox[0] || answer[0] >= target.BBox[2] || answer[1] < target.BBox[1] || answer[1] >= target.BBox[3] {
			return false
		}
	}
	return true
}

func verifySlide(record export.SampleRecord, offsetX int, offsetY int) bool {
	if record.OffsetX == nil || record.OffsetY == nil {
		return false
	}
	return offsetX == *record.OffsetX && offsetY == *record.OffsetY
}

func normalize(record export.SampleRecord) export.SampleRecord {
	record.TruthChecks = nil
	return record
}

func sameGroup1Identity(left export.ObjectRecord, right export.ObjectRecord) bool {
	if left.AssetID != "" || right.AssetID != "" || left.TemplateID != "" || right.TemplateID != "" || left.VariantID != "" || right.VariantID != "" {
		return left.AssetID == right.AssetID && left.TemplateID == right.TemplateID && left.VariantID == right.VariantID
	}
	return left.Class == right.Class && left.ClassID == right.ClassID
}
