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

	assertFileExists(t, filepath.Join(trainingDir, "dataset.yaml"))
	assertDirHasFiles(t, filepath.Join(trainingDir, "images", "train"))
	assertDirHasFiles(t, filepath.Join(trainingDir, "labels", "train"))
	assertFileExists(t, filepath.Join(trainingDir, ".sinan", "job.json"))
	assertFileExists(t, filepath.Join(trainingDir, ".sinan", "manifest.json"))
	assertDirHasFiles(t, filepath.Join(trainingDir, ".sinan", "raw", filepath.Base(result.BatchRoot), "scene"))
	assertDatasetYAMLHasNoPathField(t, filepath.Join(trainingDir, "dataset.yaml"))
	if !strings.Contains(result.DatasetConfig, filepath.Join(trainingDir, "dataset.yaml")) {
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

func createMaterialsPack(t *testing.T) string {
	t.Helper()
	root := filepath.Join(t.TempDir(), "materials")
	writeClassesManifest(t, filepath.Join(root, "manifests", "classes.yaml"))
	writePNG(t, filepath.Join(root, "backgrounds", "bg_001.png"), 320, 180)
	writePNG(t, filepath.Join(root, "backgrounds", "bg_002.png"), 320, 180)
	writeMaskIconPNG(t, filepath.Join(root, "icons", "icon_house", "001.png"), 48, 48)
	writeMaskIconPNG(t, filepath.Join(root, "icons", "icon_leaf", "001.png"), 48, 48)
	return root
}

func writeClassesManifest(t *testing.T, path string) {
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

func assertDatasetYAMLHasNoPathField(t *testing.T, path string) {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read dataset yaml %s: %v", path, err)
	}
	text := string(content)
	if strings.Contains(text, "\npath:") || strings.HasPrefix(text, "path:") {
		t.Fatalf("dataset yaml should not contain path field:\n%s", text)
	}
	if !strings.Contains(text, "train: images/train") {
		t.Fatalf("dataset yaml missing train path:\n%s", text)
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
