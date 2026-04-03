package materialset

import (
	"archive/zip"
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"sinan-captcha/generator/internal/workspace"
)

func TestFetchArchiveImportsZipIntoOfficialMaterials(t *testing.T) {
	workspaceRoot := filepath.Join(t.TempDir(), "workspace")
	state, err := workspace.Ensure(workspaceRoot)
	if err != nil {
		t.Fatalf("ensure workspace: %v", err)
	}

	materialsRoot := createMaterialsPack(t)
	archivePath := createMaterialsArchive(t, materialsRoot)

	result, err := FetchArchive(state, archivePath, "official-pack-v1")
	if err != nil {
		t.Fatalf("fetch archive: %v", err)
	}
	if result.Ref.Scope != "official" {
		t.Fatalf("unexpected scope: %s", result.Ref.Scope)
	}
	if result.Ref.Name != "official-pack-v1" {
		t.Fatalf("unexpected name: %s", result.Ref.Name)
	}
	if result.Validation.ClassCount != 2 {
		t.Fatalf("unexpected class count: %d", result.Validation.ClassCount)
	}
	if _, err := os.Stat(filepath.Join(result.Root, "manifests", "classes.yaml")); err != nil {
		t.Fatalf("expected fetched manifest: %v", err)
	}
}

func createMaterialsPack(t *testing.T) string {
	t.Helper()
	root := filepath.Join(t.TempDir(), "materials")
	writeClassesManifest(t, filepath.Join(root, "manifests", "classes.yaml"))
	writePNG(t, filepath.Join(root, "backgrounds", "bg_001.png"), 320, 180)
	writePNG(t, filepath.Join(root, "icons", "icon_house", "001.png"), 48, 48)
	writePNG(t, filepath.Join(root, "icons", "icon_leaf", "001.png"), 48, 48)
	return root
}

func createMaterialsArchive(t *testing.T, materialsRoot string) string {
	t.Helper()
	archivePath := filepath.Join(t.TempDir(), "materials-pack.zip")
	file, err := os.Create(archivePath)
	if err != nil {
		t.Fatalf("create archive: %v", err)
	}
	defer file.Close()
	writer := zip.NewWriter(file)
	err = filepath.WalkDir(materialsRoot, func(path string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if entry.IsDir() {
			return nil
		}
		relative, err := filepath.Rel(filepath.Dir(materialsRoot), path)
		if err != nil {
			return err
		}
		zipFile, err := writer.Create(filepath.ToSlash(relative))
		if err != nil {
			return err
		}
		content, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		_, err = zipFile.Write(content)
		return err
	})
	if err != nil {
		t.Fatalf("walk materials: %v", err)
	}
	if err := writer.Close(); err != nil {
		t.Fatalf("close archive writer: %v", err)
	}
	return archivePath
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
	output, err := os.Create(path)
	if err != nil {
		t.Fatalf("create png: %v", err)
	}
	defer output.Close()
	if err := png.Encode(output, img); err != nil {
		t.Fatalf("encode png: %v", err)
	}
}
