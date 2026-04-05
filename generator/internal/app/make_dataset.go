package app

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"time"

	"sinan-captcha/generator/internal/backend"
	"sinan-captcha/generator/internal/config"
	"sinan-captcha/generator/internal/dataset"
	"sinan-captcha/generator/internal/export"
	"sinan-captcha/generator/internal/material"
	"sinan-captcha/generator/internal/materialset"
	"sinan-captcha/generator/internal/preset"
	"sinan-captcha/generator/internal/qa"
	"sinan-captcha/generator/internal/truth"
	"sinan-captcha/generator/internal/workspace"
)

type MakeDatasetRequest struct {
	Task           string
	Preset         string
	WorkspaceRoot  string
	DatasetDir     string
	Materials      string
	MaterialSource string
	OverrideFile   string
	Force          bool
	Writer         io.Writer
}

type MakeDatasetResult struct {
	WorkspaceRoot string                   `json:"workspace_root"`
	DatasetDir    string                   `json:"dataset_dir"`
	BatchRoot     string                   `json:"batch_root"`
	DatasetConfig string                   `json:"dataset_config"`
	JobPath       string                   `json:"job_path"`
	Preset        string                   `json:"preset"`
	Task          string                   `json:"task"`
	Materials     workspace.MaterialSetRef `json:"materials"`
	Generated     int                      `json:"generated"`
}

type jobRecord struct {
	JobID         string                   `json:"job_id"`
	CreatedAt     string                   `json:"created_at"`
	Task          string                   `json:"task"`
	Preset        string                   `json:"preset"`
	WorkspaceRoot string                   `json:"workspace_root"`
	DatasetDir    string                   `json:"dataset_dir"`
	Materials     workspace.MaterialSetRef `json:"materials"`
	BatchRoot     string                   `json:"batch_root"`
	DatasetConfig string                   `json:"dataset_config"`
	Generated     int                      `json:"generated"`
}

func MakeDataset(request MakeDatasetRequest) (MakeDatasetResult, error) {
	task, mode, err := normalizeTask(request.Task)
	if err != nil {
		return MakeDatasetResult{}, err
	}
	if request.DatasetDir == "" {
		return MakeDatasetResult{}, fmt.Errorf("--dataset-dir is required")
	}

	state, err := workspace.Ensure(request.WorkspaceRoot)
	if err != nil {
		return MakeDatasetResult{}, err
	}
	notify(request.Writer, "workspace ready: %s\n", state.Layout.Root)

	if err := prepareDatasetDir(request.DatasetDir, request.Force); err != nil {
		return MakeDatasetResult{}, err
	}

	materials, err := materialset.ResolveOrAcquire(state, request.Materials, request.MaterialSource, task)
	if err != nil {
		return MakeDatasetResult{}, err
	}
	notify(request.Writer, "materials ready: %s/%s\n", materials.Ref.Scope, materials.Ref.Name)

	selectedPreset, err := preset.ResolveForWorkspace(state.Layout.PresetsDir, task, request.Preset)
	if err != nil {
		return MakeDatasetResult{}, err
	}
	configPath := filepath.Join(state.Layout.PresetsDir, selectedPreset.FileName)
	cfg := selectedPreset.Config
	if request.OverrideFile != "" {
		override, err := config.LoadOverride(request.OverrideFile)
		if err != nil {
			return MakeDatasetResult{}, err
		}
		cfg = config.ApplyOverride(cfg, override)
		if err := cfg.Validate(); err != nil {
			return MakeDatasetResult{}, err
		}
	}
	cfg = runtimeConfig(cfg, task, selectedPreset.Name)
	if request.OverrideFile != "" {
		configPath = filepath.Join(request.DatasetDir, ".sinan", "effective-config.yaml")
		if err := os.WriteFile(configPath, []byte(config.Format(cfg)), 0o644); err != nil {
			return MakeDatasetResult{}, err
		}
	}

	generatorSpec, generatorInstance, err := backend.Resolve(mode, "native")
	if err != nil {
		return MakeDatasetResult{}, err
	}
	catalog, err := material.LoadCatalog(materials.Root, task)
	if err != nil {
		return MakeDatasetResult{}, err
	}

	rawRoot := filepath.Join(request.DatasetDir, ".sinan", "raw")
	if err := os.MkdirAll(rawRoot, 0o755); err != nil {
		return MakeDatasetResult{}, err
	}
	writer, err := export.NewBatchWriter(
		rawRoot,
		configPath,
		cfg,
		materials.Validation,
		export.BatchLayout{
			Mode:      string(generatorSpec.Mode),
			Backend:   string(generatorSpec.Backend),
			AssetDirs: generatorSpec.AssetDirs(),
		},
	)
	if err != nil {
		return MakeDatasetResult{}, err
	}

	notify(request.Writer, "generating %d samples...\n", cfg.Project.SampleCount)
	for index := 0; index < cfg.Project.SampleCount; index++ {
		record, assets, err := generatorInstance.Generate(index, cfg, catalog)
		if err != nil {
			return MakeDatasetResult{}, err
		}
		checks, err := truth.Validate(record, generatorSpec, cfg.Canvas, func() (export.SampleRecord, error) {
			replayed, _, replayErr := generatorInstance.Generate(index, cfg, catalog)
			return replayed, replayErr
		})
		if err != nil {
			return MakeDatasetResult{}, err
		}
		record.TruthChecks = checks
		if err := writer.WriteSample(record, assets); err != nil {
			return MakeDatasetResult{}, err
		}
		if (index+1)%25 == 0 || index+1 == cfg.Project.SampleCount {
			notify(request.Writer, "generated %d/%d\n", index+1, cfg.Project.SampleCount)
		}
	}
	batchResult, err := writer.Finalize()
	if err != nil {
		return MakeDatasetResult{}, err
	}

	notify(request.Writer, "running batch QA...\n")
	if _, err := qa.InspectBatch(batchResult.BatchRoot); err != nil {
		return MakeDatasetResult{}, err
	}
	notify(request.Writer, "building dataset directory...\n")
	datasetResult, err := dataset.Build(dataset.BuildRequest{
		Task:       task,
		BatchRoot:  batchResult.BatchRoot,
		DatasetDir: request.DatasetDir,
		Force:      true,
	})
	if err != nil {
		return MakeDatasetResult{}, err
	}

	if err := copyFile(batchResult.Manifest, filepath.Join(request.DatasetDir, ".sinan", "manifest.json")); err != nil {
		return MakeDatasetResult{}, err
	}
	jobID := cfg.Project.BatchID
	jobPath := filepath.Join(request.DatasetDir, ".sinan", "job.json")
	job := jobRecord{
		JobID:         jobID,
		CreatedAt:     time.Now().UTC().Format(time.RFC3339),
		Task:          task,
		Preset:        selectedPreset.Name,
		WorkspaceRoot: state.Layout.Root,
		DatasetDir:    request.DatasetDir,
		Materials:     materials.Ref,
		BatchRoot:     batchResult.BatchRoot,
		DatasetConfig: datasetResult.DatasetConfig,
		Generated:     batchResult.GeneratedCount,
	}
	if err := writeJSON(jobPath, job); err != nil {
		return MakeDatasetResult{}, err
	}

	notify(request.Writer, "done: %s\n", datasetResult.DatasetConfig)
	return MakeDatasetResult{
		WorkspaceRoot: state.Layout.Root,
		DatasetDir:    request.DatasetDir,
		BatchRoot:     batchResult.BatchRoot,
		DatasetConfig: datasetResult.DatasetConfig,
		JobPath:       jobPath,
		Preset:        selectedPreset.Name,
		Task:          task,
		Materials:     materials.Ref,
		Generated:     batchResult.GeneratedCount,
	}, nil
}

