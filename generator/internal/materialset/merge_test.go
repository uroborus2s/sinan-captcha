package materialset

import (
	"image"
	"image/color"
	"image/draw"
	"image/png"
	"os"
	"path/filepath"
	"testing"

	"sinan-captcha/generator/internal/material"
)

func TestMergeAddsIncomingAssetsAndUpdatesManifests(t *testing.T) {
	targetRoot := filepath.Join(t.TempDir(), "materials")
	writeMaterialsManifest(t, filepath.Join(targetRoot, "manifests", "materials.yaml"))
	writeSingleGroup2Manifest(t, filepath.Join(targetRoot, "manifests", "group2.shapes.yaml"), "shape_ticket", "票形缺口")
	writePNG(t, filepath.Join(targetRoot, "backgrounds", "bg_existing.png"), 320, 180)
	writePNG(t, filepath.Join(targetRoot, "group2", "shapes", "shape_ticket", "001.png"), 48, 48)

	incomingRoot := filepath.Join(t.TempDir(), "incoming")
	writePNG(t, filepath.Join(incomingRoot, "backgrounds", "bg_new.png"), 360, 200)
	writePNG(t, filepath.Join(incomingRoot, "group1", "star.png"), 40, 40)
	writeTallTransparentPNG(t, filepath.Join(incomingRoot, "group2", "star-gap.png"), 41, 148)

	result, err := Merge(targetRoot, incomingRoot)
	if err != nil {
		t.Fatalf("merge materials: %v", err)
	}

	if result.AddedBackgrounds != 1 {
		t.Fatalf("expected 1 background, got %d", result.AddedBackgrounds)
	}
	if result.AddedGroup1Classes != 1 || result.AddedGroup1Images != 1 {
		t.Fatalf("expected 1 group1 class/image, got %+v", result)
	}
	if result.AddedGroup2Shapes != 1 || result.AddedGroup2Images != 1 {
		t.Fatalf("expected 1 group2 shape/image, got %+v", result)
	}
	if result.Validation.BackgroundCount != 2 {
		t.Fatalf("expected 2 backgrounds after merge, got %d", result.Validation.BackgroundCount)
	}
	if result.Validation.Group1ClassCount != 1 {
		t.Fatalf("expected 1 group1 class after merge, got %d", result.Validation.Group1ClassCount)
	}
	if result.Validation.Group2ShapeCount != 2 {
		t.Fatalf("expected 2 group2 shapes after merge, got %d", result.Validation.Group2ShapeCount)
	}

	group1Entries, err := material.LoadGroup1Manifest(filepath.Join(targetRoot, "manifests", "group1.classes.yaml"))
	if err != nil {
		t.Fatalf("load group1 manifest: %v", err)
	}
	if len(group1Entries) != 1 || group1Entries[0].Name != "star" {
		t.Fatalf("unexpected group1 entries: %+v", group1Entries)
	}

	group2Entries, err := material.LoadGroup2Manifest(filepath.Join(targetRoot, "manifests", "group2.shapes.yaml"))
	if err != nil {
		t.Fatalf("load group2 manifest: %v", err)
	}
	if len(group2Entries) != 2 {
		t.Fatalf("unexpected group2 entry count: %d", len(group2Entries))
	}
	if group2Entries[1].Name != "star-gap" {
		t.Fatalf("expected new group2 shape to use file name, got %+v", group2Entries[1])
	}

	shapePath := filepath.Join(targetRoot, "group2", "shapes", "star-gap", "001.png")
	shapeImage := decodePNG(t, shapePath)
	if shapeImage.Bounds().Dx() != shapeImage.Bounds().Dy() {
		t.Fatalf("expected normalized shape to be square, got %dx%d", shapeImage.Bounds().Dx(), shapeImage.Bounds().Dy())
	}
	if shapeImage.RGBAAt(0, 0).A != 0 {
		t.Fatalf("expected normalized shape corner to stay transparent")
	}
}

func TestMergeKeepsOneImageOneClassWhenNameCollides(t *testing.T) {
	targetRoot := filepath.Join(t.TempDir(), "materials")
	writeMaterialsManifest(t, filepath.Join(targetRoot, "manifests", "materials.yaml"))
	writeSingleGroup1Manifest(t, filepath.Join(targetRoot, "manifests", "group1.classes.yaml"), "icon_house", "房子")
	writePNG(t, filepath.Join(targetRoot, "backgrounds", "bg_existing.png"), 320, 180)
	writePNG(t, filepath.Join(targetRoot, "group1", "icons", "icon_house", "001.png"), 48, 48)

	incomingRoot := filepath.Join(t.TempDir(), "incoming")
	writePNG(t, filepath.Join(incomingRoot, "group1", "icon_house.png"), 40, 40)

	result, err := Merge(targetRoot, incomingRoot)
	if err != nil {
		t.Fatalf("merge materials: %v", err)
	}
	if result.AddedGroup1Classes != 1 {
		t.Fatalf("expected 1 added group1 class, got %d", result.AddedGroup1Classes)
	}

	group1Entries, err := material.LoadGroup1Manifest(filepath.Join(targetRoot, "manifests", "group1.classes.yaml"))
	if err != nil {
		t.Fatalf("load group1 manifest: %v", err)
	}
	if len(group1Entries) != 2 {
		t.Fatalf("expected 2 group1 entries, got %d", len(group1Entries))
	}
	if group1Entries[1].Name != "icon_house_002" {
		t.Fatalf("expected unique one-image-one-class name, got %+v", group1Entries[1])
	}
	if _, err := os.Stat(filepath.Join(targetRoot, "group1", "icons", "icon_house_002", "001.png")); err != nil {
		t.Fatalf("expected unique class directory: %v", err)
	}
}

