package material

import (
	"image"
	_ "image/jpeg"
	_ "image/png"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type BackgroundAsset struct {
	ID     string `json:"id"`
	Path   string `json:"path"`
	Width  int    `json:"width"`
	Height int    `json:"height"`
}

type IconAsset struct {
	Path   string `json:"path"`
	Width  int    `json:"width"`
	Height int    `json:"height"`
}

type ClassAssets struct {
	ID     int         `json:"id"`
	Name   string      `json:"name"`
	ZhName string      `json:"zh_name"`
	Icons  []IconAsset `json:"icons"`
}

type Catalog struct {
	Root        string            `json:"root"`
	Manifest    string            `json:"manifest"`
	Backgrounds []BackgroundAsset `json:"backgrounds"`
	Classes     []ClassAssets     `json:"classes"`
}

func LoadCatalog(root string) (Catalog, error) {
	catalog := Catalog{
		Root:     root,
		Manifest: filepath.Join(root, "manifests", "classes.yaml"),
	}

	manifest, err := LoadManifest(catalog.Manifest)
	if err != nil {
		return catalog, err
	}

	backgroundPaths, err := listImageFiles(filepath.Join(root, "backgrounds"))
	if err != nil {
		return catalog, err
	}
	for _, backgroundPath := range backgroundPaths {
		width, height, err := imageSize(backgroundPath)
		if err != nil {
			return catalog, err
		}
		catalog.Backgrounds = append(catalog.Backgrounds, BackgroundAsset{
			ID:     strings.TrimSuffix(filepath.Base(backgroundPath), filepath.Ext(backgroundPath)),
			Path:   backgroundPath,
			Width:  width,
			Height: height,
		})
	}

	for _, classItem := range manifest.Classes {
		iconPaths, err := listImageFiles(filepath.Join(root, "icons", classItem.Name))
		if err != nil {
			return catalog, err
		}

		classAssets := ClassAssets{
			ID:     classItem.ID,
			Name:   classItem.Name,
			ZhName: classItem.ZhName,
			Icons:  make([]IconAsset, 0, len(iconPaths)),
		}
		for _, iconPath := range iconPaths {
			width, height, err := imageSize(iconPath)
			if err != nil {
				return catalog, err
			}
			classAssets.Icons = append(classAssets.Icons, IconAsset{
				Path:   iconPath,
				Width:  width,
				Height: height,
			})
		}
		catalog.Classes = append(catalog.Classes, classAssets)
	}

	return catalog, nil
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
