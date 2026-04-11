package app

import (
	"encoding/json"
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"sinan-captcha/generator/internal/config"
	"sinan-captcha/generator/internal/export"
	"sinan-captcha/generator/internal/materialset"
	"sinan-captcha/generator/internal/workspace"
)

func TestMakeDatasetBuildsGroup1TrainingDirectory(t *testing.T) {
	workspaceRoot := filepath.Join(t.TempDir(), "workspace")
	materialsRoot := createMaterialsPack(t)
	trainingDir := filepath.Join(t.TempDir(), "train-group1")

	result, err := MakeDataset(MakeDatasetRequest{
		Task:           "group1",
		Preset:         "smoke",
		WorkspaceRoot:  workspaceRoot,
		DatasetDir:     trainingDir,
		MaterialSource: materialsRoot,
	})
	if err != nil {
		t.Fatalf("make dataset: %v", err)
	}

	assertFileExists(t, filepath.Join(trainingDir, "dataset.json"))
	assertDirHasFiles(t, filepath.Join(trainingDir, "proposal-yolo", "images", "train"))
	assertDirHasFiles(t, filepath.Join(trainingDir, "proposal-yolo", "labels", "train"))
	assertDirHasFiles(t, filepath.Join(trainingDir, "embedding", "queries", "train"))
	assertDirHasFiles(t, filepath.Join(trainingDir, "embedding", "candidates", "train"))
	assertFileExists(t, filepath.Join(trainingDir, "embedding", "pairs.jsonl"))
	assertFileExists(t, filepath.Join(trainingDir, "embedding", "triplets.jsonl"))
	assertDirHasFiles(t, filepath.Join(trainingDir, "eval", "query", "train"))
	assertDirHasFiles(t, filepath.Join(trainingDir, "eval", "scene", "train"))
	assertFileExists(t, filepath.Join(trainingDir, "eval", "labels.jsonl"))
	assertFileExists(t, filepath.Join(trainingDir, "splits", "train.jsonl"))
	assertFileExists(t, filepath.Join(trainingDir, "splits", "val.jsonl"))
	assertFileExists(t, filepath.Join(trainingDir, "splits", "test.jsonl"))
	assertFileExists(t, filepath.Join(trainingDir, ".sinan", "job.json"))
	assertFileExists(t, filepath.Join(trainingDir, ".sinan", "manifest.json"))
	assertDirHasFiles(t, filepath.Join(trainingDir, ".sinan", "raw", filepath.Base(result.BatchRoot), "scene"))
	assertDirHasFiles(t, filepath.Join(trainingDir, ".sinan", "raw", filepath.Base(result.BatchRoot), "query"))
	assertGroup1DatasetJSONReferencesPipelineArtifacts(t, filepath.Join(trainingDir, "dataset.json"))
	assertGroup1SplitCarriesInstanceIdentity(t, filepath.Join(trainingDir, "splits", "train.jsonl"))
	assertGroup1EvalCarriesInstanceIdentity(t, filepath.Join(trainingDir, "eval", "labels.jsonl"))
	assertGroup1EmbeddingMetadataCarriesInstanceIdentity(t, filepath.Join(trainingDir, "embedding", "pairs.jsonl"))
	assertGroup1EmbeddingTripletsCarryInstanceIdentity(t, filepath.Join(trainingDir, "embedding", "triplets.jsonl"))
	assertGroup1RawBatchCarriesInstanceIdentity(t, filepath.Join(trainingDir, ".sinan", "raw", filepath.Base(result.BatchRoot), "labels.jsonl"))
	if !strings.Contains(result.DatasetConfig, filepath.Join(trainingDir, "dataset.json")) {
		t.Fatalf("unexpected dataset config path: %s", result.DatasetConfig)
	}
}

