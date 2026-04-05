package app

import (
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"sinan-captcha/generator/internal/config"
	"sinan-captcha/generator/internal/workspace"
)

func TestMakeDatasetBuildsGroup1TrainingDirectory(t *testing.T) {
	workspaceRoot := filepath.Join(t.TempDir(), "workspace")
	materialsRoot := createMaterialsPack(t)
	trainingDir := filepath.Join(t.TempDir(), "train-group1")

	result, err := MakeDataset(MakeDatasetRequest{
		Task:           "group1",
		Preset:         "smoke",
		WorkspaceRoot:  workspaceRoot,
		DatasetDir:     trainingDir,
		MaterialSource: materialsRoot,
	})
	if err != nil {
		t.Fatalf("make dataset: %v", err)
	}

	assertFileExists(t, filepath.Join(trainingDir, "dataset.json"))
	assertDirHasFiles(t, filepath.Join(trainingDir, "scene-yolo", "images", "train"))
	assertDirHasFiles(t, filepath.Join(trainingDir, "scene-yolo", "labels", "train"))
	assertDirHasFiles(t, filepath.Join(trainingDir, "query-yolo", "images", "train"))
	assertDirHasFiles(t, filepath.Join(trainingDir, "query-yolo", "labels", "train"))
	assertFileExists(t, filepath.Join(trainingDir, "splits", "train.jsonl"))
	assertFileExists(t, filepath.Join(trainingDir, "splits", "val.jsonl"))
	assertFileExists(t, filepath.Join(trainingDir, "splits", "test.jsonl"))
	assertFileExists(t, filepath.Join(trainingDir, ".sinan", "job.json"))
	assertFileExists(t, filepath.Join(trainingDir, ".sinan", "manifest.json"))
	assertDirHasFiles(t, filepath.Join(trainingDir, ".sinan", "raw", filepath.Base(result.BatchRoot), "scene"))
	assertDirHasFiles(t, filepath.Join(trainingDir, ".sinan", "raw", filepath.Base(result.BatchRoot), "query"))
	assertGroup1DatasetJSONReferencesPipelineArtifacts(t, filepath.Join(trainingDir, "dataset.json"))
	if !strings.Contains(result.DatasetConfig, filepath.Join(trainingDir, "dataset.json")) {
		t.Fatalf("unexpected dataset config path: %s", result.DatasetConfig)
	}
}

func TestMakeDatasetBuildsGroup2TrainingDirectory(t *testing.T) {
	workspaceRoot := filepath.Join(t.TempDir(), "workspace")
	materialsRoot := createMaterialsPack(t)
	trainingDir := filepath.Join(t.TempDir(), "train-group2")

	result, err := MakeDataset(MakeDatasetRequest{
		Task:           "group2",
		Preset:         "smoke",
		WorkspaceRoot:  workspaceRoot,
		DatasetDir:     trainingDir,
		MaterialSource: materialsRoot,
	})
	if err != nil {
		t.Fatalf("make dataset: %v", err)
	}

	assertFileExists(t, filepath.Join(trainingDir, "dataset.json"))
	assertDirHasFiles(t, filepath.Join(trainingDir, "master", "train"))
	assertDirHasFiles(t, filepath.Join(trainingDir, "tile", "train"))
	assertFileExists(t, filepath.Join(trainingDir, "splits", "train.jsonl"))
	assertFileExists(t, filepath.Join(trainingDir, "splits", "val.jsonl"))
	assertFileExists(t, filepath.Join(trainingDir, "splits", "test.jsonl"))
	assertDirHasFiles(t, filepath.Join(trainingDir, ".sinan", "raw", filepath.Base(result.BatchRoot), "master"))
	assertDirHasFiles(t, filepath.Join(trainingDir, ".sinan", "raw", filepath.Base(result.BatchRoot), "tile"))
	assertDatasetJSONReferencesPairedSplits(t, filepath.Join(trainingDir, "dataset.json"))
	if !strings.Contains(result.DatasetConfig, filepath.Join(trainingDir, "dataset.json")) {
		t.Fatalf("unexpected dataset config path: %s", result.DatasetConfig)
	}
}

