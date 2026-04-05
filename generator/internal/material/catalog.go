package material

import (
	"fmt"
	"image"
	_ "image/jpeg"
	_ "image/png"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

const CurrentSchemaVersion = 2

type BackgroundAsset struct {
	ID     string `json:"id"`
	Path   string `json:"path"`
	Width  int    `json:"width"`
	Height int    `json:"height"`
}

type ImageAsset struct {
	Path   string `json:"path"`
	Width  int    `json:"width"`
	Height int    `json:"height"`
}

type ClassAssets struct {
	ID     int          `json:"id"`
	Name   string       `json:"name"`
	ZhName string       `json:"zh_name"`
	Icons  []ImageAsset `json:"icons"`
}

type ShapeAssets struct {
	ID     int          `json:"id"`
	Name   string       `json:"name"`
	ZhName string       `json:"zh_name"`
	Shapes []ImageAsset `json:"shapes"`
}

type Catalog struct {
	Root              string            `json:"root"`
	Task              string            `json:"task"`
	SchemaVersion     int               `json:"schema_version"`
	MaterialsManifest string            `json:"materials_manifest"`
	Group1Manifest    string            `json:"group1_manifest"`
	Group2Manifest    string            `json:"group2_manifest"`
	Backgrounds       []BackgroundAsset `json:"backgrounds"`
	Group1Classes     []ClassAssets     `json:"group1_classes,omitempty"`
	Group2Shapes      []ShapeAssets     `json:"group2_shapes,omitempty"`
}

type MaterialsManifest struct {
	SchemaVersion int
}

type CatalogEntry struct {
	ID     int
	Name   string
	ZhName string
}

func LoadCatalog(root string, task string) (Catalog, error) {
	catalog := Catalog{
		Root:              root,
		Task:              task,
		MaterialsManifest: filepath.Join(root, "manifests", "materials.yaml"),
		Group1Manifest:    filepath.Join(root, "manifests", "group1.classes.yaml"),
		Group2Manifest:    filepath.Join(root, "manifests", "group2.shapes.yaml"),
	}

	manifest, err := LoadMaterialsManifest(catalog.MaterialsManifest)
	if err != nil {
		return catalog, err
	}
	if manifest.SchemaVersion != CurrentSchemaVersion {
		return catalog, fmt.Errorf("unsupported materials schema version: %d", manifest.SchemaVersion)
	}
	catalog.SchemaVersion = manifest.SchemaVersion

	backgrounds, err := loadBackgrounds(root)
	if err != nil {
		return catalog, err
	}
	catalog.Backgrounds = backgrounds

	switch strings.TrimSpace(task) {
	case "group1":
		classes, err := LoadGroup1Manifest(catalog.Group1Manifest)
		if err != nil {
			return catalog, err
		}
		catalog.Group1Classes, err = loadClassAssets(root, classes)
		if err != nil {
			return catalog, err
		}
	case "group2":
		shapes, err := LoadGroup2Manifest(catalog.Group2Manifest)
		if err != nil {
			return catalog, err
		}
		catalog.Group2Shapes, err = loadShapeAssets(root, shapes)
		if err != nil {
			return catalog, err
		}
	default:
		return catalog, fmt.Errorf("unsupported materials task: %s", task)
	}

	return catalog, nil
}

func loadBackgrounds(root string) ([]BackgroundAsset, error) {
	backgroundPaths, err := listImageFiles(filepath.Join(root, "backgrounds"))
	if err != nil {
		return nil, err
	}
	backgrounds := make([]BackgroundAsset, 0, len(backgroundPaths))
	for _, backgroundPath := range backgroundPaths {
		width, height, err := imageSize(backgroundPath)
		if err != nil {
			return nil, err
		}
		backgrounds = append(backgrounds, BackgroundAsset{
			ID:     strings.TrimSuffix(filepath.Base(backgroundPath), filepath.Ext(backgroundPath)),
			Path:   backgroundPath,
			Width:  width,
			Height: height,
		})
	}
	return backgrounds, nil
}

func loadClassAssets(root string, entries []CatalogEntry) ([]ClassAssets, error) {
	classes := make([]ClassAssets, 0, len(entries))
	for _, entry := range entries {
		iconPaths, err := listImageFiles(filepath.Join(root, "group1", "icons", entry.Name))
		if err != nil {
			return nil, err
		}
		classAssets := ClassAssets{
			ID:     entry.ID,
			Name:   entry.Name,
			ZhName: entry.ZhName,
			Icons:  make([]ImageAsset, 0, len(iconPaths)),
		}
		for _, iconPath := range iconPaths {
			width, height, err := imageSize(iconPath)
			if err != nil {
				return nil, err
			}
			classAssets.Icons = append(classAssets.Icons, ImageAsset{
				Path:   iconPath,
				Width:  width,
				Height: height,
			})
		}
		classes = append(classes, classAssets)
	}
	return classes, nil
}

func loadShapeAssets(root string, entries []CatalogEntry) ([]ShapeAssets, error) {
	shapes := make([]ShapeAssets, 0, len(entries))
	for _, entry := range entries {
		shapePaths, err := listImageFiles(filepath.Join(root, "group2", "shapes", entry.Name))
		if err != nil {
			return nil, err
		}
		shapeAssets := ShapeAssets{
			ID:     entry.ID,
			Name:   entry.Name,
			ZhName: entry.ZhName,
			Shapes: make([]ImageAsset, 0, len(shapePaths)),
		}
		for _, shapePath := range shapePaths {
			width, height, err := imageSize(shapePath)
			if err != nil {
				return nil, err
			}
			shapeAssets.Shapes = append(shapeAssets.Shapes, ImageAsset{
				Path:   shapePath,
				Width:  width,
				Height: height,
			})
		}
		shapes = append(shapes, shapeAssets)
	}
	return shapes, nil
}

func listImageFiles(dir string) ([]string, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
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

func imageSize(path string) (int, int, error) {
	file, err := os.Open(path)
	if err != nil {
		return 0, 0, err
	}
	defer file.Close()

	cfg, _, err := image.DecodeConfig(file)
	if err != nil {
		return 0, 0, err
	}
	return cfg.Width, cfg.Height, nil
}