func TestMakeDatasetBuildsGroup2TrainingDirectory(t *testing.T) {
	workspaceRoot := filepath.Join(t.TempDir(), "workspace")
	materialsRoot := createMaterialsPack(t)
	trainingDir := filepath.Join(t.TempDir(), "train-group2")

	result, err := MakeDataset(MakeDatasetRequest{
		Task:           "group2",
		Preset:         "smoke",
		WorkspaceRoot:  workspaceRoot,
		DatasetDir:     trainingDir,
		MaterialSource: materialsRoot,
	})
	if err != nil {
		t.Fatalf("make dataset: %v", err)
	}

	assertFileExists(t, filepath.Join(trainingDir, "dataset.json"))
	assertDirHasFiles(t, filepath.Join(trainingDir, "master", "train"))
	assertDirHasFiles(t, filepath.Join(trainingDir, "tile", "train"))
	assertFileExists(t, filepath.Join(trainingDir, "splits", "train.jsonl"))
	assertFileExists(t, filepath.Join(trainingDir, "splits", "val.jsonl"))
	assertFileExists(t, filepath.Join(trainingDir, "splits", "test.jsonl"))
	assertDirHasFiles(t, filepath.Join(trainingDir, ".sinan", "raw", filepath.Base(result.BatchRoot), "master"))
	assertDirHasFiles(t, filepath.Join(trainingDir, ".sinan", "raw", filepath.Base(result.BatchRoot), "tile"))
	assertDatasetJSONReferencesPairedSplits(t, filepath.Join(trainingDir, "dataset.json"))
	if !strings.Contains(result.DatasetConfig, filepath.Join(trainingDir, "dataset.json")) {
		t.Fatalf("unexpected dataset config path: %s", result.DatasetConfig)
	}
}

func TestMakeDatasetUsesWorkspacePresetOverride(t *testing.T) {
	workspaceRoot := filepath.Join(t.TempDir(), "workspace")
	materialsRoot := createMaterialsPack(t)
	trainingDir := filepath.Join(t.TempDir(), "train-group1-hard")

	state, err := workspace.Ensure(workspaceRoot)
	if err != nil {
		t.Fatalf("ensure workspace: %v", err)
	}
	override := config.Config{
		Project: config.ProjectConfig{
			DatasetName: "sinan_group1_hard",
			Split:       "train",
			SampleCount: 3,
			BatchID:     "group1_hd_0001",
			Seed:        20260404,
		},
		Canvas: config.CanvasConfig{
			SceneWidth:  300,
			SceneHeight: 150,
			QueryWidth:  120,
			QueryHeight: 36,
		},
		Sampling: config.SamplingConfig{
			TargetCountMin:     2,
			TargetCountMax:     3,
			DistractorCountMin: 2,
			DistractorCountMax: 4,
		},
		Slide: config.SlideConfig{
			GapWidth:          52,
			GapHeight:         52,
			MaxVerticalJitter: 4,
		},
		Effects: config.EffectsConfig{
			Common: config.CommonEffectsConfig{
				SceneVeilStrength:       1.4,
				BackgroundBlurRadiusMin: 1,
				BackgroundBlurRadiusMax: 1,
			},
			Click: config.ClickEffectsConfig{
				IconShadowAlphaMin:    0.24,
				IconShadowAlphaMax:    0.24,
				IconShadowOffsetXMin:  2,
				IconShadowOffsetXMax:  2,
				IconShadowOffsetYMin:  3,
				IconShadowOffsetYMax:  3,
				IconEdgeBlurRadiusMin: 1,
				IconEdgeBlurRadiusMax: 1,
			},
		},
	}
	overridePath := filepath.Join(state.Layout.PresetsDir, "group1.hard.yaml")
	if err := os.WriteFile(overridePath, []byte(config.Format(override)), 0o644); err != nil {
		t.Fatalf("write override preset: %v", err)
	}

	result, err := MakeDataset(MakeDatasetRequest{
		Task:           "group1",
		Preset:         "hard",
		WorkspaceRoot:  workspaceRoot,
		DatasetDir:     trainingDir,
		MaterialSource: materialsRoot,
	})
	if err != nil {
		t.Fatalf("make dataset with workspace override: %v", err)
	}

	if got, want := result.Generated, 3; got != want {
		t.Fatalf("expected workspace override sample count to apply, got %d want %d", got, want)
	}
}

