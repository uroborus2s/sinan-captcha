package app

import (
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"
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
	if !strings.Contains(result.DatasetYAML, filepath.Join(trainingDir, "dataset.yaml")) {
		t.Fatalf("unexpected dataset yaml path: %s", result.DatasetYAML)
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

	assertFileExists(t, filepath.Join(trainingDir, "dataset.yaml"))
	assertDirHasFiles(t, filepath.Join(trainingDir, "images", "train"))
	assertDirHasFiles(t, filepath.Join(trainingDir, "labels", "train"))
	assertDirHasFiles(t, filepath.Join(trainingDir, ".sinan", "raw", filepath.Base(result.BatchRoot), "master"))
	assertDirHasFiles(t, filepath.Join(trainingDir, ".sinan", "raw", filepath.Base(result.BatchRoot), "tile"))
}

func createMaterialsPack(t *testing.T) string {
	t.Helper()
	root := filepath.Join(t.TempDir(), "materials")
	writeClassesManifest(t, filepath.Join(root, "manifests", "classes.yaml"))
	writePNG(t, filepath.Join(root, "backgrounds", "bg_001.png"), 320, 180)
	writePNG(t, filepath.Join(root, "backgrounds", "bg_002.png"), 320, 180)
	writePNG(t, filepath.Join(root, "icons", "icon_house", "001.png"), 48, 48)
	writePNG(t, filepath.Join(root, "icons", "icon_leaf", "001.png"), 48, 48)
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
