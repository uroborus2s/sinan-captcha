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
	DatasetDir    string         `json:"dataset_dir"`
	DatasetConfig string         `json:"dataset_config"`
	RawBatch      string         `json:"raw_batch"`
	SplitCounts   map[string]int `json:"split_counts"`
}

func Build(request BuildRequest) (BuildResult, error) {
	result := BuildResult{
		DatasetDir:  request.DatasetDir,
		RawBatch:    request.BatchRoot,
		SplitCounts: map[string]int{},
	}
	switch request.Task {
	case "group1":
		result.DatasetConfig = filepath.Join(request.DatasetDir, "dataset.json")
	case "group2":
		result.DatasetConfig = filepath.Join(request.DatasetDir, "dataset.json")
	default:
		return result, fmt.Errorf("unsupported task: %s", request.Task)
	}

	if err := prepareDatasetDir(request.Task, request.DatasetDir, request.Force); err != nil {
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
	switch request.Task {
	case "group1":
		classMap, err := collectClassMap(request.Task, records)
		if err != nil {
			return result, err
		}
		splitRows := map[string][]export.SampleRecord{
			"train": {},
			"val":   {},
			"test":  {},
		}
		for _, assignment := range assignments {
			row, err := writeGroup1Assignment(request, assignment)
			if err != nil {
				return result, err
			}
			splitRows[assignment.Split] = append(splitRows[assignment.Split], row)
			result.SplitCounts[assignment.Split]++
		}
		if err := writeDatasetYAML(filepath.Join(request.DatasetDir, "scene-yolo", "dataset.yaml"), classMap); err != nil {
			return result, err
		}
		if err := writeDatasetYAML(filepath.Join(request.DatasetDir, "query-yolo", "dataset.yaml"), classMap); err != nil {
			return result, err
		}
		if err := writeGroup1DatasetConfig(result.DatasetConfig, classMap); err != nil {
			return result, err
		}
		if err := writeGroup1SplitJSONL(request.DatasetDir, splitRows); err != nil {
			return result, err
		}
	case "group2":
		splitRows := map[string][]export.SampleRecord{
			"train": {},
			"val":   {},
			"test":  {},
		}
		for _, assignment := range assignments {
			row, err := writeGroup2Assignment(request, assignment)
			if err != nil {
				return result, err
			}
			splitRows[assignment.Split] = append(splitRows[assignment.Split], row)
			result.SplitCounts[assignment.Split]++
		}
		if err := writeGroup2DatasetConfig(result.DatasetConfig); err != nil {
			return result, err
		}
		if err := writeGroup2SplitJSONL(request.DatasetDir, splitRows); err != nil {
			return result, err
		}
	}
	return result, nil
}

type assignment struct {
	Split  string
	Record export.SampleRecord
}

func prepareDatasetDir(task string, datasetDir string, force bool) error {
	var managedPaths []string
	switch task {
	case "group1":
		managedPaths = []string{
			filepath.Join(datasetDir, "scene-yolo"),
			filepath.Join(datasetDir, "query-yolo"),
			filepath.Join(datasetDir, "splits"),
			filepath.Join(datasetDir, "dataset.json"),
		}
	case "group2":
		managedPaths = []string{
			filepath.Join(datasetDir, "master"),
			filepath.Join(datasetDir, "tile"),
			filepath.Join(datasetDir, "splits"),
			filepath.Join(datasetDir, "dataset.json"),
		}
	default:
		return fmt.Errorf("unsupported task: %s", task)
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
	switch task {
	case "group1":
		for _, split := range []string{"train", "val", "test"} {
			if err := os.MkdirAll(filepath.Join(datasetDir, "scene-yolo", "images", split), 0o755); err != nil {
				return err
			}
			if err := os.MkdirAll(filepath.Join(datasetDir, "scene-yolo", "labels", split), 0o755); err != nil {
				return err
			}
			if err := os.MkdirAll(filepath.Join(datasetDir, "query-yolo", "images", split), 0o755); err != nil {
				return err
			}
			if err := os.MkdirAll(filepath.Join(datasetDir, "query-yolo", "labels", split), 0o755); err != nil {
				return err
			}
		}
		if err := os.MkdirAll(filepath.Join(datasetDir, "splits"), 0o755); err != nil {
			return err
		}
	case "group2":
		if err := os.MkdirAll(filepath.Join(datasetDir, "splits"), 0o755); err != nil {
			return err
		}
		for _, split := range []string{"train", "val", "test"} {
			if err := os.MkdirAll(filepath.Join(datasetDir, "master", split), 0o755); err != nil {
				return err
			}
			if err := os.MkdirAll(filepath.Join(datasetDir, "tile", split), 0o755); err != nil {
				return err
			}
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
			for _, object := range record.SceneTargets {
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

func writeGroup1Assignment(request BuildRequest, item assignment) (export.SampleRecord, error) {
	record := item.Record
	sceneSource := filepath.Join(request.BatchRoot, filepath.FromSlash(record.SceneImage))
	querySource := filepath.Join(request.BatchRoot, filepath.FromSlash(record.QueryImage))
	if _, err := os.Stat(sceneSource); err != nil {
		return export.SampleRecord{}, err
	}
	if _, err := os.Stat(querySource); err != nil {
		return export.SampleRecord{}, err
	}

	sceneRelative := filepath.ToSlash(filepath.Join("scene-yolo", "images", item.Split, filepath.Base(sceneSource)))
	queryRelative := filepath.ToSlash(filepath.Join("query-yolo", "images", item.Split, filepath.Base(querySource)))
	if err := copyFile(sceneSource, filepath.Join(request.DatasetDir, filepath.FromSlash(sceneRelative))); err != nil {
		return export.SampleRecord{}, err
	}
	if err := copyFile(querySource, filepath.Join(request.DatasetDir, filepath.FromSlash(queryRelative))); err != nil {
		return export.SampleRecord{}, err
	}

	sceneWidth, sceneHeight, err := imageSize(sceneSource)
	if err != nil {
		return export.SampleRecord{}, err
	}
	queryWidth, queryHeight, err := imageSize(querySource)
	if err != nil {
		return export.SampleRecord{}, err
	}

	sceneObjects := append([]export.ObjectRecord(nil), record.SceneTargets...)
	sceneObjects = append(sceneObjects, record.Distractors...)
	sceneLines := make([]string, 0, len(sceneObjects))
	for _, object := range sceneObjects {
		sceneLines = append(sceneLines, toYOLOLine(object, sceneWidth, sceneHeight))
	}
	sceneLabelPath := filepath.Join(request.DatasetDir, "scene-yolo", "labels", item.Split, stringsTrimExt(filepath.Base(sceneSource))+".txt")
	if err := os.WriteFile(sceneLabelPath, []byte(joinLines(sceneLines)), 0o644); err != nil {
		return export.SampleRecord{}, err
	}

	queryLines := make([]string, 0, len(record.QueryTargets))
	for _, object := range record.QueryTargets {
		queryLines = append(queryLines, toYOLOLine(object, queryWidth, queryHeight))
	}
	queryLabelPath := filepath.Join(request.DatasetDir, "query-yolo", "labels", item.Split, stringsTrimExt(filepath.Base(querySource))+".txt")
	if err := os.WriteFile(queryLabelPath, []byte(joinLines(queryLines)), 0o644); err != nil {
		return export.SampleRecord{}, err
	}

	record.SceneImage = sceneRelative
	record.QueryImage = queryRelative
	return record, nil
}

func writeGroup2Assignment(request BuildRequest, item assignment) (export.SampleRecord, error) {
	record := item.Record
	if record.TargetGap == nil {
		return export.SampleRecord{}, fmt.Errorf("target_gap is required for group2")
	}
	if record.TileBBox == nil {
		return export.SampleRecord{}, fmt.Errorf("tile_bbox is required for group2")
	}

	masterSource := filepath.Join(request.BatchRoot, filepath.FromSlash(record.MasterImage))
	tileSource := filepath.Join(request.BatchRoot, filepath.FromSlash(record.TileImage))
	if _, err := os.Stat(masterSource); err != nil {
		return export.SampleRecord{}, err
	}
	if _, err := os.Stat(tileSource); err != nil {
		return export.SampleRecord{}, err
	}

	masterRelative := filepath.ToSlash(filepath.Join("master", item.Split, filepath.Base(masterSource)))
	tileRelative := filepath.ToSlash(filepath.Join("tile", item.Split, filepath.Base(tileSource)))
	if err := copyFile(masterSource, filepath.Join(request.DatasetDir, filepath.FromSlash(masterRelative))); err != nil {
		return export.SampleRecord{}, err
	}
	if err := copyFile(tileSource, filepath.Join(request.DatasetDir, filepath.FromSlash(tileRelative))); err != nil {
		return export.SampleRecord{}, err
	}

	record.MasterImage = masterRelative
	record.TileImage = tileRelative
	return record, nil
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

type pairedDatasetConfig struct {
	Task    string            `json:"task"`
	Format  string            `json:"format"`
	Splits  map[string]string `json:"splits"`
	ClassID int               `json:"class_id"`
	Class   string            `json:"class"`
}

type yoloComponentConfig struct {
	Format      string `json:"format"`
	DatasetYAML string `json:"dataset_yaml"`
}

type group1MatcherConfig struct {
	Strategy string `json:"strategy"`
}

type group1DatasetConfig struct {
	Task       string                         `json:"task"`
	Format     string                         `json:"format"`
	Splits     map[string]string              `json:"splits"`
	Components map[string]yoloComponentConfig `json:"components"`
	Matcher    group1MatcherConfig            `json:"matcher"`
	Classes    map[string]string              `json:"classes"`
}

func writeGroup1DatasetConfig(path string, classMap map[int]string) error {
	classes := map[string]string{}
	for classID, className := range classMap {
		classes[fmt.Sprintf("%d", classID)] = className
	}
	content, err := json.MarshalIndent(
		group1DatasetConfig{
			Task:   "group1",
			Format: "sinan.group1.pipeline.v1",
			Splits: map[string]string{
				"train": "splits/train.jsonl",
				"val":   "splits/val.jsonl",
				"test":  "splits/test.jsonl",
			},
			Components: map[string]yoloComponentConfig{
				"scene_detector": {
					Format:      "yolo.detect.v1",
					DatasetYAML: "scene-yolo/dataset.yaml",
				},
				"query_parser": {
					Format:      "yolo.detect.v1",
					DatasetYAML: "query-yolo/dataset.yaml",
				},
			},
			Matcher: group1MatcherConfig{
				Strategy: "ordered_class_match_v1",
			},
			Classes: classes,
		},
		"",
		"  ",
	)
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(content, '\n'), 0o644)
}

func writeGroup2DatasetConfig(path string) error {
	content, err := json.MarshalIndent(
		pairedDatasetConfig{
			Task:   "group2",
			Format: "sinan.group2.paired.v1",
			Splits: map[string]string{
				"train": "splits/train.jsonl",
				"val":   "splits/val.jsonl",
				"test":  "splits/test.jsonl",
			},
			ClassID: 0,
			Class:   "slider_gap",
		},
		"",
		"  ",
	)
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(content, '\n'), 0o644)
}

func writeGroup1SplitJSONL(datasetDir string, splitRows map[string][]export.SampleRecord) error {
	for _, split := range []string{"train", "val", "test"} {
		rows := splitRows[split]
		content := make([]string, 0, len(rows))
		for _, row := range rows {
			line, err := json.Marshal(row)
			if err != nil {
				return err
			}
			content = append(content, string(line))
		}
		if err := os.WriteFile(filepath.Join(datasetDir, "splits", split+".jsonl"), []byte(joinLines(content)), 0o644); err != nil {
			return err
		}
	}
	return nil
}

func writeGroup2SplitJSONL(datasetDir string, splitRows map[string][]export.SampleRecord) error {
	for _, split := range []string{"train", "val", "test"} {
		rows := splitRows[split]
		content := make([]byte, 0, len(rows)*256)
		for _, row := range rows {
			line, err := json.Marshal(row)
			if err != nil {
				return err
			}
			content = append(content, line...)
			content = append(content, '\n')
		}
		if err := os.WriteFile(filepath.Join(datasetDir, "splits", split+".jsonl"), content, 0o644); err != nil {
			return err
		}
	}
	return nil
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