func TestMakeDatasetAppliesRuntimeOverrideFile(t *testing.T) {
	workspaceRoot := filepath.Join(t.TempDir(), "workspace")
	materialsRoot := createMaterialsPack(t)
	trainingDir := filepath.Join(t.TempDir(), "train-group1-override")
	overrideFile := filepath.Join(t.TempDir(), "generator-override.json")
	overridePayload := `{
  "project": {"sample_count": 3},
  "sampling": {
    "target_count_min": 2,
    "target_count_max": 2,
    "distractor_count_min": 0,
    "distractor_count_max": 0
  },
  "effects": {
    "common": {
      "scene_veil_strength": 1.45,
      "background_blur_radius_min": 1,
      "background_blur_radius_max": 2
    },
    "click": {
      "icon_shadow_alpha_min": 0.28,
      "icon_shadow_alpha_max": 0.36,
      "icon_shadow_offset_x_min": 2,
      "icon_shadow_offset_x_max": 3,
      "icon_shadow_offset_y_min": 3,
      "icon_shadow_offset_y_max": 4,
      "icon_edge_blur_radius_min": 1,
      "icon_edge_blur_radius_max": 2
    }
  }
}`
	if err := os.WriteFile(overrideFile, []byte(overridePayload), 0o644); err != nil {
		t.Fatalf("write runtime override file: %v", err)
	}

	result, err := MakeDataset(MakeDatasetRequest{
		Task:           "group1",
		Preset:         "smoke",
		WorkspaceRoot:  workspaceRoot,
		DatasetDir:     trainingDir,
		MaterialSource: materialsRoot,
		OverrideFile:   overrideFile,
	})
	if err != nil {
		t.Fatalf("make dataset with runtime override: %v", err)
	}

	if got, want := result.Generated, 3; got != want {
		t.Fatalf("expected runtime override sample count to apply, got %d want %d", got, want)
	}
}

func TestMakeDatasetBuildsGroup1FromGroup1OnlyMaterials(t *testing.T) {
	workspaceRoot := filepath.Join(t.TempDir(), "workspace")
	materialsRoot := createGroup1OnlyMaterialsPack(t)
	trainingDir := filepath.Join(t.TempDir(), "train-group1")

	result, err := MakeDataset(MakeDatasetRequest{
		Task:           "group1",
		Preset:         "smoke",
		WorkspaceRoot:  workspaceRoot,
		DatasetDir:     trainingDir,
		MaterialSource: materialsRoot,
	})
	if err != nil {
		t.Fatalf("make dataset from group1-only materials: %v", err)
	}

	assertFileExists(t, filepath.Join(trainingDir, "dataset.json"))
	if got, want := result.Generated, 20; got != want {
		t.Fatalf("expected smoke preset to generate %d samples, got %d", want, got)
	}
}

func TestMakeDatasetBuildsGroup2FromGroup2OnlyMaterials(t *testing.T) {
	workspaceRoot := filepath.Join(t.TempDir(), "workspace")
	materialsRoot := createGroup2OnlyMaterialsPack(t)
	trainingDir := filepath.Join(t.TempDir(), "train-group2")

	result, err := MakeDataset(MakeDatasetRequest{
		Task:           "group2",
		Preset:         "smoke",
		WorkspaceRoot:  workspaceRoot,
		DatasetDir:     trainingDir,
		MaterialSource: materialsRoot,
	})
	if err != nil {
		t.Fatalf("make dataset from group2-only materials: %v", err)
	}

	assertFileExists(t, filepath.Join(trainingDir, "dataset.json"))
	if got, want := result.Generated, 20; got != want {
		t.Fatalf("expected smoke preset to generate %d samples, got %d", want, got)
	}
}