func TestMakeDatasetUsesWorkspacePresetOverride(t *testing.T) {
	workspaceRoot := filepath.Join(t.TempDir(), "workspace")
	materialsRoot := createMaterialsPack(t)
	trainingDir := filepath.Join(t.TempDir(), "train-group1-hard")

	state, err := workspace.Ensure(workspaceRoot)
	if err != nil {
		t.Fatalf("ensure workspace: %v", err)
	}
	override := config.Config{
		Project: config.ProjectConfig{
			DatasetName: "sinan_group1_hard",
			Split:       "train",
			SampleCount: 3,
			BatchID:     "group1_hd_0001",
			Seed:        20260404,
		},
		Canvas: config.CanvasConfig{
			SceneWidth:  300,
			SceneHeight: 150,
			QueryWidth:  120,
			QueryHeight: 36,
		},
		Sampling: config.SamplingConfig{
			TargetCountMin:     2,
			TargetCountMax:     3,
			DistractorCountMin: 2,
			DistractorCountMax: 4,
		},
		Slide: config.SlideConfig{
			GapWidth:          52,
			GapHeight:         52,
			MaxVerticalJitter: 4,
		},
		Effects: config.EffectsConfig{
			Common: config.CommonEffectsConfig{
				SceneVeilStrength:       1.4,
				BackgroundBlurRadiusMin: 1,
				BackgroundBlurRadiusMax: 1,
			},
			Click: config.ClickEffectsConfig{
				IconShadowAlphaMin:    0.24,
				IconShadowAlphaMax:    0.24,
				IconShadowOffsetXMin:  2,
				IconShadowOffsetXMax:  2,
				IconShadowOffsetYMin:  3,
				IconShadowOffsetYMax:  3,
				IconEdgeBlurRadiusMin: 1,
				IconEdgeBlurRadiusMax: 1,
			},
		},
	}
	overridePath := filepath.Join(state.Layout.PresetsDir, "group1.hard.yaml")
	if err := os.WriteFile(overridePath, []byte(config.Format(override)), 0o644); err != nil {
		t.Fatalf("write override preset: %v", err)
	}

	result, err := MakeDataset(MakeDatasetRequest{
		Task:           "group1",
		Preset:         "hard",
		WorkspaceRoot:  workspaceRoot,
		DatasetDir:     trainingDir,
		MaterialSource: materialsRoot,
	})
	if err != nil {
		t.Fatalf("make dataset with workspace override: %v", err)
	}

	if got, want := result.Generated, 3; got != want {
		t.Fatalf("expected workspace override sample count to apply, got %d want %d", got, want)
	}
}

func TestMakeDatasetAppliesRuntimeOverrideFile(t *testing.T) {
	workspaceRoot := filepath.Join(t.TempDir(), "workspace")
	materialsRoot := createMaterialsPack(t)
	trainingDir := filepath.Join(t.TempDir(), "train-group1-override")
	overrideFile := filepath.Join(t.TempDir(), "generator-override.json")
	overridePayload := `{
  "project": {"sample_count": 3},
  "sampling": {
    "target_count_min": 2,
    "target_count_max": 2,
    "distractor_count_min": 0,
    "distractor_count_max": 0
  },
  "effects": {
    "common": {
      "scene_veil_strength": 1.45,
      "background_blur_radius_min": 1,
      "background_blur_radius_max": 2
    },
    "click": {
      "icon_shadow_alpha_min": 0.28,
      "icon_shadow_alpha_max": 0.36,
      "icon_shadow_offset_x_min": 2,
      "icon_shadow_offset_x_max": 3,
      "icon_shadow_offset_y_min": 3,
      "icon_shadow_offset_y_max": 4,
      "icon_edge_blur_radius_min": 1,
      "icon_edge_blur_radius_max": 2
    }
  }
}`
	if err := os.WriteFile(overrideFile, []byte(overridePayload), 0o644); err != nil {
		t.Fatalf("write runtime override file: %v", err)
	}

	result, err := MakeDataset(MakeDatasetRequest{
		Task:           "group1",
		Preset:         "smoke",
		WorkspaceRoot:  workspaceRoot,
		DatasetDir:     trainingDir,
		MaterialSource: materialsRoot,
		OverrideFile:   overrideFile,
	})
	if err != nil {
		t.Fatalf("make dataset with runtime override: %v", err)
	}

	if got, want := result.Generated, 3; got != want {
		t.Fatalf("expected runtime override sample count to apply, got %d want %d", got, want)
	}
}