func normalizeTask(task string) (string, string, error) {
	switch task {
	case "", "group1":
		return "group1", "click", nil
	case "group2":
		return "group2", "slide", nil
	default:
		return "", "", fmt.Errorf("unsupported task: %s", task)
	}
}

func runtimeConfig(base config.Config, task string, presetName string) config.Config {
	cfg := base
	now := time.Now().UTC()
	cfg.Project.BatchID = fmt.Sprintf("%s_%s_%s", task, presetName, now.Format("20060102_150405"))
	cfg.Project.DatasetName = fmt.Sprintf("sinan_%s_%s", task, presetName)
	cfg.Project.Split = "train"
	return cfg
}

func prepareDatasetDir(datasetDir string, force bool) error {
	managedPaths := []string{
		filepath.Join(datasetDir, "scene-yolo"),
		filepath.Join(datasetDir, "query-yolo"),
		filepath.Join(datasetDir, "master"),
		filepath.Join(datasetDir, "tile"),
		filepath.Join(datasetDir, "splits"),
		filepath.Join(datasetDir, "dataset.json"),
		filepath.Join(datasetDir, "dataset.yaml"),
		filepath.Join(datasetDir, "images"),
		filepath.Join(datasetDir, "labels"),
		filepath.Join(datasetDir, ".sinan"),
	}
	if !force {
		for _, path := range managedPaths {
			if _, err := os.Stat(path); err == nil {
				return fmt.Errorf("dataset directory %s already contains generated data; pass --force to overwrite", datasetDir)
			}
		}
	}
	for _, path := range managedPaths {
		if err := os.RemoveAll(path); err != nil {
			return err
		}
	}
	return os.MkdirAll(filepath.Join(datasetDir, ".sinan"), 0o755)
}

func notify(writer io.Writer, format string, args ...any) {
	if writer == nil {
		return
	}
	fmt.Fprintf(writer, format, args...)
}

func writeJSON(path string, value any) error {
	content, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(content, '\n'), 0o644)
}

func copyFile(source string, destination string) error {
	if err := os.MkdirAll(filepath.Dir(destination), 0o755); err != nil {
		return err
	}
	in, err := os.Open(source)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(destination)
	if err != nil {
		return err
	}
	defer out.Close()
	_, err = io.Copy(out, in)
	return err
}