func TestMakeDatasetRandomlyUsesMultipleMaterialSetsForGroup2(t *testing.T) {
	workspaceRoot := filepath.Join(t.TempDir(), "workspace")
	state, err := workspace.Ensure(workspaceRoot)
	if err != nil {
		t.Fatalf("ensure workspace: %v", err)
	}

	if _, err := materialset.ImportLocal(state, createNamedGroup2MaterialsPack(t, "alpha"), "alpha", "group2"); err != nil {
		t.Fatalf("import alpha materials: %v", err)
	}
	if _, err := materialset.ImportLocal(state, createNamedGroup2MaterialsPack(t, "beta"), "beta", "group2"); err != nil {
		t.Fatalf("import beta materials: %v", err)
	}

	trainingDir := filepath.Join(t.TempDir(), "train-group2")
	result, err := MakeDataset(MakeDatasetRequest{
		Task:          "group2",
		Preset:        "smoke",
		WorkspaceRoot: workspaceRoot,
		DatasetDir:    trainingDir,
		RuntimeSeed:   20260409,
	})
	if err != nil {
		t.Fatalf("make dataset with multiple materials: %v", err)
	}

	records := readBatchRecords(t, filepath.Join(result.BatchRoot, "labels.jsonl"))
	seenSets := map[string]struct{}{}
	for _, record := range records {
		seenSets[record.MaterialSet] = struct{}{}
	}
	if len(seenSets) < 2 {
		t.Fatalf("expected multiple material sets to be used, got %v", seenSets)
	}
}

func TestMakeDatasetUsesDifferentSourceSignaturesAcrossRuns(t *testing.T) {
	workspaceRoot := filepath.Join(t.TempDir(), "workspace")
	state, err := workspace.Ensure(workspaceRoot)
	if err != nil {
		t.Fatalf("ensure workspace: %v", err)
	}

	if _, err := materialset.ImportLocal(state, createNamedGroup1MaterialsPack(t, "alpha"), "alpha", "group1"); err != nil {
		t.Fatalf("import alpha materials: %v", err)
	}
	if _, err := materialset.ImportLocal(state, createNamedGroup1MaterialsPack(t, "beta"), "beta", "group1"); err != nil {
		t.Fatalf("import beta materials: %v", err)
	}

	runA, err := MakeDataset(MakeDatasetRequest{
		Task:          "group1",
		Preset:        "smoke",
		WorkspaceRoot: workspaceRoot,
		DatasetDir:    filepath.Join(t.TempDir(), "train-group1-a"),
		RuntimeSeed:   111,
	})
	if err != nil {
		t.Fatalf("make dataset run A: %v", err)
	}
	runB, err := MakeDataset(MakeDatasetRequest{
		Task:          "group1",
		Preset:        "smoke",
		WorkspaceRoot: workspaceRoot,
		DatasetDir:    filepath.Join(t.TempDir(), "train-group1-b"),
		RuntimeSeed:   222,
	})
	if err != nil {
		t.Fatalf("make dataset run B: %v", err)
	}

	signaturesA := readSourceSignatures(t, filepath.Join(runA.BatchRoot, "labels.jsonl"))
	signaturesB := readSourceSignatures(t, filepath.Join(runB.BatchRoot, "labels.jsonl"))
	if strings.Join(signaturesA, "\n") == strings.Join(signaturesB, "\n") {
		t.Fatalf("expected different source signatures across runs, got identical sequences")
	}
}

func TestMakeDatasetUsesExplicitMaterialSelectorAsSinglePack(t *testing.T) {
	workspaceRoot := filepath.Join(t.TempDir(), "workspace")
	state, err := workspace.Ensure(workspaceRoot)
	if err != nil {
		t.Fatalf("ensure workspace: %v", err)
	}

	if _, err := materialset.ImportLocal(state, createNamedGroup2MaterialsPack(t, "alpha"), "alpha", "group2"); err != nil {
		t.Fatalf("import alpha materials: %v", err)
	}
	if _, err := materialset.ImportLocal(state, createNamedGroup2MaterialsPack(t, "beta"), "beta", "group2"); err != nil {
		t.Fatalf("import beta materials: %v", err)
	}

	result, err := MakeDataset(MakeDatasetRequest{
		Task:          "group2",
		Preset:        "smoke",
		WorkspaceRoot: workspaceRoot,
		DatasetDir:    filepath.Join(t.TempDir(), "train-group2"),
		Materials:     "local/alpha",
		RuntimeSeed:   20260410,
	})
	if err != nil {
		t.Fatalf("make dataset with explicit selector: %v", err)
	}

	records := readBatchRecords(t, filepath.Join(result.BatchRoot, "labels.jsonl"))
	for _, record := range records {
		if record.MaterialSet != "local/alpha" {
			t.Fatalf("expected all records to use local/alpha, got %s", record.MaterialSet)
		}
	}
}

