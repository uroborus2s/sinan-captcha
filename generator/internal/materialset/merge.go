package materialset

import (
	"fmt"
	"image"
	"image/draw"
	_ "image/jpeg"
	"image/png"
	_ "image/png"
	"io"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"sinan-captcha/generator/internal/material"
)

type MergeResult struct {
	Root               string                     `json:"root"`
	AddedBackgrounds   int                        `json:"added_backgrounds"`
	AddedGroup1Classes int                        `json:"added_group1_classes"`
	AddedGroup1Images  int                        `json:"added_group1_images"`
	AddedGroup2Shapes  int                        `json:"added_group2_shapes"`
	AddedGroup2Images  int                        `json:"added_group2_images"`
	Validation         material.ValidationSummary `json:"validation"`
}

func Merge(targetRoot string, incomingRoot string) (MergeResult, error) {
	result := MergeResult{
		Root: filepath.Clean(targetRoot),
	}
	incomingRoot = filepath.Clean(incomingRoot)

	info, err := os.Stat(incomingRoot)
	if err != nil {
		return result, err
	}
	if !info.IsDir() {
		return result, fmt.Errorf("incoming root must be a directory: %s", incomingRoot)
	}
	if err := ensureMergeTargetLayout(result.Root); err != nil {
		return result, err
	}

	group1Path := filepath.Join(result.Root, "manifests", "group1.classes.yaml")
	group2Path := filepath.Join(result.Root, "manifests", "group2.shapes.yaml")

	group1Entries, err := loadCatalogEntriesIfPresent(group1Path, "group1")
	if err != nil {
		return result, err
	}
	group2Entries, err := loadCatalogEntriesIfPresent(group2Path, "group2")
	if err != nil {
		return result, err
	}

	if result.AddedBackgrounds, err = mergeBackgroundImages(filepath.Join(incomingRoot, "backgrounds"), filepath.Join(result.Root, "backgrounds")); err != nil {
		return result, err
	}

	addedGroup1Entries, addedGroup1Images, err := mergeGroup1Raw(filepath.Join(incomingRoot, "group1"), filepath.Join(result.Root, "group1", "icons"), group1Entries)
	if err != nil {
		return result, err
	}
	group1Entries = addedGroup1Entries
	result.AddedGroup1Classes = addedGroup1Images
	result.AddedGroup1Images = addedGroup1Images
	if len(group1Entries) > 0 {
		if err := writeCatalogManifest(group1Path, "classes", group1Entries); err != nil {
			return result, err
		}
	}

	addedGroup2Entries, addedGroup2Images, err := mergeGroup2Raw(filepath.Join(incomingRoot, "group2"), filepath.Join(result.Root, "group2", "shapes"), group2Entries)
	if err != nil {
		return result, err
	}
	group2Entries = addedGroup2Entries
	result.AddedGroup2Shapes = addedGroup2Images
	result.AddedGroup2Images = addedGroup2Images
	if len(group2Entries) > 0 {
		if err := writeCatalogManifest(group2Path, "shapes", group2Entries); err != nil {
			return result, err
		}
	}

	if result.AddedBackgrounds == 0 && result.AddedGroup1Images == 0 && result.AddedGroup2Images == 0 {
		return result, fmt.Errorf("no incoming materials found in %s", incomingRoot)
	}

	result.Validation, err = material.ValidateForMerge(result.Root)
	if err != nil {
		return result, err
	}
	return result, nil
}

func ensureMergeTargetLayout(root string) error {
	dirs := []string{
		filepath.Join(root, "backgrounds"),
		filepath.Join(root, "group1", "icons"),
		filepath.Join(root, "group2", "shapes"),
		filepath.Join(root, "manifests"),
	}
	for _, dir := range dirs {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
	}
	manifestPath := filepath.Join(root, "manifests", "materials.yaml")
	if _, err := os.Stat(manifestPath); err == nil {
		return nil
	} else if !os.IsNotExist(err) {
		return err
	}
	return os.WriteFile(manifestPath, []byte("schema_version: 2\n"), 0o644)
}

func loadCatalogEntriesIfPresent(path string, task string) ([]material.CatalogEntry, error) {
	if _, err := os.Stat(path); err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	if task == "group1" {
		return material.LoadGroup1Manifest(path)
	}
	return material.LoadGroup2Manifest(path)
}