func TestMergeAcceptsIncrementalGroup1WithoutBackgrounds(t *testing.T) {
	targetRoot := filepath.Join(t.TempDir(), "materials")
	writeMaterialsManifest(t, filepath.Join(targetRoot, "manifests", "materials.yaml"))

	incomingRoot := filepath.Join(t.TempDir(), "incoming")
	writePNG(t, filepath.Join(incomingRoot, "group1", "star.png"), 40, 40)

	result, err := Merge(targetRoot, incomingRoot)
	if err != nil {
		t.Fatalf("merge group1-only materials: %v", err)
	}
	if result.AddedBackgrounds != 0 {
		t.Fatalf("expected no backgrounds to be added, got %d", result.AddedBackgrounds)
	}
	if result.AddedGroup1Classes != 1 || result.AddedGroup1Images != 1 {
		t.Fatalf("expected one group1 class/image, got %+v", result)
	}
	if result.Validation.BackgroundCount != 0 {
		t.Fatalf("expected background count to stay 0, got %d", result.Validation.BackgroundCount)
	}
	if result.Validation.Group1ClassCount != 1 {
		t.Fatalf("expected one validated group1 class, got %d", result.Validation.Group1ClassCount)
	}
	if result.Validation.Group2ShapeCount != 0 {
		t.Fatalf("expected group2 validation to be skipped, got %d", result.Validation.Group2ShapeCount)
	}
}

func TestMergeAcceptsBackgroundOnlyIncrementalImport(t *testing.T) {
	targetRoot := filepath.Join(t.TempDir(), "materials")
	writeMaterialsManifest(t, filepath.Join(targetRoot, "manifests", "materials.yaml"))

	incomingRoot := filepath.Join(t.TempDir(), "incoming")
	writePNG(t, filepath.Join(incomingRoot, "backgrounds", "bg_new.png"), 360, 200)

	result, err := Merge(targetRoot, incomingRoot)
	if err != nil {
		t.Fatalf("merge backgrounds-only materials: %v", err)
	}
	if result.AddedBackgrounds != 1 {
		t.Fatalf("expected one added background, got %d", result.AddedBackgrounds)
	}
	if result.AddedGroup1Images != 0 || result.AddedGroup2Images != 0 {
		t.Fatalf("expected no task assets to be added, got %+v", result)
	}
	if result.Validation.BackgroundCount != 1 {
		t.Fatalf("expected one validated background, got %d", result.Validation.BackgroundCount)
	}
	if result.Validation.Group1ClassCount != 0 || result.Validation.Group2ShapeCount != 0 {
		t.Fatalf("expected task validation to be skipped, got %+v", result.Validation)
	}
}

func writeTallTransparentPNG(t *testing.T, path string, width int, height int) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir tall png dir: %v", err)
	}

	img := image.NewRGBA(image.Rect(0, 0, width, height))
	draw.Draw(img, img.Bounds(), image.Transparent, image.Point{}, draw.Src)
	fill := image.Rect(width/4, 6, width-width/4, height-6)
	for y := fill.Min.Y; y < fill.Max.Y; y++ {
		for x := fill.Min.X; x < fill.Max.X; x++ {
			img.SetRGBA(x, y, color.RGBA{R: 210, G: 160, B: 80, A: 255})
		}
	}

	file, err := os.Create(path)
	if err != nil {
		t.Fatalf("create tall png: %v", err)
	}
	defer file.Close()
	if err := png.Encode(file, img); err != nil {
		t.Fatalf("encode tall png: %v", err)
	}
}

func decodePNG(t *testing.T, path string) *image.RGBA {
	t.Helper()
	file, err := os.Open(path)
	if err != nil {
		t.Fatalf("open png %s: %v", path, err)
	}
	defer file.Close()

	img, err := png.Decode(file)
	if err != nil {
		t.Fatalf("decode png %s: %v", path, err)
	}
	rgba, ok := img.(*image.RGBA)
	if ok {
		return rgba
	}
	bounds := img.Bounds()
	out := image.NewRGBA(bounds)
	draw.Draw(out, bounds, img, bounds.Min, draw.Src)
	return out
}

func writeSingleGroup1Manifest(t *testing.T, path string, name string, zhName string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir manifest dir: %v", err)
	}
	content := "classes:\n  - id: 0\n    name: " + name + "\n    zh_name: " + zhName + "\n"
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write group1 manifest: %v", err)
	}
}

func writeSingleGroup2Manifest(t *testing.T, path string, name string, zhName string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir manifest dir: %v", err)
	}
	content := "shapes:\n  - id: 0\n    name: " + name + "\n    zh_name: " + zhName + "\n"
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write group2 manifest: %v", err)
	}
}