func createMaterialsPack(t *testing.T) string {
	t.Helper()
	root := filepath.Join(t.TempDir(), "materials")
	writeMaterialsManifest(t, filepath.Join(root, "manifests", "materials.yaml"))
	writeGroup1TemplatesManifest(t, filepath.Join(root, "manifests", "group1.templates.yaml"))
	writeGroup2Manifest(t, filepath.Join(root, "manifests", "group2.shapes.yaml"))
	writePNG(t, filepath.Join(root, "backgrounds", "bg_001.png"), 320, 180)
	writePNG(t, filepath.Join(root, "backgrounds", "bg_002.png"), 320, 180)
	writeMaskIconPNG(t, filepath.Join(root, "group1", "icons", "tpl_house", "var_house_001.png"), 48, 48)
	writeMaskIconPNG(t, filepath.Join(root, "group1", "icons", "tpl_leaf", "var_leaf_001.png"), 48, 48)
	writeMaskIconPNG(t, filepath.Join(root, "group2", "shapes", "shape_ticket", "001.png"), 48, 48)
	writeMaskIconPNG(t, filepath.Join(root, "group2", "shapes", "shape_cloud", "001.png"), 48, 48)
	return root
}

func createGroup1OnlyMaterialsPack(t *testing.T) string {
	t.Helper()
	root := filepath.Join(t.TempDir(), "materials-group1")
	writeMaterialsManifest(t, filepath.Join(root, "manifests", "materials.yaml"))
	writeGroup1TemplatesManifest(t, filepath.Join(root, "manifests", "group1.templates.yaml"))
	writePNG(t, filepath.Join(root, "backgrounds", "bg_001.png"), 320, 180)
	writePNG(t, filepath.Join(root, "backgrounds", "bg_002.png"), 320, 180)
	writeMaskIconPNG(t, filepath.Join(root, "group1", "icons", "tpl_house", "var_house_001.png"), 48, 48)
	writeMaskIconPNG(t, filepath.Join(root, "group1", "icons", "tpl_leaf", "var_leaf_001.png"), 48, 48)
	return root
}

func createGroup2OnlyMaterialsPack(t *testing.T) string {
	t.Helper()
	root := filepath.Join(t.TempDir(), "materials-group2")
	writeMaterialsManifest(t, filepath.Join(root, "manifests", "materials.yaml"))
	writeGroup2Manifest(t, filepath.Join(root, "manifests", "group2.shapes.yaml"))
	writePNG(t, filepath.Join(root, "backgrounds", "bg_001.png"), 320, 180)
	writePNG(t, filepath.Join(root, "backgrounds", "bg_002.png"), 320, 180)
	writeMaskIconPNG(t, filepath.Join(root, "group2", "shapes", "shape_ticket", "001.png"), 48, 48)
	writeMaskIconPNG(t, filepath.Join(root, "group2", "shapes", "shape_cloud", "001.png"), 48, 48)
	return root
}

func createNamedGroup1MaterialsPack(t *testing.T, name string) string {
	t.Helper()
	root := filepath.Join(t.TempDir(), "materials-"+name)
	writeMaterialsManifest(t, filepath.Join(root, "manifests", "materials.yaml"))
	writeNamedGroup1TemplatesManifest(t, filepath.Join(root, "manifests", "group1.templates.yaml"), name)
	writePNG(t, filepath.Join(root, "backgrounds", name+"_bg_001.png"), 320, 180)
	writePNG(t, filepath.Join(root, "backgrounds", name+"_bg_002.png"), 320, 180)
	writeMaskIconPNG(t, filepath.Join(root, "group1", "icons", "tpl_"+name+"_house", "var_"+name+"_house_001.png"), 48, 48)
	writeMaskIconPNG(t, filepath.Join(root, "group1", "icons", "tpl_"+name+"_leaf", "var_"+name+"_leaf_001.png"), 48, 48)
	return root
}

