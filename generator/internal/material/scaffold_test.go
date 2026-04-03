package material

import (
	"os"
	"path/filepath"
	"testing"
)

func TestInitializeCreatesSkeletonWhenManifestMissing(t *testing.T) {
	root := t.TempDir()

	summary, err := Initialize(root)
	if err != nil {
		t.Fatalf("expected init to succeed: %v", err)
	}
	if !summary.ManifestCreated {
		t.Fatal("expected manifest to be created")
	}

	for _, path := range []string{
		filepath.Join(root, "backgrounds"),
		filepath.Join(root, "icons"),
		filepath.Join(root, "manifests"),
		summary.ManifestPath,
	} {
		if _, err := os.Stat(path); err != nil {
			t.Fatalf("expected %s to exist: %v", path, err)
		}
	}
}

func TestInitializeCreatesIconDirsFromExistingManifest(t *testing.T) {
	root := t.TempDir()
	manifestPath := filepath.Join(root, "manifests", "classes.yaml")
	if err := os.MkdirAll(filepath.Dir(manifestPath), 0o755); err != nil {
		t.Fatalf("mkdir manifests: %v", err)
	}
	content := "classes:\n  - id: 0\n    name: icon_house\n    zh_name: 房子\n  - id: 1\n    name: icon_leaf\n    zh_name: 叶子\n"
	if err := os.WriteFile(manifestPath, []byte(content), 0o644); err != nil {
		t.Fatalf("write manifest: %v", err)
	}

	summary, err := Initialize(root)
	if err != nil {
		t.Fatalf("expected init to succeed: %v", err)
	}
	if summary.IconDirCount != 2 {
		t.Fatalf("expected 2 icon dirs, got %d", summary.IconDirCount)
	}
	for _, dir := range []string{
		filepath.Join(root, "icons", "icon_house"),
		filepath.Join(root, "icons", "icon_leaf"),
	} {
		if info, err := os.Stat(dir); err != nil || !info.IsDir() {
			t.Fatalf("expected icon dir %s to exist: %v", dir, err)
		}
	}
}