func mergeBackgroundImages(incomingDir string, destinationDir string) (int, error) {
	paths, err := listSupportedImageFiles(incomingDir)
	if err != nil {
		return 0, err
	}
	usedNames, err := listUsedFileNames(destinationDir)
	if err != nil {
		return 0, err
	}
	added := 0
	for _, path := range paths {
		if _, err := decodeImage(path); err != nil {
			return added, fmt.Errorf("decode background %s: %w", path, err)
		}
		targetPath := uniqueFilePath(destinationDir, filepath.Base(path), usedNames)
		if err := copyFile(path, targetPath); err != nil {
			return added, err
		}
		added++
	}
	return added, nil
}

func mergeGroup1Raw(incomingDir string, destinationDir string, existing []material.CatalogEntry) ([]material.CatalogEntry, int, error) {
	paths, err := listSupportedImageFiles(incomingDir)
	if err != nil {
		return existing, 0, err
	}
	if len(paths) == 0 {
		return existing, 0, nil
	}

	usedNames := make(map[string]struct{}, len(existing))
	maxID := -1
	for _, entry := range existing {
		usedNames[entry.Name] = struct{}{}
		if entry.ID > maxID {
			maxID = entry.ID
		}
	}

	added := 0
	entries := append([]material.CatalogEntry{}, existing...)
	for _, path := range paths {
		name := uniqueCatalogName(strings.TrimSuffix(filepath.Base(path), filepath.Ext(path)), "icon", usedNames)
		maxID++
		entries = append(entries, material.CatalogEntry{
			ID:     maxID,
			Name:   name,
			ZhName: name,
		})
		img, err := decodeImage(path)
		if err != nil {
			return existing, added, fmt.Errorf("decode group1 icon %s: %w", path, err)
		}
		classDir := filepath.Join(destinationDir, name)
		if err := os.MkdirAll(classDir, 0o755); err != nil {
			return existing, added, err
		}
		if err := savePNG(filepath.Join(classDir, "001.png"), img); err != nil {
			return existing, added, err
		}
		added++
	}
	return entries, added, nil
}

func mergeGroup2Raw(incomingDir string, destinationDir string, existing []material.CatalogEntry) ([]material.CatalogEntry, int, error) {
	paths, err := listSupportedImageFiles(incomingDir)
	if err != nil {
		return existing, 0, err
	}
	if len(paths) == 0 {
		return existing, 0, nil
	}

	usedNames := make(map[string]struct{}, len(existing))
	maxID := -1
	for _, entry := range existing {
		usedNames[entry.Name] = struct{}{}
		if entry.ID > maxID {
			maxID = entry.ID
		}
	}

	added := 0
	entries := append([]material.CatalogEntry{}, existing...)
	for _, path := range paths {
		name := uniqueCatalogName(strings.TrimSuffix(filepath.Base(path), filepath.Ext(path)), "shape", usedNames)
		maxID++
		entries = append(entries, material.CatalogEntry{
			ID:     maxID,
			Name:   name,
			ZhName: name,
		})
		img, err := decodeImage(path)
		if err != nil {
			return existing, added, fmt.Errorf("decode group2 gap %s: %w", path, err)
		}
		normalized, err := normalizeShapeMask(img)
		if err != nil {
			return existing, added, fmt.Errorf("normalize group2 gap %s: %w", path, err)
		}
		shapeDir := filepath.Join(destinationDir, name)
		if err := os.MkdirAll(shapeDir, 0o755); err != nil {
			return existing, added, err
		}
		if err := savePNG(filepath.Join(shapeDir, "001.png"), normalized); err != nil {
			return existing, added, err
		}
		added++
	}
	return entries, added, nil
}

func writeCatalogManifest(path string, section string, entries []material.CatalogEntry) error {
	sort.Slice(entries, func(i int, j int) bool {
		return entries[i].ID < entries[j].ID
	})
	lines := []string{section + ":"}
	for _, entry := range entries {
		lines = append(lines,
			fmt.Sprintf("  - id: %d", entry.ID),
			fmt.Sprintf("    name: %s", entry.Name),
			fmt.Sprintf("    zh_name: %s", entry.ZhName),
		)
	}
	lines = append(lines, "")
	return os.WriteFile(path, []byte(strings.Join(lines, "\n")), 0o644)
}