func createNamedGroup2MaterialsPack(t *testing.T, name string) string {
	t.Helper()
	root := filepath.Join(t.TempDir(), "materials-"+name)
	writeMaterialsManifest(t, filepath.Join(root, "manifests", "materials.yaml"))
	writeNamedGroup2Manifest(t, filepath.Join(root, "manifests", "group2.shapes.yaml"), name)
	writePNG(t, filepath.Join(root, "backgrounds", name+"_bg_001.png"), 320, 180)
	writePNG(t, filepath.Join(root, "backgrounds", name+"_bg_002.png"), 320, 180)
	writeMaskIconPNG(t, filepath.Join(root, "group2", "shapes", name+"_shape_ticket", name+"_ticket_001.png"), 48, 48)
	writeMaskIconPNG(t, filepath.Join(root, "group2", "shapes", name+"_shape_cloud", name+"_cloud_001.png"), 48, 48)
	return root
}

func writeMaterialsManifest(t *testing.T, path string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir manifest dir: %v", err)
	}
	content := "schema_version: 3\n"
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write manifest: %v", err)
	}
}

func writeGroup1TemplatesManifest(t *testing.T, path string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir manifest dir: %v", err)
	}
	content := strings.Join([]string{
		"schema_version: 3",
		"task: group1",
		"mode: instance_matching",
		"",
		"templates:",
		"  - template_id: tpl_house",
		"    zh_name: 房子",
		"    family: building",
		"    tags: [house, home]",
		"    status: active",
		"    variants:",
		"      - variant_id: var_house_001",
		"        source: generator_seed",
		"        source_ref: house_seed_001",
		"        style: flat",
		"  - template_id: tpl_leaf",
		"    zh_name: 叶子",
		"    family: nature",
		"    tags: [leaf]",
		"    status: active",
		"    variants:",
		"      - variant_id: var_leaf_001",
		"        source: generator_seed",
		"        source_ref: leaf_seed_001",
		"        style: flat",
		"",
	}, "\n")
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write manifest: %v", err)
	}
}

func writeGroup2Manifest(t *testing.T, path string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir manifest dir: %v", err)
	}
	content := strings.Join([]string{
		"shapes:",
		"  - id: 0",
		"    name: shape_ticket",
		"    zh_name: 票形缺口",
		"  - id: 1",
		"    name: shape_cloud",
		"    zh_name: 云形缺口",
		"",
	}, "\n")
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write manifest: %v", err)
	}
}

func writeNamedGroup1TemplatesManifest(t *testing.T, path string, name string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir manifest dir: %v", err)
	}
	content := strings.Join([]string{
		"schema_version: 3",
		"task: group1",
		"mode: instance_matching",
		"",
		"templates:",
		"  - template_id: tpl_" + name + "_house",
		"    zh_name: " + name + "_房子",
		"    family: building",
		"    tags: [" + name + ", house]",
		"    status: active",
		"    variants:",
		"      - variant_id: var_" + name + "_house_001",
		"        source: generator_seed",
		"        source_ref: " + name + "_house_seed_001",
		"        style: flat",
		"  - template_id: tpl_" + name + "_leaf",
		"    zh_name: " + name + "_叶子",
		"    family: nature",
		"    tags: [" + name + ", leaf]",
		"    status: active",
		"    variants:",
		"      - variant_id: var_" + name + "_leaf_001",
		"        source: generator_seed",
		"        source_ref: " + name + "_leaf_seed_001",
		"        style: flat",
		"",
	}, "\n")
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write manifest: %v", err)
	}
}