func TestMakeDatasetBuildsGroup1FromGroup1OnlyMaterials(t *testing.T) {
	workspaceRoot := filepath.Join(t.TempDir(), "workspace")
	materialsRoot := createGroup1OnlyMaterialsPack(t)
	trainingDir := filepath.Join(t.TempDir(), "train-group1")

	result, err := MakeDataset(MakeDatasetRequest{
		Task:           "group1",
		Preset:         "smoke",
		WorkspaceRoot:  workspaceRoot,
		DatasetDir:     trainingDir,
		MaterialSource: materialsRoot,
	})
	if err != nil {
		t.Fatalf("make dataset from group1-only materials: %v", err)
	}

	assertFileExists(t, filepath.Join(trainingDir, "dataset.json"))
	if got, want := result.Generated, 20; got != want {
		t.Fatalf("expected smoke preset to generate %d samples, got %d", want, got)
	}
}

func TestMakeDatasetBuildsGroup2FromGroup2OnlyMaterials(t *testing.T) {
	workspaceRoot := filepath.Join(t.TempDir(), "workspace")
	materialsRoot := createGroup2OnlyMaterialsPack(t)
	trainingDir := filepath.Join(t.TempDir(), "train-group2")

	result, err := MakeDataset(MakeDatasetRequest{
		Task:           "group2",
		Preset:         "smoke",
		WorkspaceRoot:  workspaceRoot,
		DatasetDir:     trainingDir,
		MaterialSource: materialsRoot,
	})
	if err != nil {
		t.Fatalf("make dataset from group2-only materials: %v", err)
	}

	assertFileExists(t, filepath.Join(trainingDir, "dataset.json"))
	if got, want := result.Generated, 20; got != want {
		t.Fatalf("expected smoke preset to generate %d samples, got %d", want, got)
	}
}

func createMaterialsPack(t *testing.T) string {
	t.Helper()
	root := filepath.Join(t.TempDir(), "materials")
	writeMaterialsManifest(t, filepath.Join(root, "manifests", "materials.yaml"))
	writeGroup1Manifest(t, filepath.Join(root, "manifests", "group1.classes.yaml"))
	writeGroup2Manifest(t, filepath.Join(root, "manifests", "group2.shapes.yaml"))
	writePNG(t, filepath.Join(root, "backgrounds", "bg_001.png"), 320, 180)
	writePNG(t, filepath.Join(root, "backgrounds", "bg_002.png"), 320, 180)
	writeMaskIconPNG(t, filepath.Join(root, "group1", "icons", "icon_house", "001.png"), 48, 48)
	writeMaskIconPNG(t, filepath.Join(root, "group1", "icons", "icon_leaf", "001.png"), 48, 48)
	writeMaskIconPNG(t, filepath.Join(root, "group2", "shapes", "shape_ticket", "001.png"), 48, 48)
	writeMaskIconPNG(t, filepath.Join(root, "group2", "shapes", "shape_cloud", "001.png"), 48, 48)
	return root
}

func createGroup1OnlyMaterialsPack(t *testing.T) string {
	t.Helper()
	root := filepath.Join(t.TempDir(), "materials-group1")
	writeMaterialsManifest(t, filepath.Join(root, "manifests", "materials.yaml"))
	writeGroup1Manifest(t, filepath.Join(root, "manifests", "group1.classes.yaml"))
	writePNG(t, filepath.Join(root, "backgrounds", "bg_001.png"), 320, 180)
	writePNG(t, filepath.Join(root, "backgrounds", "bg_002.png"), 320, 180)
	writeMaskIconPNG(t, filepath.Join(root, "group1", "icons", "icon_house", "001.png"), 48, 48)
	writeMaskIconPNG(t, filepath.Join(root, "group1", "icons", "icon_leaf", "001.png"), 48, 48)
	return root
}

func createGroup2OnlyMaterialsPack(t *testing.T) string {
	t.Helper()
	root := filepath.Join(t.TempDir(), "materials-group2")
	writeMaterialsManifest(t, filepath.Join(root, "manifests", "materials.yaml"))
	writeGroup2Manifest(t, filepath.Join(root, "manifests", "group2.shapes.yaml"))
	writePNG(t, filepath.Join(root, "backgrounds", "bg_001.png"), 320, 180)
	writePNG(t, filepath.Join(root, "backgrounds", "bg_002.png"), 320, 180)
	writeMaskIconPNG(t, filepath.Join(root, "group2", "shapes", "shape_ticket", "001.png"), 48, 48)
	writeMaskIconPNG(t, filepath.Join(root, "group2", "shapes", "shape_cloud", "001.png"), 48, 48)
	return root
}

