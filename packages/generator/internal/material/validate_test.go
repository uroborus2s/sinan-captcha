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
	writeMaterialsManifest(t, root)
	writeGroup1TemplatesManifest(t, root)
	writeGroup2Manifest(t, root)
	writeInvalidImage(t, filepath.Join(root, "backgrounds", "broken.jpeg"))
	writePNG(t, filepath.Join(root, "group1", "icons", "tpl_house", "var_real_cluster_040_01.png"), 32, 32)
	writePNG(t, filepath.Join(root, "group2", "shapes", "shape_ticket", "001.png"), 32, 32)

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
	writeMaterialsManifest(t, root)
	writeGroup1TemplatesManifest(t, root)
	writeGroup2Manifest(t, root)
	writePNG(t, filepath.Join(root, "backgrounds", "bg.png"), 320, 180)
	writeInvalidImage(t, filepath.Join(root, "group1", "icons", "tpl_house", "var_real_cluster_040_01.png"))
	writePNG(t, filepath.Join(root, "group2", "shapes", "shape_ticket", "001.png"), 32, 32)

	_, err := Validate(root)
	if err == nil {
		t.Fatal("expected invalid icon image to fail validation")
	}
	if !strings.Contains(err.Error(), "tpl_house/var_real_cluster_040_01") {
		t.Fatalf("expected error to mention broken icon, got %v", err)
	}
}

func TestValidateRejectsTruncatedJPEGBackground(t *testing.T) {
	root := t.TempDir()
	writeMaterialsManifest(t, root)
	writeGroup1TemplatesManifest(t, root)
	writeGroup2Manifest(t, root)
	writeTruncatedJPEG(t, filepath.Join(root, "backgrounds", "truncated.jpeg"), 320, 180)
	writePNG(t, filepath.Join(root, "group1", "icons", "tpl_house", "var_real_cluster_040_01.png"), 32, 32)
	writePNG(t, filepath.Join(root, "group2", "shapes", "shape_ticket", "001.png"), 32, 32)

	_, err := Validate(root)
	if err == nil {
		t.Fatal("expected truncated JPEG background to fail validation")
	}
	if !strings.Contains(err.Error(), "truncated.jpeg") {
		t.Fatalf("expected error to mention truncated background, got %v", err)
	}
}

func TestValidateRejectsMissingGroup2Shapes(t *testing.T) {
	root := t.TempDir()
	writeMaterialsManifest(t, root)
	writeGroup1TemplatesManifest(t, root)
	writeGroup2Manifest(t, root)
	writePNG(t, filepath.Join(root, "backgrounds", "bg.png"), 320, 180)
	writePNG(t, filepath.Join(root, "group1", "icons", "tpl_house", "var_real_cluster_040_01.png"), 32, 32)

	_, err := Validate(root)
	if err == nil {
		t.Fatal("expected missing group2 shapes to fail validation")
	}
	if !strings.Contains(err.Error(), "group2 shape images") {
		t.Fatalf("expected group2 shape validation error, got %v", err)
	}
}

func TestValidateForTaskAcceptsGroup1OnlyMaterials(t *testing.T) {
	root := t.TempDir()
	writeMaterialsManifest(t, root)
	writeGroup1TemplatesManifest(t, root)
	writePNG(t, filepath.Join(root, "backgrounds", "bg.png"), 320, 180)
	writePNG(t, filepath.Join(root, "group1", "icons", "tpl_house", "var_real_cluster_040_01.png"), 32, 32)

	summary, err := ValidateForTask(root, "group1")
	if err != nil {
		t.Fatalf("validate group1-only materials: %v", err)
	}
	if summary.Group1TemplateCount != 1 {
		t.Fatalf("expected 1 group1 template, got %d", summary.Group1TemplateCount)
	}
	if summary.Group1VariantCount != 1 {
		t.Fatalf("expected 1 group1 variant, got %d", summary.Group1VariantCount)
	}
	if summary.Group2ShapeCount != 0 {
		t.Fatalf("expected group2 shape count to remain 0, got %d", summary.Group2ShapeCount)
	}
}

func TestValidateForTaskAcceptsGroup2OnlyMaterials(t *testing.T) {
	root := t.TempDir()
	writeMaterialsManifest(t, root)
	writeGroup2Manifest(t, root)
	writePNG(t, filepath.Join(root, "backgrounds", "bg.png"), 320, 180)
	writePNG(t, filepath.Join(root, "group2", "shapes", "shape_ticket", "001.png"), 32, 32)

	summary, err := ValidateForTask(root, "group2")
	if err != nil {
		t.Fatalf("validate group2-only materials: %v", err)
	}
	if summary.Group2ShapeCount != 1 {
		t.Fatalf("expected 1 group2 shape, got %d", summary.Group2ShapeCount)
	}
	if summary.Group1TemplateCount != 0 {
		t.Fatalf("expected group1 template count to remain 0, got %d", summary.Group1TemplateCount)
	}
}

func writeMaterialsManifest(t *testing.T, root string) {
	t.Helper()
	manifestPath := filepath.Join(root, "manifests", "materials.yaml")
	if err := os.MkdirAll(filepath.Dir(manifestPath), 0o755); err != nil {
		t.Fatalf("mkdir manifests: %v", err)
	}
	content := "schema_version: 3\n"
	if err := os.WriteFile(manifestPath, []byte(content), 0o644); err != nil {
		t.Fatalf("write manifest: %v", err)
	}
}

func writeGroup1TemplatesManifest(t *testing.T, root string) {
	t.Helper()
	manifestPath := filepath.Join(root, "manifests", "group1.templates.yaml")
	if err := os.MkdirAll(filepath.Dir(manifestPath), 0o755); err != nil {
		t.Fatalf("mkdir manifests: %v", err)
	}
	content := strings.Join([]string{
		"schema_version: 3",
		"task: group1",
		"mode: instance_matching",
		"",
		"templates:",
		"  - template_id: tpl_house",
		"    zh_name: 房子",
		"    family: building",
		"    tags: [house, home]",
		"    status: active",
		"    variants:",
		"      - variant_id: var_real_cluster_040_01",
		"        source: real_query",
		"        source_ref: cluster_040_01",
		"        style: captured",
		"",
	}, "\n")
	if err := os.WriteFile(manifestPath, []byte(content), 0o644); err != nil {
		t.Fatalf("write manifest: %v", err)
	}
}

func writeGroup2Manifest(t *testing.T, root string) {
	t.Helper()
	manifestPath := filepath.Join(root, "manifests", "group2.shapes.yaml")
	if err := os.MkdirAll(filepath.Dir(manifestPath), 0o755); err != nil {
		t.Fatalf("mkdir manifests: %v", err)
	}
	content := "shapes:\n  - id: 0\n    name: shape_ticket\n    zh_name: 缺口票形\n"
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
