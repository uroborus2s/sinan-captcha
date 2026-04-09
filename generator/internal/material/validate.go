package material

import (
	"errors"
	"fmt"
	"image"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

type ValidationSummary struct {
	SchemaVersion         int    `json:"schema_version"`
	MaterialsManifestPath string `json:"materials_manifest_path"`
	Group1ManifestPath    string `json:"group1_manifest_path"`
	Group2ManifestPath    string `json:"group2_manifest_path"`
	BackgroundCount       int    `json:"background_count"`
	Group1ClassCount      int    `json:"group1_class_count"`
	Group1IconDirCount    int    `json:"group1_icon_dir_count"`
	Group2ShapeCount      int    `json:"group2_shape_count"`
	Group2ShapeDirCount   int    `json:"group2_shape_dir_count"`
}

func Validate(root string) (ValidationSummary, error) {
	return ValidateForTask(root, "")
}

func ValidateForTask(root string, task string) (ValidationSummary, error) {
	return validateForTask(root, task, true, false)
}

func ValidateForMerge(root string) (ValidationSummary, error) {
	return validateForTask(root, "", false, true)
}

func validateForTask(root string, task string, requireBackgrounds bool, allowMissingTasks bool) (ValidationSummary, error) {
	summary := ValidationSummary{
		MaterialsManifestPath: filepath.Join(root, "manifests", "materials.yaml"),
		Group1ManifestPath:    filepath.Join(root, "manifests", "group1.classes.yaml"),
		Group2ManifestPath:    filepath.Join(root, "manifests", "group2.shapes.yaml"),
	}

	materialsManifest, err := LoadMaterialsManifest(summary.MaterialsManifestPath)
	if err != nil {
		return summary, err
	}
	if materialsManifest.SchemaVersion != CurrentSchemaVersion {
		return summary, fmt.Errorf("unsupported materials schema version: %d", materialsManifest.SchemaVersion)
	}
	summary.SchemaVersion = materialsManifest.SchemaVersion

	backgroundCount, err := countValidImageFiles(filepath.Join(root, "backgrounds"))
	if err != nil && !os.IsNotExist(err) {
		return summary, err
	}
	if requireBackgrounds && backgroundCount == 0 {
		return summary, errors.New("no background images found")
	}
	summary.BackgroundCount = backgroundCount

	switch strings.TrimSpace(task) {
	case "", "all":
		if err := validateGroup1(root, &summary, allowMissingTasks); err != nil {
			return summary, err
		}
		if err := validateGroup2(root, &summary, allowMissingTasks); err != nil {
			return summary, err
		}
	case "group1":
		if err := validateGroup1(root, &summary, allowMissingTasks); err != nil {
			return summary, err
		}
	case "group2":
		if err := validateGroup2(root, &summary, allowMissingTasks); err != nil {
			return summary, err
		}
	default:
		return summary, fmt.Errorf("unsupported materials task: %s", task)
	}

	return summary, nil
}

func validateGroup1(root string, summary *ValidationSummary, allowMissing bool) error {
	group1Entries, err := LoadGroup1Manifest(summary.Group1ManifestPath)
	if err != nil {
		if allowMissing && os.IsNotExist(err) {
			return nil
		}
		return err
	}
	summary.Group1ClassCount = len(group1Entries)
	if summary.Group1ClassCount == 0 {
		if allowMissing {
			return nil
		}
		return errors.New("group1 classes manifest is empty")
	}
	for _, entry := range group1Entries {
		count, err := countValidImageFiles(filepath.Join(root, "group1", "icons", entry.Name))
		if err != nil && !os.IsNotExist(err) {
			return err
		}
		if count == 0 {
			return errors.New("no group1 icon images found for class: " + entry.Name)
		}
		summary.Group1IconDirCount++
	}
	return nil
}

func validateGroup2(root string, summary *ValidationSummary, allowMissing bool) error {
	group2Entries, err := LoadGroup2Manifest(summary.Group2ManifestPath)
	if err != nil {
		if allowMissing && os.IsNotExist(err) {
			return nil
		}
		return err
	}
	summary.Group2ShapeCount = len(group2Entries)
	if summary.Group2ShapeCount == 0 {
		if allowMissing {
			return nil
		}
		return errors.New("group2 shapes manifest is empty")
	}
	for _, entry := range group2Entries {
		count, err := countValidImageFiles(filepath.Join(root, "group2", "shapes", entry.Name))
		if err != nil && !os.IsNotExist(err) {
			return err
		}
		if count == 0 {
			return errors.New("no group2 shape images found for shape: " + entry.Name)
		}
		summary.Group2ShapeDirCount++
	}
	return nil
}

func LoadMaterialsManifest(path string) (MaterialsManifest, error) {
	manifest := MaterialsManifest{}
	content, err := os.ReadFile(path)
	if err != nil {
		return manifest, err
	}
	for lineNumber, rawLine := range strings.Split(string(content), "\n") {
		line := strings.TrimSpace(rawLine)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		key, value, err := splitManifestField(line)
		if err != nil {
			return manifest, fmt.Errorf("invalid materials manifest line %d: %w", lineNumber+1, err)
		}
		switch key {
		case "schema_version":
			parsed, err := strconv.Atoi(value)
			if err != nil {
				return manifest, fmt.Errorf("invalid materials manifest line %d: %w", lineNumber+1, err)
			}
			manifest.SchemaVersion = parsed
		default:
			return manifest, fmt.Errorf("invalid materials manifest line %d: unsupported key: %s", lineNumber+1, key)
		}
	}
	if manifest.SchemaVersion == 0 {
		return manifest, errors.New("materials schema_version is required")
	}
	return manifest, nil
}

func LoadGroup1Manifest(path string) ([]CatalogEntry, error) {
	return loadCatalogEntries(path, "classes")
}

func LoadGroup2Manifest(path string) ([]CatalogEntry, error) {
	return loadCatalogEntries(path, "shapes")
}

func loadCatalogEntries(path string, section string) ([]CatalogEntry, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return parseCatalogEntries(content, section)
}

func countValidImageFiles(dir string) (int, error) {
	files, err := listImageFiles(dir)
	if err != nil {
		return 0, err
	}
	for _, path := range files {
		if err := validateImageFile(path); err != nil {
			return 0, fmt.Errorf("invalid image file %s: %w", path, err)
		}
	}
	return len(files), nil
}

func validateImageFile(path string) error {
	file, err := os.Open(path)
	if err != nil {
		return err
	}
	defer file.Close()

	img, _, err := image.Decode(file)
	if err != nil {
		return err
	}
	bounds := img.Bounds()
	if bounds.Dx() <= 0 || bounds.Dy() <= 0 {
		return fmt.Errorf("invalid image bounds %dx%d", bounds.Dx(), bounds.Dy())
	}
	return nil
}

func parseCatalogEntries(content []byte, section string) ([]CatalogEntry, error) {
	entries := make([]CatalogEntry, 0)
	inSection := false
	var current *CatalogEntry

	for lineNumber, rawLine := range strings.Split(string(content), "\n") {
		line := strings.TrimSpace(rawLine)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if line == section+":" {
			inSection = true
			continue
		}
		if !inSection {
			continue
		}
		if strings.HasSuffix(line, ":") && !strings.HasPrefix(line, "- ") {
			return nil, fmt.Errorf("invalid manifest line %d: unexpected section %s", lineNumber+1, line)
		}

		if strings.HasPrefix(line, "- ") {
			entries = append(entries, CatalogEntry{})
			current = &entries[len(entries)-1]
			line = strings.TrimSpace(strings.TrimPrefix(line, "- "))
			if line == "" {
				continue
			}
		}
		if current == nil {
			return nil, fmt.Errorf("invalid manifest line %d: item not started", lineNumber+1)
		}

		key, value, err := splitManifestField(line)
		if err != nil {
			return nil, fmt.Errorf("invalid manifest line %d: %w", lineNumber+1, err)
		}
		if err := assignCatalogEntryField(current, key, value); err != nil {
			return nil, fmt.Errorf("invalid manifest line %d: %w", lineNumber+1, err)
		}
	}

	return entries, nil
}

func splitManifestField(line string) (string, string, error) {
	parts := strings.SplitN(line, ":", 2)
	if len(parts) != 2 {
		return "", "", fmt.Errorf("expected key: value")
	}
	key := strings.TrimSpace(parts[0])
	value := strings.Trim(strings.TrimSpace(parts[1]), "\"'")
	if key == "" || value == "" {
		return "", "", fmt.Errorf("expected non-empty key and value")
	}
	return key, value, nil
}

func assignCatalogEntryField(entry *CatalogEntry, key string, value string) error {
	switch key {
	case "id":
		parsed, err := strconv.Atoi(value)
		if err != nil {
			return err
		}
		entry.ID = parsed
	case "name":
		entry.Name = value
	case "zh_name":
		entry.ZhName = value
	default:
		return fmt.Errorf("unsupported key: %s", key)
	}
	return nil
}
