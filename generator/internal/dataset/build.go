package dataset

import (
	"bufio"
	"encoding/json"
	"fmt"
	"image"
	_ "image/jpeg"
	_ "image/png"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"sinan-captcha/generator/internal/export"
)

type BuildRequest struct {
	Task       string
	BatchRoot  string
	DatasetDir string
	Force      bool
}

type BuildResult struct {
	DatasetDir  string         `json:"dataset_dir"`
	DatasetYAML string         `json:"dataset_yaml"`
	RawBatch    string         `json:"raw_batch"`
	SplitCounts map[string]int `json:"split_counts"`
}

func Build(request BuildRequest) (BuildResult, error) {
	result := BuildResult{
		DatasetDir:  request.DatasetDir,
		DatasetYAML: filepath.Join(request.DatasetDir, "dataset.yaml"),
		RawBatch:    request.BatchRoot,
		SplitCounts: map[string]int{},
	}

	if err := prepareDatasetDir(request.DatasetDir, request.Force); err != nil {
		return result, err
	}

	records, err := readRecords(filepath.Join(request.BatchRoot, "labels.jsonl"))
	if err != nil {
		return result, err
	}
	if len(records) == 0 {
		return result, fmt.Errorf("labels.jsonl is empty")
	}

	assignments := splitRecords(records)
	classMap, err := collectClassMap(request.Task, records)
	if err != nil {
		return result, err
	}
	for _, assignment := range assignments {
		if err := writeAssignment(request, assignment); err != nil {
			return result, err
		}
		result.SplitCounts[assignment.Split]++
	}
	if err := writeDatasetYAML(result.DatasetYAML, classMap); err != nil {
		return result, err
	}
	return result, nil
}

type assignment struct {
	Split  string
	Record export.SampleRecord
}

func prepareDatasetDir(datasetDir string, force bool) error {
	managedPaths := []string{
		filepath.Join(datasetDir, "images"),
		filepath.Join(datasetDir, "labels"),
		filepath.Join(datasetDir, "dataset.yaml"),
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
	for _, split := range []string{"train", "val", "test"} {
		if err := os.MkdirAll(filepath.Join(datasetDir, "images", split), 0o755); err != nil {
			return err
		}
		if err := os.MkdirAll(filepath.Join(datasetDir, "labels", split), 0o755); err != nil {
			return err
		}
	}
	return nil
}

func readRecords(path string) ([]export.SampleRecord, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	records := []export.SampleRecord{}
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}
		var record export.SampleRecord
		if err := json.Unmarshal(line, &record); err != nil {
			return nil, err
		}
		records = append(records, record)
	}
	return records, scanner.Err()
}

func splitRecords(records []export.SampleRecord) []assignment {
	ordered := append([]export.SampleRecord(nil), records...)
	sort.Slice(ordered, func(left int, right int) bool {
		return ordered[left].SampleID < ordered[right].SampleID
	})

	total := len(ordered)
	assignments := make([]assignment, 0, total)
	switch total {
	case 1:
		return append(assignments, assignment{Split: "train", Record: ordered[0]})
	case 2:
		return append(assignments,
			assignment{Split: "train", Record: ordered[0]},
			assignment{Split: "val", Record: ordered[1]},
		)
	}

	valCount := maxInt(1, int(float64(total)*0.1+0.5))
	testCount := maxInt(1, int(float64(total)*0.1+0.5))
	trainCount := total - valCount - testCount
	if trainCount < 1 {
		trainCount = 1
		overflow := valCount + testCount - (total - 1)
		if overflow > 0 {
			if testCount >= overflow {
				testCount -= overflow
			} else {
				overflow -= testCount
				testCount = 0
				valCount = maxInt(1, valCount-overflow)
			}
		}
	}

	for index, record := range ordered {
		split := "test"
		if index < trainCount {
			split = "train"
		} else if index < trainCount+valCount {
			split = "val"
		}
		assignments = append(assignments, assignment{Split: split, Record: record})
	}
	return assignments
}

