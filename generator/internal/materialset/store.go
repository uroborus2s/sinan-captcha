package materialset

import (
	"archive/zip"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"

	"sinan-captcha/generator/internal/material"
	"sinan-captcha/generator/internal/workspace"
)

type SyncResult struct {
	Ref        workspace.MaterialSetRef   `json:"ref"`
	Root       string                     `json:"root"`
	Validation material.ValidationSummary `json:"validation"`
}

func ResolveOrAcquire(state workspace.State, selector string, source string) (SyncResult, error) {
	if selector != "" {
		return Resolve(state, selector)
	}
	if state.Metadata.ActiveMaterialSet != nil {
		path, err := workspace.MaterialSetPath(state.Layout, *state.Metadata.ActiveMaterialSet)
		if err == nil {
			summary, validateErr := material.Validate(path)
			if validateErr == nil {
				return SyncResult{Ref: *state.Metadata.ActiveMaterialSet, Root: path, Validation: summary}, nil
			}
		}
	}
	if source == "" {
		source = state.Metadata.DefaultMaterialSource
	}
	if source == "" {
		return SyncResult{}, fmt.Errorf("no materials available in workspace %s; import local materials or provide --materials-source", state.Layout.Root)
	}
	return Sync(state, source, "")
}

func Resolve(state workspace.State, selector string) (SyncResult, error) {
	ref, err := parseSelector(selector)
	if err != nil {
		return SyncResult{}, err
	}
	root, err := workspace.MaterialSetPath(state.Layout, ref)
	if err != nil {
		return SyncResult{}, err
	}
	summary, err := material.Validate(root)
	if err != nil {
		return SyncResult{}, err
	}
	return SyncResult{Ref: ref, Root: root, Validation: summary}, nil
}

func Sync(state workspace.State, source string, name string) (SyncResult, error) {
	info, err := os.Stat(source)
	if err == nil && info.IsDir() {
		return ImportLocal(state, source, name)
	}
	return FetchArchive(state, source, name)
}

func ImportLocal(state workspace.State, source string, name string) (SyncResult, error) {
	source = filepath.Clean(source)
	if name == "" {
		name = filepath.Base(source)
	}
	ref := workspace.MaterialSetRef{
		Scope:        "local",
		Name:         sanitizeName(name),
		RelativePath: filepath.ToSlash(filepath.Join("materials", "local", sanitizeName(name))),
	}
	destination, err := workspace.MaterialSetPath(state.Layout, ref)
	if err != nil {
		return SyncResult{}, err
	}
	if err := os.RemoveAll(destination); err != nil {
		return SyncResult{}, err
	}
	if err := copyDir(source, destination); err != nil {
		return SyncResult{}, err
	}
	summary, err := material.Validate(destination)
	if err != nil {
		return SyncResult{}, err
	}
	updated, err := workspace.SetActiveMaterialSet(state.Layout.Root, ref)
	if err != nil {
		return SyncResult{}, err
	}
	return SyncResult{Ref: *updated.Metadata.ActiveMaterialSet, Root: destination, Validation: summary}, nil
}

func FetchArchive(state workspace.State, source string, name string) (SyncResult, error) {
	archivePath, resolvedName, err := acquireArchive(state, source, name)
	if err != nil {
		return SyncResult{}, err
	}
	if resolvedName == "" {
		resolvedName = "official-pack"
	}
	ref := workspace.MaterialSetRef{
		Scope:        "official",
		Name:         sanitizeName(resolvedName),
		RelativePath: filepath.ToSlash(filepath.Join("materials", "official", sanitizeName(resolvedName))),
	}
	destination, err := workspace.MaterialSetPath(state.Layout, ref)
	if err != nil {
		return SyncResult{}, err
	}
	if err := os.RemoveAll(destination); err != nil {
		return SyncResult{}, err
	}
	tempDir, err := os.MkdirTemp(state.Layout.CacheDownloadsDir, "materials-unpack-*")
	if err != nil {
		return SyncResult{}, err
	}
	defer os.RemoveAll(tempDir)
	if err := unzipArchive(archivePath, tempDir); err != nil {
		return SyncResult{}, err
	}
	packRoot, err := detectMaterialRoot(tempDir)
	if err != nil {
		return SyncResult{}, err
	}
	if err := copyDir(packRoot, destination); err != nil {
		return SyncResult{}, err
	}
	summary, err := material.Validate(destination)
	if err != nil {
		return SyncResult{}, err
	}
	updated, err := workspace.SetActiveMaterialSet(state.Layout.Root, ref)
	if err != nil {
		return SyncResult{}, err
	}
	return SyncResult{Ref: *updated.Metadata.ActiveMaterialSet, Root: destination, Validation: summary}, nil
}

func parseSelector(selector string) (workspace.MaterialSetRef, error) {
	parts := strings.Split(strings.TrimSpace(selector), "/")
	if len(parts) != 2 {
		return workspace.MaterialSetRef{}, fmt.Errorf("materials selector must be <official|local>/<name>")
	}
	ref := workspace.MaterialSetRef{
		Scope:        parts[0],
		Name:         parts[1],
		RelativePath: filepath.ToSlash(filepath.Join("materials", parts[0], parts[1])),
	}
	if ref.Scope != "official" && ref.Scope != "local" {
		return workspace.MaterialSetRef{}, fmt.Errorf("unsupported materials scope: %s", ref.Scope)
	}
	return ref, nil
}