func writeNamedGroup2Manifest(t *testing.T, path string, name string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir manifest dir: %v", err)
	}
	content := strings.Join([]string{
		"shapes:",
		"  - id: 0",
		"    name: " + name + "_shape_ticket",
		"    zh_name: " + name + "_票形缺口",
		"  - id: 1",
		"    name: " + name + "_shape_cloud",
		"    zh_name: " + name + "_云形缺口",
		"",
	}, "\n")
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write manifest: %v", err)
	}
}

func writePNG(t *testing.T, path string, width int, height int) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir png dir: %v", err)
	}
	img := image.NewRGBA(image.Rect(0, 0, width, height))
	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			img.SetRGBA(x, y, color.RGBA{R: uint8(30 + x%80), G: uint8(60 + y%80), B: 180, A: 255})
		}
	}
	file, err := os.Create(path)
	if err != nil {
		t.Fatalf("create png: %v", err)
	}
	defer file.Close()
	if err := png.Encode(file, img); err != nil {
		t.Fatalf("encode png: %v", err)
	}
}

func writeMaskIconPNG(t *testing.T, path string, width int, height int) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir png dir: %v", err)
	}
	img := image.NewRGBA(image.Rect(0, 0, width, height))
	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			alpha := uint8(0)
			if x > 4 && x < width/3 && y > height/4 && y < height-height/4 {
				alpha = 255
			}
			if x >= width/3 {
				top := height/2 - (x-width/3)/2
				bottom := height/2 + (x-width/3)/3
				if y >= top && y <= bottom {
					alpha = 255
				}
			}
			if alpha > 0 {
				img.SetRGBA(x, y, color.RGBA{R: 255, G: 255, B: 255, A: alpha})
			}
		}
	}
	file, err := os.Create(path)
	if err != nil {
		t.Fatalf("create png: %v", err)
	}
	defer file.Close()
	if err := png.Encode(file, img); err != nil {
		t.Fatalf("encode png: %v", err)
	}
}

func assertFileExists(t *testing.T, path string) {
	t.Helper()
	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("expected file %s: %v", path, err)
	}
	if info.IsDir() {
		t.Fatalf("expected %s to be a file", path)
	}
}

func assertDirHasFiles(t *testing.T, path string) {
	t.Helper()
	entries, err := os.ReadDir(path)
	if err != nil {
		t.Fatalf("expected directory %s: %v", path, err)
	}
	if len(entries) == 0 {
		t.Fatalf("expected directory %s to contain files", path)
	}
}

func assertGroup1DatasetJSONReferencesPipelineArtifacts(t *testing.T, path string) {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read dataset json %s: %v", path, err)
	}
	text := string(content)
	for _, expected := range []string{
		`"task": "group1"`,
		`"format": "sinan.group1.instance_matching.v1"`,
		`"proposal_detector"`,
		`"proposal-yolo/dataset.yaml"`,
		`"embedding"`,
		`"pairs_jsonl": "embedding/pairs.jsonl"`,
		`"triplets_jsonl": "embedding/triplets.jsonl"`,
		`"eval"`,
		`"labels_jsonl": "eval/labels.jsonl"`,
		`"train": "splits/train.jsonl"`,
	} {
		if !strings.Contains(text, expected) {
			t.Fatalf("dataset json missing %s:\n%s", expected, text)
		}
	}
	for _, unexpected := range []string{`"scene-yolo/`, `"query-yolo/`, `"scene_detector"`, `"query_parser"`, `"matcher"`} {
		if strings.Contains(text, unexpected) {
			t.Fatalf("dataset json should not contain legacy field %s:\n%s", unexpected, text)
		}
	}
}

func assertGroup1EvalCarriesInstanceIdentity(t *testing.T, path string) {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read eval labels %s: %v", path, err)
	}
	text := string(content)
	for _, expected := range []string{`"query_items"`, `"scene_targets"`, `"asset_id"`, `"template_id"`, `"variant_id"`} {
		if !strings.Contains(text, expected) {
			t.Fatalf("eval labels missing %s:\n%s", expected, text)
		}
	}
}