func collectClassMap(task string, records []export.SampleRecord) (map[int]string, error) {
	classMap := map[int]string{}
	switch task {
	case "group1":
		for _, record := range records {
			for _, object := range record.Targets {
				classMap[object.ClassID] = object.Class
			}
			for _, object := range record.Distractors {
				classMap[object.ClassID] = object.Class
			}
		}
	case "group2":
		classMap[0] = "slider_gap"
	default:
		return nil, fmt.Errorf("unsupported task: %s", task)
	}
	return classMap, nil
}

func writeAssignment(request BuildRequest, item assignment) error {
	imageRelative := item.Record.SceneImage
	objects := append([]export.ObjectRecord(nil), item.Record.Targets...)
	if request.Task == "group2" {
		imageRelative = item.Record.MasterImage
		if item.Record.TargetGap == nil {
			return fmt.Errorf("target_gap is required for group2")
		}
		objects = []export.ObjectRecord{*item.Record.TargetGap}
	} else {
		objects = append(objects, item.Record.Distractors...)
	}

	sourceImage := filepath.Join(request.BatchRoot, filepath.FromSlash(imageRelative))
	if _, err := os.Stat(sourceImage); err != nil {
		return err
	}
	destinationImage := filepath.Join(request.DatasetDir, "images", item.Split, filepath.Base(sourceImage))
	if err := copyFile(sourceImage, destinationImage); err != nil {
		return err
	}
	width, height, err := imageSize(sourceImage)
	if err != nil {
		return err
	}

	lines := make([]string, 0, len(objects))
	for _, object := range objects {
		lines = append(lines, toYOLOLine(object, width, height))
	}
	labelPath := filepath.Join(request.DatasetDir, "labels", item.Split, stringsTrimExt(filepath.Base(sourceImage))+".txt")
	return os.WriteFile(labelPath, []byte(joinLines(lines)), 0o644)
}

func toYOLOLine(object export.ObjectRecord, width int, height int) string {
	x1, y1, x2, y2 := object.BBox[0], object.BBox[1], object.BBox[2], object.BBox[3]
	bboxWidth := x2 - x1
	bboxHeight := y2 - y1
	centerX := float64(x1) + float64(bboxWidth)/2
	centerY := float64(y1) + float64(bboxHeight)/2
	return fmt.Sprintf(
		"%d %s %s %s %s",
		object.ClassID,
		formatFloat(centerX/float64(width)),
		formatFloat(centerY/float64(height)),
		formatFloat(float64(bboxWidth)/float64(width)),
		formatFloat(float64(bboxHeight)/float64(height)),
	)
}

func writeDatasetYAML(path string, classMap map[int]string) error {
	classIDs := make([]int, 0, len(classMap))
	for classID := range classMap {
		classIDs = append(classIDs, classID)
	}
	sort.Ints(classIDs)
	lines := []string{
		"path: .",
		"train: images/train",
		"val: images/val",
		"test: images/test",
		"names:",
	}
	for _, classID := range classIDs {
		lines = append(lines, fmt.Sprintf("  %d: %s", classID, classMap[classID]))
	}
	return os.WriteFile(path, []byte(joinLines(lines)), 0o644)
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

func formatFloat(value float64) string {
	text := fmt.Sprintf("%.6f", value)
	text = strings.TrimRight(text, "0")
	text = strings.TrimRight(text, ".")
	if text == "" {
		return "0"
	}
	return text
}

func stringsTrimExt(name string) string {
	return strings.TrimSuffix(name, filepath.Ext(name))
}

func joinLines(lines []string) string {
	if len(lines) == 0 {
		return ""
	}
	return strings.Join(lines, "\n") + "\n"
}

func maxInt(left int, right int) int {
	if left > right {
		return left
	}
	return right
}
