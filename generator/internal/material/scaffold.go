package material

import (
	"fmt"
	"os"
	"path/filepath"
)

type InitSummary struct {
	Root            string `json:"root"`
	ManifestPath    string `json:"manifest_path"`
	ManifestCreated bool   `json:"manifest_created"`
	IconDirCount    int    `json:"icon_dir_count"`
}

func Initialize(root string) (InitSummary, error) {
	summary := InitSummary{
		Root:         root,
		ManifestPath: filepath.Join(root, "manifests", "classes.yaml"),
	}

	requiredDirs := []string{
		filepath.Join(root, "backgrounds"),
		filepath.Join(root, "icons"),
		filepath.Join(root, "manifests"),
	}
	for _, dir := range requiredDirs {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return summary, err
		}
	}

	if _, err := os.Stat(summary.ManifestPath); os.IsNotExist(err) {
		if err := os.WriteFile(summary.ManifestPath, []byte(defaultManifestContent()), 0o644); err != nil {
			return summary, err
		}
		summary.ManifestCreated = true
		return summary, nil
	} else if err != nil {
		return summary, err
	}

	manifest, err := LoadManifest(summary.ManifestPath)
	if err != nil {
		return summary, err
	}
	for _, classItem := range manifest.Classes {
		if classItem.Name == "" {
			return summary, fmt.Errorf("class name must not be empty")
		}
		if err := os.MkdirAll(filepath.Join(root, "icons", classItem.Name), 0o755); err != nil {
			return summary, err
		}
		summary.IconDirCount++
	}
	return summary, nil
}

func defaultManifestContent() string {
	return "# Fill this manifest before running validate-materials or generate.\n" +
		"classes:\n" +
		"  # - id: 0\n" +
		"  #   name: icon_house\n" +
		"  #   zh_name: 房子\n"
}