func acquireArchive(state workspace.State, source string, name string) (string, string, error) {
	if fileInfo, err := os.Stat(source); err == nil && !fileInfo.IsDir() {
		resolvedName := name
		if resolvedName == "" {
			resolvedName = strings.TrimSuffix(filepath.Base(source), filepath.Ext(source))
		}
		return source, resolvedName, nil
	}

	parsed, err := url.Parse(source)
	if err != nil {
		return "", "", err
	}
	if parsed.Scheme == "" || parsed.Scheme == "file" {
		path := strings.TrimPrefix(source, "file://")
		resolvedName := name
		if resolvedName == "" {
			resolvedName = strings.TrimSuffix(filepath.Base(path), filepath.Ext(path))
		}
		return path, resolvedName, nil
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return "", "", fmt.Errorf("unsupported materials source: %s", source)
	}

	resolvedName := name
	if resolvedName == "" {
		resolvedName = strings.TrimSuffix(filepath.Base(parsed.Path), filepath.Ext(parsed.Path))
	}
	if resolvedName == "" {
		resolvedName = fmt.Sprintf("official-%d", time.Now().Unix())
	}
	archivePath := filepath.Join(state.Layout.CacheDownloadsDir, sanitizeName(resolvedName)+".zip")
	if err := downloadToFile(source, archivePath); err != nil {
		return "", "", err
	}
	return archivePath, resolvedName, nil
}

func downloadToFile(source string, destination string) error {
	request, err := http.NewRequest(http.MethodGet, source, nil)
	if err != nil {
		return err
	}
	client := &http.Client{Timeout: 60 * time.Second}
	response, err := client.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return fmt.Errorf("download materials archive: unexpected status %s", response.Status)
	}
	file, err := os.Create(destination)
	if err != nil {
		return err
	}
	defer file.Close()
	_, err = io.Copy(file, response.Body)
	return err
}

func unzipArchive(path string, destination string) error {
	reader, err := zip.OpenReader(path)
	if err != nil {
		return err
	}
	defer reader.Close()
	for _, file := range reader.File {
		targetPath := filepath.Join(destination, file.Name)
		cleanTarget := filepath.Clean(targetPath)
		if !strings.HasPrefix(cleanTarget, filepath.Clean(destination)+string(os.PathSeparator)) && cleanTarget != filepath.Clean(destination) {
			return fmt.Errorf("archive entry escapes destination: %s", file.Name)
		}
		if file.FileInfo().IsDir() {
			if err := os.MkdirAll(cleanTarget, 0o755); err != nil {
				return err
			}
			continue
		}
		if err := os.MkdirAll(filepath.Dir(cleanTarget), 0o755); err != nil {
			return err
		}
		in, err := file.Open()
		if err != nil {
			return err
		}
		out, err := os.Create(cleanTarget)
		if err != nil {
			in.Close()
			return err
		}
		if _, err := io.Copy(out, in); err != nil {
			in.Close()
			out.Close()
			return err
		}
		in.Close()
		out.Close()
	}
	return nil
}

func detectMaterialRoot(root string) (string, error) {
	if isMaterialRoot(root) {
		return root, nil
	}
	entries, err := os.ReadDir(root)
	if err != nil {
		return "", err
	}
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		candidate := filepath.Join(root, entry.Name())
		if isMaterialRoot(candidate) {
			return candidate, nil
		}
	}
	return "", fmt.Errorf("could not detect materials root in %s", root)
}

func isMaterialRoot(root string) bool {
	required := []string{
		filepath.Join(root, "backgrounds"),
		filepath.Join(root, "icons"),
		filepath.Join(root, "manifests", "classes.yaml"),
	}
	for _, path := range required {
		if _, err := os.Stat(path); err != nil {
			return false
		}
	}
	return true
}

func copyDir(source string, destination string) error {
	return filepath.WalkDir(source, func(path string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		relative, err := filepath.Rel(source, path)
		if err != nil {
			return err
		}
		target := filepath.Join(destination, relative)
		if entry.IsDir() {
			return os.MkdirAll(target, 0o755)
		}
		if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
			return err
		}
		in, err := os.Open(path)
		if err != nil {
			return err
		}
		out, err := os.Create(target)
		if err != nil {
			in.Close()
			return err
		}
		if _, err := io.Copy(out, in); err != nil {
			in.Close()
			out.Close()
			return err
		}
		if err := in.Close(); err != nil {
			out.Close()
			return err
		}
		return out.Close()
	})
}

func sanitizeName(name string) string {
	name = strings.TrimSpace(name)
	name = strings.ReplaceAll(name, " ", "-")
	name = strings.ReplaceAll(name, "/", "-")
	name = strings.ReplaceAll(name, "\\", "-")
	if name == "" {
		return "materials"
	}
	return name
}