func assertGroup1EmbeddingMetadataCarriesInstanceIdentity(t *testing.T, path string) {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read embedding pairs %s: %v", path, err)
	}
	text := string(content)
	for _, expected := range []string{`"query_item"`, `"candidate"`, `"label"`, `"asset_id"`, `"template_id"`, `"variant_id"`} {
		if !strings.Contains(text, expected) {
			t.Fatalf("embedding pairs missing %s:\n%s", expected, text)
		}
	}
}

func assertGroup1EmbeddingTripletsCarryInstanceIdentity(t *testing.T, path string) {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read embedding triplets %s: %v", path, err)
	}
	text := string(content)
	for _, expected := range []string{`"anchor"`, `"positive"`, `"negative"`, `"asset_id"`, `"template_id"`, `"variant_id"`} {
		if !strings.Contains(text, expected) {
			t.Fatalf("embedding triplets missing %s:\n%s", expected, text)
		}
	}
}

func assertGroup1SplitCarriesInstanceIdentity(t *testing.T, path string) {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read split jsonl %s: %v", path, err)
	}
	lines := strings.Split(strings.TrimSpace(string(content)), "\n")
	if len(lines) == 0 || strings.TrimSpace(lines[0]) == "" {
		t.Fatalf("expected split file %s to contain at least one row", path)
	}
	row := map[string]any{}
	if err := json.Unmarshal([]byte(lines[0]), &row); err != nil {
		t.Fatalf("parse split row: %v", err)
	}
	if _, exists := row["query_items"]; !exists {
		t.Fatalf("expected split row to use query_items, got %v", row)
	}
	items, ok := row["query_items"].([]any)
	if !ok || len(items) == 0 {
		t.Fatalf("expected split row query_items to be a non-empty array, got %T", row["query_items"])
	}
	first, ok := items[0].(map[string]any)
	if !ok {
		t.Fatalf("expected first query item to be an object, got %T", items[0])
	}
	for _, field := range []string{"asset_id", "template_id", "variant_id"} {
		if _, exists := first[field]; !exists {
			t.Fatalf("expected query item to contain %s, got %v", field, first)
		}
	}
}

func assertGroup1RawBatchCarriesInstanceIdentity(t *testing.T, path string) {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read raw labels %s: %v", path, err)
	}
	text := string(content)
	for _, expected := range []string{`"query_items"`, `"asset_id"`, `"template_id"`, `"variant_id"`} {
		if !strings.Contains(text, expected) {
			t.Fatalf("raw labels missing %s:\n%s", expected, text)
		}
	}
}

func assertDatasetJSONReferencesPairedSplits(t *testing.T, path string) {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read dataset json %s: %v", path, err)
	}
	text := string(content)
	for _, expected := range []string{
		"\"format\": \"sinan.group2.paired.v1\"",
		"\"train\": \"splits/train.jsonl\"",
		"\"val\": \"splits/val.jsonl\"",
		"\"test\": \"splits/test.jsonl\"",
	} {
		if !strings.Contains(text, expected) {
			t.Fatalf("dataset json missing %s:\n%s", expected, text)
		}
	}
}

func readBatchRecords(t *testing.T, path string) []export.SampleRecord {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read labels %s: %v", path, err)
	}
	lines := strings.Split(strings.TrimSpace(string(content)), "\n")
	records := make([]export.SampleRecord, 0, len(lines))
	for _, line := range lines {
		if strings.TrimSpace(line) == "" {
			continue
		}
		var record export.SampleRecord
		if err := json.Unmarshal([]byte(line), &record); err != nil {
			t.Fatalf("parse labels row: %v", err)
		}
		records = append(records, record)
	}
	return records
}

func readSourceSignatures(t *testing.T, path string) []string {
	t.Helper()
	records := readBatchRecords(t, path)
	signatures := make([]string, 0, len(records))
	for _, record := range records {
		signatures = append(signatures, record.SourceSignature)
	}
	return signatures
}