func writeMaterialsManifest(t *testing.T, path string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir manifest dir: %v", err)
	}
	content := "schema_version: 2\n"
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write manifest: %v", err)
	}
}

func writeGroup1Manifest(t *testing.T, path string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir manifest dir: %v", err)
	}
	content := strings.Join([]string{
		"classes:",
		"  - id: 0",
		"    name: icon_house",
		"    zh_name: 房子",
		"  - id: 1",
		"    name: icon_leaf",
		"    zh_name: 叶子",
		"",
	}, "\n")
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write manifest: %v", err)
	}
}

func writeGroup2Manifest(t *testing.T, path string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir manifest dir: %v", err)
	}
	content := strings.Join([]string{
		"shapes:",
		"  - id: 0",
		"    name: shape_ticket",
		"    zh_name: 票形缺口",
		"  - id: 1",
		"    name: shape_cloud",
		"    zh_name: 云形缺口",
		"",
	}, "\n")
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write manifest: %v", err)
	}
}

func writePNG(t *testing.T, path string, width int, height int) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir png dir: %v", err)
	}
	img := image.NewRGBA(image.Rect(0, 0, width, height))
	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			img.SetRGBA(x, y, color.RGBA{R: uint8(30 + x%80), G: uint8(60 + y%80), B: 180, A: 255})
		}
	}
	file, err := os.Create(path)
	if err != nil {
		t.Fatalf("create png: %v", err)
	}
	defer file.Close()
	if err := png.Encode(file, img); err != nil {
		t.Fatalf("encode png: %v", err)
	}
}

func writeMaskIconPNG(t *testing.T, path string, width int, height int) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir png dir: %v", err)
	}
	img := image.NewRGBA(image.Rect(0, 0, width, height))
	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			alpha := uint8(0)
			if x > 4 && x < width/3 && y > height/4 && y < height-height/4 {
				alpha = 255
			}
			if x >= width/3 {
				top := height/2 - (x-width/3)/2
				bottom := height/2 + (x-width/3)/3
				if y >= top && y <= bottom {
					alpha = 255
				}
			}
			if alpha > 0 {
				img.SetRGBA(x, y, color.RGBA{R: 255, G: 255, B: 255, A: alpha})
			}
		}
	}
	file, err := os.Create(path)
	if err != nil {
		t.Fatalf("create png: %v", err)
	}
	defer file.Close()
	if err := png.Encode(file, img); err != nil {
		t.Fatalf("encode png: %v", err)
	}
}

func assertFileExists(t *testing.T, path string) {
	t.Helper()
	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("expected file %s: %v", path, err)
	}
	if info.IsDir() {
		t.Fatalf("expected %s to be a file", path)
	}
}

func assertDirHasFiles(t *testing.T, path string) {
	t.Helper()
	entries, err := os.ReadDir(path)
	if err != nil {
		t.Fatalf("expected directory %s: %v", path, err)
	}
	if len(entries) == 0 {
		t.Fatalf("expected directory %s to contain files", path)
	}
}

func assertGroup1DatasetJSONReferencesPipelineArtifacts(t *testing.T, path string) {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read dataset json %s: %v", path, err)
	}
	text := string(content)
	for _, expected := range []string{
		`"task": "group1"`,
		`"format": "sinan.group1.pipeline.v1"`,
		`"scene_detector"`,
		`"scene-yolo/dataset.yaml"`,
		`"query_parser"`,
		`"query-yolo/dataset.yaml"`,
		`"train": "splits/train.jsonl"`,
		`"strategy": "ordered_class_match_v1"`,
	} {
		if !strings.Contains(text, expected) {
			t.Fatalf("dataset json missing %s:\n%s", expected, text)
		}
	}
}

func assertDatasetJSONReferencesPairedSplits(t *testing.T, path string) {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read dataset json %s: %v", path, err)
	}
	text := string(content)
	for _, expected := range []string{
		"\"format\": \"sinan.group2.paired.v1\"",
		"\"train\": \"splits/train.jsonl\"",
		"\"val\": \"splits/val.jsonl\"",
		"\"test\": \"splits/test.jsonl\"",
	} {
		if !strings.Contains(text, expected) {
			t.Fatalf("dataset json missing %s:\n%s", expected, text)
		}
	}
}
