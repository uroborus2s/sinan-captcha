package material

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

type ClassManifest struct {
	Classes []Class `yaml:"classes"`
}

type Class struct {
	ID     int    `yaml:"id"`
	Name   string `yaml:"name"`
	ZhName string `yaml:"zh_name"`
}

type ValidationSummary struct {
	ManifestPath    string `json:"manifest_path"`
	ClassCount      int    `json:"class_count"`
	BackgroundCount int    `json:"background_count"`
	IconDirCount    int    `json:"icon_dir_count"`
}

func Validate(root string) (ValidationSummary, error) {
	summary := ValidationSummary{
		ManifestPath: filepath.Join(root, "manifests", "classes.yaml"),
	}

	manifest, err := LoadManifest(summary.ManifestPath)
	if err != nil {
		return summary, err
	}
	summary.ClassCount = len(manifest.Classes)
	if summary.ClassCount == 0 {
		return summary, errors.New("classes manifest is empty")
	}

	backgroundDir := filepath.Join(root, "backgrounds")
	backgroundCount, err := countImageFiles(backgroundDir)
	if err != nil {
		return summary, err
	}
	if backgroundCount == 0 {
		return summary, errors.New("no background images found")
	}
	summary.BackgroundCount = backgroundCount

	iconsRoot := filepath.Join(root, "icons")
	iconDirCount := 0
	for _, classItem := range manifest.Classes {
		classDir := filepath.Join(iconsRoot, classItem.Name)
		count, err := countImageFiles(classDir)
		if err != nil {
			return summary, err
		}
		if count == 0 {
			return summary, errors.New("no icon images found for class: " + classItem.Name)
		}
		iconDirCount++
	}
	summary.IconDirCount = iconDirCount
	return summary, nil
}

func LoadManifest(path string) (ClassManifest, error) {
	var manifest ClassManifest
	content, err := os.ReadFile(path)
	if err != nil {
		return manifest, err
	}
	return manifest, parseManifest(content, &manifest)
}

func countImageFiles(dir string) (int, error) {
	files, err := listImageFiles(dir)
	if err != nil {
		return 0, err
	}
	return len(files), nil
}

func parseManifest(content []byte, manifest *ClassManifest) error {
	inClasses := false
	var current *Class

	for lineNumber, rawLine := range strings.Split(string(content), "\n") {
		line := strings.TrimSpace(rawLine)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if line == "classes:" {
			inClasses = true
			continue
		}
		if !inClasses {
			continue
		}

		if strings.HasPrefix(line, "- ") {
			manifest.Classes = append(manifest.Classes, Class{})
			current = &manifest.Classes[len(manifest.Classes)-1]
			line = strings.TrimSpace(strings.TrimPrefix(line, "- "))
			if line == "" {
				continue
			}
		}
		if current == nil {
			return fmt.Errorf("invalid manifest line %d: class item not started", lineNumber+1)
		}
		key, value, err := splitManifestField(line)
		if err != nil {
			return fmt.Errorf("invalid manifest line %d: %w", lineNumber+1, err)
		}
		if err := assignClassField(current, key, value); err != nil {
			return fmt.Errorf("invalid manifest line %d: %w", lineNumber+1, err)
		}
	}
	return nil
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

func assignClassField(class *Class, key string, value string) error {
	switch key {
	case "id":
		parsed, err := strconv.Atoi(value)
		if err != nil {
			return err
		}
		class.ID = parsed
	case "name":
		class.Name = value
	case "zh_name":
		class.ZhName = value
	default:
		return fmt.Errorf("unsupported key: %s", key)
	}
	return nil
}
