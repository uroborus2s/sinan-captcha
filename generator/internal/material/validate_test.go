package material

import (
	"image"
	"image/color"
	"image/jpeg"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestValidateRejectsUndecodableBackground(t *testing.T) {
	root := t.TempDir()
	writeManifest(t, root)
	writeInvalidImage(t, filepath.Join(root, "backgrounds", "broken.jpeg"))
	writePNG(t, filepath.Join(root, "icons", "icon_house", "001.png"), 32, 32)

	_, err := Validate(root)
	if err == nil {
		t.Fatal("expected invalid background image to fail validation")
	}
	if !strings.Contains(err.Error(), "broken.jpeg") {
		t.Fatalf("expected error to mention broken background, got %v", err)
	}
}

func TestValidateRejectsUndecodableIcon(t *testing.T) {
	root := t.TempDir()
	writeManifest(t, root)
	writePNG(t, filepath.Join(root, "backgrounds", "bg.png"), 320, 180)
	writeInvalidImage(t, filepath.Join(root, "icons", "icon_house", "broken.png"))

	_, err := Validate(root)
	if err == nil {
		t.Fatal("expected invalid icon image to fail validation")
	}
	if !strings.Contains(err.Error(), "broken.png") {
		t.Fatalf("expected error to mention broken icon, got %v", err)
	}
}

func TestValidateRejectsTruncatedJPEGBackground(t *testing.T) {
	root := t.TempDir()
	writeManifest(t, root)
	writeTruncatedJPEG(t, filepath.Join(root, "backgrounds", "truncated.jpeg"), 320, 180)
	writePNG(t, filepath.Join(root, "icons", "icon_house", "001.png"), 32, 32)

	_, err := Validate(root)
	if err == nil {
		t.Fatal("expected truncated JPEG background to fail validation")
	}
	if !strings.Contains(err.Error(), "truncated.jpeg") {
		t.Fatalf("expected error to mention truncated background, got %v", err)
	}
}

func writeManifest(t *testing.T, root string) {
	t.Helper()
	manifestPath := filepath.Join(root, "manifests", "classes.yaml")
	if err := os.MkdirAll(filepath.Dir(manifestPath), 0o755); err != nil {
		t.Fatalf("mkdir manifests: %v", err)
	}
	content := "classes:\n  - id: 0\n    name: icon_house\n    zh_name: 房子\n"
	if err := os.WriteFile(manifestPath, []byte(content), 0o644); err != nil {
		t.Fatalf("write manifest: %v", err)
	}
}

func writeInvalidImage(t *testing.T, path string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir invalid image dir: %v", err)
	}
	if err := os.WriteFile(path, []byte("not-an-image"), 0o644); err != nil {
		t.Fatalf("write invalid image: %v", err)
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
			img.SetRGBA(x, y, color.RGBA{R: uint8(40 + x%30), G: uint8(80 + y%30), B: 140, A: 255})
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

func writeTruncatedJPEG(t *testing.T, path string, width int, height int) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir jpeg dir: %v", err)
	}

	img := image.NewRGBA(image.Rect(0, 0, width, height))
	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			img.SetRGBA(x, y, color.RGBA{R: uint8(10 + x%80), G: uint8(40 + y%80), B: 200, A: 255})
		}
	}

	file, err := os.Create(path)
	if err != nil {
		t.Fatalf("create jpeg: %v", err)
	}
	if err := jpeg.Encode(file, img, &jpeg.Options{Quality: 85}); err != nil {
		file.Close()
		t.Fatalf("encode jpeg: %v", err)
	}
	if err := file.Close(); err != nil {
		t.Fatalf("close jpeg: %v", err)
	}

	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read jpeg: %v", err)
	}
	if len(content) < 32 {
		t.Fatalf("encoded jpeg too small to truncate: %d", len(content))
	}
	content = content[:len(content)-24]
	if err := os.WriteFile(path, content, 0o644); err != nil {
		t.Fatalf("truncate jpeg: %v", err)
	}
}
