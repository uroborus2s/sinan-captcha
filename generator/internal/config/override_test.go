package config

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestLoadOverrideRejectsYAMLStyleContentWithClearMessage(t *testing.T) {
	root := t.TempDir()
	path := filepath.Join(root, "override.json")
	content := "" +
		"sampling:\n" +
		"  target_count_min: 2\n"
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write override: %v", err)
	}

	_, err := LoadOverride(path)
	if err == nil {
		t.Fatalf("expected override load to fail")
	}
	if !strings.Contains(err.Error(), "must be a JSON object starting with '{'") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestLoadOverrideParsesJSONObject(t *testing.T) {
	root := t.TempDir()
	path := filepath.Join(root, "override.json")
	content := `{
  "project": {
    "sample_count": 64
  },
  "sampling": {
    "target_count_min": 2,
    "target_count_max": 4
  }
}`
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write override: %v", err)
	}

	override, err := LoadOverride(path)
	if err != nil {
		t.Fatalf("load override: %v", err)
	}
	if override.Project == nil || override.Project.SampleCount == nil || *override.Project.SampleCount != 64 {
		t.Fatalf("unexpected project override: %+v", override.Project)
	}
	if override.Sampling == nil || override.Sampling.TargetCountMax == nil || *override.Sampling.TargetCountMax != 4 {
		t.Fatalf("unexpected sampling override: %+v", override.Sampling)
	}
}
