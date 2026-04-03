package workspace

import (
	"os"
	"path/filepath"
	"testing"
)

func TestEnsureCreatesWorkspaceLayoutAndMetadata(t *testing.T) {
	root := filepath.Join(t.TempDir(), "workspace")

	state, err := Ensure(root)
	if err != nil {
		t.Fatalf("ensure workspace: %v", err)
	}

	expectedDirs := []string{
		state.Layout.Root,
		state.Layout.PresetsDir,
		state.Layout.OfficialMaterialsDir,
		state.Layout.LocalMaterialsDir,
		state.Layout.ManifestsDir,
		state.Layout.QuarantineDir,
		state.Layout.CacheDownloadsDir,
		state.Layout.JobsDir,
		state.Layout.LogsDir,
	}
	for _, dir := range expectedDirs {
		info, err := os.Stat(dir)
		if err != nil {
			t.Fatalf("expected %s to exist: %v", dir, err)
		}
		if !info.IsDir() {
			t.Fatalf("expected %s to be a directory", dir)
		}
	}

	if state.Metadata.SchemaVersion != CurrentSchemaVersion {
		t.Fatalf("unexpected schema version: got %d want %d", state.Metadata.SchemaVersion, CurrentSchemaVersion)
	}
	if state.Metadata.WorkspaceRoot != root {
		t.Fatalf("unexpected workspace root: got %s want %s", state.Metadata.WorkspaceRoot, root)
	}
	if state.Metadata.CreatedAt == "" {
		t.Fatalf("expected created_at to be populated")
	}

	expectedPresets := []string{
		filepath.Join(state.Layout.PresetsDir, "smoke.yaml"),
		filepath.Join(state.Layout.PresetsDir, "group1.firstpass.yaml"),
		filepath.Join(state.Layout.PresetsDir, "group2.firstpass.yaml"),
	}
	for _, path := range expectedPresets {
		if _, err := os.Stat(path); err != nil {
			t.Fatalf("expected preset %s to exist: %v", path, err)
		}
	}
}

func TestEnsurePreservesExistingMetadata(t *testing.T) {
	root := filepath.Join(t.TempDir(), "workspace")

	first, err := Ensure(root)
	if err != nil {
		t.Fatalf("first ensure: %v", err)
	}
	first.Metadata.DefaultMaterialSource = "https://example.com/materials.zip"
	if err := SaveMetadata(first.Layout.Root, first.Metadata); err != nil {
		t.Fatalf("save metadata: %v", err)
	}

	second, err := Ensure(root)
	if err != nil {
		t.Fatalf("second ensure: %v", err)
	}
	if second.Metadata.DefaultMaterialSource != "https://example.com/materials.zip" {
		t.Fatalf("expected metadata to persist, got %q", second.Metadata.DefaultMaterialSource)
	}
}
