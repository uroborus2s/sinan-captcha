package workspace

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"time"

	"sinan-captcha/generator/internal/preset"
)

const CurrentSchemaVersion = 1

type MaterialSetRef struct {
	Scope        string `json:"scope"`
	Name         string `json:"name"`
	RelativePath string `json:"relative_path"`
}

type Metadata struct {
	SchemaVersion         int             `json:"schema_version"`
	WorkspaceRoot         string          `json:"workspace_root"`
	CreatedAt             string          `json:"created_at"`
	ActiveMaterialSet     *MaterialSetRef `json:"active_material_set,omitempty"`
	DefaultMaterialSource string          `json:"default_material_source,omitempty"`
}

type Layout struct {
	Root                 string
	MetadataPath         string
	PresetsDir           string
	MaterialsDir         string
	OfficialMaterialsDir string
	LocalMaterialsDir    string
	ManifestsDir         string
	QuarantineDir        string
	CacheDir             string
	CacheDownloadsDir    string
	JobsDir              string
	LogsDir              string
}

type State struct {
	Layout   Layout
	Metadata Metadata
}

func DefaultRoot() (string, error) {
	if runtime.GOOS == "windows" {
		if root := os.Getenv("LOCALAPPDATA"); root != "" {
			return filepath.Join(root, "SinanGenerator"), nil
		}
	}
	root, err := os.UserConfigDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(root, "SinanGenerator"), nil
}

func Ensure(root string) (State, error) {
	if root == "" {
		var err error
		root, err = DefaultRoot()
		if err != nil {
			return State{}, err
		}
	}
	root = filepath.Clean(root)
	layout := buildLayout(root)
	if err := ensureDirs(layout); err != nil {
		return State{}, err
	}

	metadata, err := loadMetadata(layout.MetadataPath)
	if err != nil {
		if !os.IsNotExist(err) {
			return State{}, err
		}
		metadata = Metadata{
			SchemaVersion: CurrentSchemaVersion,
			WorkspaceRoot: layout.Root,
			CreatedAt:     time.Now().UTC().Format(time.RFC3339),
		}
	}
	if metadata.SchemaVersion == 0 {
		metadata.SchemaVersion = CurrentSchemaVersion
	}
	if metadata.WorkspaceRoot == "" {
		metadata.WorkspaceRoot = layout.Root
	}
	if metadata.CreatedAt == "" {
		metadata.CreatedAt = time.Now().UTC().Format(time.RFC3339)
	}
	if err := SaveMetadata(layout.Root, metadata); err != nil {
		return State{}, err
	}
	if err := preset.WriteWorkspaceCopies(layout.PresetsDir); err != nil {
		return State{}, err
	}
	return State{Layout: layout, Metadata: metadata}, nil
}

func SaveMetadata(root string, metadata Metadata) error {
	layout := buildLayout(root)
	content, err := json.MarshalIndent(metadata, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(layout.MetadataPath, append(content, '\n'), 0o644)
}

func SetActiveMaterialSet(root string, ref MaterialSetRef) (State, error) {
	state, err := Ensure(root)
	if err != nil {
		return State{}, err
	}
	state.Metadata.ActiveMaterialSet = &ref
	if err := SaveMetadata(state.Layout.Root, state.Metadata); err != nil {
		return State{}, err
	}
	return state, nil
}

func MaterialSetPath(layout Layout, ref MaterialSetRef) (string, error) {
	switch ref.Scope {
	case "official":
		return filepath.Join(layout.OfficialMaterialsDir, ref.Name), nil
	case "local":
		return filepath.Join(layout.LocalMaterialsDir, ref.Name), nil
	default:
		return "", fmt.Errorf("unsupported material scope: %s", ref.Scope)
	}
}

func buildLayout(root string) Layout {
	materialsDir := filepath.Join(root, "materials")
	cacheDir := filepath.Join(root, "cache")
	return Layout{
		Root:                 root,
		MetadataPath:         filepath.Join(root, "workspace.json"),
		PresetsDir:           filepath.Join(root, "presets"),
		MaterialsDir:         materialsDir,
		OfficialMaterialsDir: filepath.Join(materialsDir, "official"),
		LocalMaterialsDir:    filepath.Join(materialsDir, "local"),
		ManifestsDir:         filepath.Join(materialsDir, "manifests"),
		QuarantineDir:        filepath.Join(materialsDir, "quarantine"),
		CacheDir:             cacheDir,
		CacheDownloadsDir:    filepath.Join(cacheDir, "downloads"),
		JobsDir:              filepath.Join(root, "jobs"),
		LogsDir:              filepath.Join(root, "logs"),
	}
}

func ensureDirs(layout Layout) error {
	dirs := []string{
		layout.Root,
		layout.PresetsDir,
		layout.OfficialMaterialsDir,
		layout.LocalMaterialsDir,
		layout.ManifestsDir,
		layout.QuarantineDir,
		layout.CacheDownloadsDir,
		layout.JobsDir,
		layout.LogsDir,
	}
	for _, dir := range dirs {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
	}
	return nil
}

func loadMetadata(path string) (Metadata, error) {
	var metadata Metadata
	content, err := os.ReadFile(path)
	if err != nil {
		return metadata, err
	}
	if err := json.Unmarshal(content, &metadata); err != nil {
		return metadata, err
	}
	return metadata, nil
}
