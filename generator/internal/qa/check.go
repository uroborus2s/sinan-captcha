package qa

import (
	"bufio"
	"errors"
	"os"
	"path/filepath"
	"strings"
)

type Summary struct {
	BatchRoot      string `json:"batch_root"`
	QueryCount     int    `json:"query_count"`
	SceneCount     int    `json:"scene_count"`
	LabelLineCount int    `json:"label_line_count"`
	LabelsExists   bool   `json:"labels_exists"`
}

func InspectBatch(batchRoot string) (Summary, error) {
	summary := Summary{
		BatchRoot: batchRoot,
	}

	queryDir := filepath.Join(batchRoot, "query")
	sceneDir := filepath.Join(batchRoot, "scene")
	labelsPath := filepath.Join(batchRoot, "labels.jsonl")

	queryCount, err := countFiles(queryDir)
	if err != nil {
		return summary, err
	}
	sceneCount, err := countFiles(sceneDir)
	if err != nil {
		return summary, err
	}
	if _, err := os.Stat(labelsPath); err != nil {
		return summary, err
	}

	summary.QueryCount = queryCount
	summary.SceneCount = sceneCount
	summary.LabelLineCount, err = countLines(labelsPath)
	if err != nil {
		return summary, err
	}
	summary.LabelsExists = true

	if summary.QueryCount != summary.SceneCount {
		return summary, errors.New("query and scene image counts do not match")
	}
	if summary.QueryCount != summary.LabelLineCount {
		return summary, errors.New("image counts and labels.jsonl line count do not match")
	}

	return summary, nil
}

func countFiles(dir string) (int, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return 0, err
	}

	count := 0
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		ext := strings.ToLower(filepath.Ext(entry.Name()))
		if ext == ".png" || ext == ".jpg" || ext == ".jpeg" || ext == ".jsonl" {
			count++
		}
	}
	return count, nil
}

func countLines(path string) (int, error) {
	file, err := os.Open(path)
	if err != nil {
		return 0, err
	}
	defer file.Close()

	count := 0
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		count++
	}
	if err := scanner.Err(); err != nil {
		return 0, err
	}
	return count, nil
}
