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

const CurrentSchemaVersion = 3

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

type Group1VariantAsset struct {
	AssetID    string `json:"asset_id"`
	TemplateID string `json:"template_id"`
	VariantID  string `json:"variant_id"`
	Source     string `json:"source,omitempty"`
	SourceRef  string `json:"source_ref,omitempty"`
	Style      string `json:"style,omitempty"`
	Path       string `json:"path"`
	Width      int    `json:"width"`
	Height     int    `json:"height"`
}

type Group1TemplateAssets struct {
	Index      int                  `json:"index"`
	TemplateID string               `json:"template_id"`
	ZhName     string               `json:"zh_name"`
	Family     string               `json:"family,omitempty"`
	Tags       []string             `json:"tags,omitempty"`
	Status     string               `json:"status,omitempty"`
	Variants   []Group1VariantAsset `json:"variants"`
}

type ShapeAssets struct {
	ID     int          `json:"id"`
	Name   string       `json:"name"`
	ZhName string       `json:"zh_name"`
	Shapes []ImageAsset `json:"shapes"`
}

type Catalog struct {
	Root                    string                 `json:"root"`
	Task                    string                 `json:"task"`
	SchemaVersion           int                    `json:"schema_version"`
	MaterialsManifest       string                 `json:"materials_manifest"`
	Group1TemplatesManifest string                 `json:"group1_templates_manifest"`
	Group2Manifest          string                 `json:"group2_manifest"`
	Backgrounds             []BackgroundAsset      `json:"backgrounds"`
	Group1Templates         []Group1TemplateAssets `json:"group1_templates,omitempty"`
	Group2Shapes            []ShapeAssets          `json:"group2_shapes,omitempty"`
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
		Root:                    root,
		Task:                    task,
		MaterialsManifest:       filepath.Join(root, "manifests", "materials.yaml"),
		Group1TemplatesManifest: filepath.Join(root, "manifests", "group1.templates.yaml"),
		Group2Manifest:          filepath.Join(root, "manifests", "group2.shapes.yaml"),
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
		manifest, err := LoadGroup1TemplatesManifest(catalog.Group1TemplatesManifest)
		if err != nil {
			return catalog, err
		}
		catalog.Group1Templates, err = loadGroup1TemplateAssets(root, manifest.Templates)
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

func loadGroup1TemplateAssets(root string, entries []Group1TemplateEntry) ([]Group1TemplateAssets, error) {
	templates := make([]Group1TemplateAssets, 0, len(entries))
	for index, entry := range entries {
		templateAssets := Group1TemplateAssets{
			Index:      index,
			TemplateID: entry.TemplateID,
			ZhName:     entry.ZhName,
			Family:     entry.Family,
			Tags:       append([]string(nil), entry.Tags...),
			Status:     entry.Status,
			Variants:   make([]Group1VariantAsset, 0, len(entry.Variants)),
		}
		for _, variant := range entry.Variants {
			variantPath := filepath.Join(root, "group1", "icons", entry.TemplateID, variant.VariantID+".png")
			width, height, err := imageSize(variantPath)
			if err != nil {
				return nil, err
			}
			templateAssets.Variants = append(templateAssets.Variants, Group1VariantAsset{
				AssetID:    BuildGroup1AssetID(entry.TemplateID, variant.VariantID),
				TemplateID: entry.TemplateID,
				VariantID:  variant.VariantID,
				Source:     variant.Source,
				SourceRef:  variant.SourceRef,
				Style:      variant.Style,
				Path:       variantPath,
				Width:      width,
				Height:     height,
			})
		}
		templates = append(templates, templateAssets)
	}
	return templates, nil
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

func BuildGroup1AssetID(templateID string, variantID string) string {
	templateID = strings.TrimSpace(templateID)
	variantID = strings.TrimSpace(variantID)
	if templateID == "" || variantID == "" {
		return ""
	}
	return "asset_" + templateID + "__" + variantID
}