func normalizeShapeMask(src image.Image) (*image.RGBA, error) {
	rgba := toRGBA(src)
	bounds, ok := opaqueBounds(rgba)
	if !ok {
		return nil, fmt.Errorf("image has no opaque pixels")
	}

	cropped := image.NewRGBA(image.Rect(0, 0, bounds.Dx(), bounds.Dy()))
	draw.Draw(cropped, cropped.Bounds(), rgba, bounds.Min, draw.Src)

	maxDim := maxInt(bounds.Dx(), bounds.Dy())
	padding := maxInt(2, int(math.Round(float64(maxDim)*0.08)))
	canvasSize := maxDim + padding*2
	dst := image.NewRGBA(image.Rect(0, 0, canvasSize, canvasSize))
	offsetX := (canvasSize - bounds.Dx()) / 2
	offsetY := (canvasSize - bounds.Dy()) / 2
	targetRect := image.Rect(offsetX, offsetY, offsetX+bounds.Dx(), offsetY+bounds.Dy())
	draw.Draw(dst, targetRect, cropped, image.Point{}, draw.Src)
	return dst, nil
}

func opaqueBounds(img *image.RGBA) (image.Rectangle, bool) {
	bounds := img.Bounds()
	minX := bounds.Max.X
	minY := bounds.Max.Y
	maxX := bounds.Min.X
	maxY := bounds.Min.Y
	found := false

	for y := bounds.Min.Y; y < bounds.Max.Y; y++ {
		for x := bounds.Min.X; x < bounds.Max.X; x++ {
			if img.RGBAAt(x, y).A == 0 {
				continue
			}
			if x < minX {
				minX = x
			}
			if y < minY {
				minY = y
			}
			if x+1 > maxX {
				maxX = x + 1
			}
			if y+1 > maxY {
				maxY = y + 1
			}
			found = true
		}
	}
	if !found {
		return image.Rectangle{}, false
	}
	return image.Rect(minX, minY, maxX, maxY), true
}

func toRGBA(src image.Image) *image.RGBA {
	if rgba, ok := src.(*image.RGBA); ok {
		return rgba
	}
	bounds := src.Bounds()
	dst := image.NewRGBA(image.Rect(0, 0, bounds.Dx(), bounds.Dy()))
	draw.Draw(dst, dst.Bounds(), src, bounds.Min, draw.Src)
	return dst
}

func decodeImage(path string) (image.Image, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	img, _, err := image.Decode(file)
	if err != nil {
		return nil, err
	}
	return img, nil
}

func savePNG(path string, img image.Image) error {
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	return png.Encode(file, img)
}

func listSupportedImageFiles(dir string) ([]string, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	files := make([]string, 0, len(entries))
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		ext := strings.ToLower(filepath.Ext(entry.Name()))
		if ext != ".png" && ext != ".jpg" && ext != ".jpeg" {
			continue
		}
		files = append(files, filepath.Join(dir, entry.Name()))
	}
	sort.Strings(files)
	return files, nil
}

func listUsedFileNames(dir string) (map[string]struct{}, error) {
	used := make(map[string]struct{})
	entries, err := os.ReadDir(dir)
	if err != nil {
		if os.IsNotExist(err) {
			return used, nil
		}
		return nil, err
	}
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		used[strings.ToLower(entry.Name())] = struct{}{}
	}
	return used, nil
}

func uniqueFilePath(dir string, filename string, used map[string]struct{}) string {
	ext := filepath.Ext(filename)
	base := strings.TrimSuffix(filename, ext)
	candidate := filename
	if ext == "" {
		ext = ".png"
		candidate = base + ext
	}
	if _, exists := used[strings.ToLower(candidate)]; !exists {
		used[strings.ToLower(candidate)] = struct{}{}
		return filepath.Join(dir, candidate)
	}
	for index := 2; ; index++ {
		next := fmt.Sprintf("%s_%03d%s", base, index, ext)
		if _, exists := used[strings.ToLower(next)]; exists {
			continue
		}
		used[strings.ToLower(next)] = struct{}{}
		return filepath.Join(dir, next)
	}
}

func uniqueCatalogName(base string, fallback string, used map[string]struct{}) string {
	name := sanitizeName(base)
	name = strings.Trim(name, "-_.")
	if name == "" {
		name = fallback
	}
	if _, exists := used[name]; !exists {
		used[name] = struct{}{}
		return name
	}
	for index := 2; ; index++ {
		candidate := fmt.Sprintf("%s_%03d", name, index)
		if _, exists := used[candidate]; exists {
			continue
		}
		used[candidate] = struct{}{}
		return candidate
	}
}

func copyFile(source string, destination string) error {
	in, err := os.Open(source)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(destination)
	if err != nil {
		return err
	}
	if _, err := io.Copy(out, in); err != nil {
		out.Close()
		return err
	}
	return out.Close()
}

func maxInt(left int, right int) int {
	if left > right {
		return left
	}
	return right
}
