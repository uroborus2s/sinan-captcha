package app

import (
	cryptorand "crypto/rand"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"hash/fnv"
	"io"
	mathrand "math/rand"
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
	RuntimeSeed    int64
	Writer         io.Writer
}

type MakeDatasetResult struct {
	WorkspaceRoot string                     `json:"workspace_root"`
	DatasetDir    string                     `json:"dataset_dir"`
	BatchRoot     string                     `json:"batch_root"`
	DatasetConfig string                     `json:"dataset_config"`
	JobPath       string                     `json:"job_path"`
	Preset        string                     `json:"preset"`
	Task          string                     `json:"task"`
	MaterialSets  []workspace.MaterialSetRef `json:"material_sets"`
	Seed          int64                      `json:"seed"`
	Generated     int                        `json:"generated"`
}

type jobRecord struct {
	JobID         string                     `json:"job_id"`
	CreatedAt     string                     `json:"created_at"`
	Task          string                     `json:"task"`
	Preset        string                     `json:"preset"`
	WorkspaceRoot string                     `json:"workspace_root"`
	DatasetDir    string                     `json:"dataset_dir"`
	MaterialSets  []workspace.MaterialSetRef `json:"material_sets"`
	BatchRoot     string                     `json:"batch_root"`
	DatasetConfig string                     `json:"dataset_config"`
	Seed          int64                      `json:"seed"`
	Generated     int                        `json:"generated"`
}

type materialPoolEntry struct {
	Ref        workspace.MaterialSetRef
	Root       string
	Validation material.ValidationSummary
	Catalog    material.Catalog
	Selector   string
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

	materials, err := materialset.ResolveOrAcquirePool(state, request.Materials, request.MaterialSource, task)
	if err != nil {
		return MakeDatasetResult{}, err
	}
	materialPool, err := loadMaterialPool(task, materials)
	if err != nil {
		return MakeDatasetResult{}, err
	}
	notify(request.Writer, "materials ready: %d packs\n", len(materialPool))

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
	runSeed, err := resolveRuntimeSeed(cfg.Project.Seed, request.RuntimeSeed)
	if err != nil {
		return MakeDatasetResult{}, err
	}
	cfg = runtimeConfig(cfg, task, selectedPreset.Name, runSeed)
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
	rawRoot := filepath.Join(request.DatasetDir, ".sinan", "raw")
	if err := os.MkdirAll(rawRoot, 0o755); err != nil {
		return MakeDatasetResult{}, err
	}
	writer, err := export.NewBatchWriter(
		rawRoot,
		configPath,
		cfg,
		poolValidationSummaries(materialPool),
		poolSelectors(materialPool),
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
	poolRng := mathrand.New(mathrand.NewSource(cfg.Project.Seed))
	for index := 0; index < cfg.Project.SampleCount; index++ {
		selectedMaterial := materialPool[poolRng.Intn(len(materialPool))]
		sampleCfg := cfg
		sampleCfg.Project.Seed = materialSeed(cfg.Project.Seed, selectedMaterial.Selector)

		record, assets, err := generatorInstance.Generate(index, sampleCfg, selectedMaterial.Catalog)
		if err != nil {
			return MakeDatasetResult{}, err
		}
		annotateMaterialSource(&record, selectedMaterial.Selector)
		checks, err := truth.Validate(record, generatorSpec, cfg.Canvas, func() (export.SampleRecord, error) {
			replayed, _, replayErr := generatorInstance.Generate(index, sampleCfg, selectedMaterial.Catalog)
			if replayErr == nil {
				annotateMaterialSource(&replayed, selectedMaterial.Selector)
			}
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
		MaterialSets:  poolRefs(materialPool),
		BatchRoot:     batchResult.BatchRoot,
		DatasetConfig: datasetResult.DatasetConfig,
		Seed:          cfg.Project.Seed,
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
		MaterialSets:  poolRefs(materialPool),
		Seed:          cfg.Project.Seed,
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

func runtimeConfig(base config.Config, task string, presetName string, runSeed int64) config.Config {
	cfg := base
	now := time.Now().UTC()
	cfg.Project.BatchID = fmt.Sprintf("%s_%s_%s", task, presetName, now.Format("20060102_150405"))
	cfg.Project.DatasetName = fmt.Sprintf("sinan_%s_%s", task, presetName)
	cfg.Project.Split = "train"
	cfg.Project.Seed = runSeed
	return cfg
}

func prepareDatasetDir(datasetDir string, force bool) error {
	managedPaths := []string{
		filepath.Join(datasetDir, "proposal-yolo"),
		filepath.Join(datasetDir, "embedding"),
		filepath.Join(datasetDir, "eval"),
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

func loadMaterialPool(task string, results []materialset.SyncResult) ([]materialPoolEntry, error) {
	pool := make([]materialPoolEntry, 0, len(results))
	for _, result := range results {
		catalog, err := material.LoadCatalog(result.Root, task)
		if err != nil {
			return nil, err
		}
		pool = append(pool, materialPoolEntry{
			Ref:        result.Ref,
			Root:       result.Root,
			Validation: result.Validation,
			Catalog:    catalog,
			Selector:   fmt.Sprintf("%s/%s", result.Ref.Scope, result.Ref.Name),
		})
	}
	return pool, nil
}

func poolValidationSummaries(pool []materialPoolEntry) []material.ValidationSummary {
	summaries := make([]material.ValidationSummary, 0, len(pool))
	for _, entry := range pool {
		summaries = append(summaries, entry.Validation)
	}
	return summaries
}

func poolSelectors(pool []materialPoolEntry) []string {
	selectors := make([]string, 0, len(pool))
	for _, entry := range pool {
		selectors = append(selectors, entry.Selector)
	}
	return selectors
}

func poolRefs(pool []materialPoolEntry) []workspace.MaterialSetRef {
	refs := make([]workspace.MaterialSetRef, 0, len(pool))
	for _, entry := range pool {
		refs = append(refs, entry.Ref)
	}
	return refs
}

func resolveRuntimeSeed(baseSeed int64, override int64) (int64, error) {
	if override != 0 {
		return override, nil
	}
	var raw [8]byte
	if _, err := cryptorand.Read(raw[:]); err != nil {
		return 0, err
	}
	randomSeed := int64(binary.LittleEndian.Uint64(raw[:]) & 0x7fffffffffffffff)
	if randomSeed == 0 {
		randomSeed = time.Now().UTC().UnixNano()
	}
	return baseSeed ^ randomSeed ^ time.Now().UTC().UnixNano(), nil
}

func materialSeed(baseSeed int64, selector string) int64 {
	hasher := fnv.New64a()
	_, _ = hasher.Write([]byte(selector))
	mixed := baseSeed ^ int64(hasher.Sum64()&0x7fffffffffffffff)
	if mixed == 0 {
		return baseSeed + 1
	}
	return mixed
}

func annotateMaterialSource(record *export.SampleRecord, selector string) {
	record.MaterialSet = selector
	if record.SourceSignature == "" {
		record.SourceSignature = selector
		return
	}
	record.SourceSignature = selector + "|" + record.SourceSignature
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
