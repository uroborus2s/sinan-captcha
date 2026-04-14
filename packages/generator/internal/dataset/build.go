package dataset

import (
	"bufio"
	"encoding/json"
	"fmt"
	"image"
	"image/draw"
	_ "image/jpeg"
	"image/png"
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
		splitRows := map[string][]export.SampleRecord{
			"train": {},
			"val":   {},
			"test":  {},
		}
		evalRows := make([]export.SampleRecord, 0, len(assignments))
		embeddingPairs := []group1EmbeddingPairRecord{}
		embeddingTriplets := []group1EmbeddingTripletRecord{}
		for _, assignment := range assignments {
			artifacts, err := writeGroup1Assignment(request, assignment)
			if err != nil {
				return result, err
			}
			splitRows[assignment.Split] = append(splitRows[assignment.Split], artifacts.SplitRow)
			evalRows = append(evalRows, artifacts.EvalRow)
			embeddingPairs = append(embeddingPairs, artifacts.EmbeddingPairs...)
			embeddingTriplets = append(embeddingTriplets, artifacts.EmbeddingTriplets...)
			result.SplitCounts[assignment.Split]++
		}
		if err := writeDatasetYAML(filepath.Join(request.DatasetDir, "query-yolo", "dataset.yaml"), map[int]string{0: "query_item"}); err != nil {
			return result, err
		}
		if err := writeDatasetYAML(filepath.Join(request.DatasetDir, "proposal-yolo", "dataset.yaml"), map[int]string{0: "icon_object"}); err != nil {
			return result, err
		}
		if err := writeGroup1DatasetConfig(result.DatasetConfig); err != nil {
			return result, err
		}
		if err := writeGroup1EvalJSONL(request.DatasetDir, evalRows); err != nil {
			return result, err
		}
		if err := writeGroup1EmbeddingJSONL(request.DatasetDir, embeddingPairs, embeddingTriplets); err != nil {
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

type group1AssignmentArtifacts struct {
	SplitRow          export.SampleRecord
	EvalRow           export.SampleRecord
	EmbeddingPairs    []group1EmbeddingPairRecord
	EmbeddingTriplets []group1EmbeddingTripletRecord
}

type group1EmbeddingPairRecord struct {
	Split          string              `json:"split"`
	SampleID       string              `json:"sample_id"`
	Label          int                 `json:"label"`
	QueryImage     string              `json:"query_image"`
	CandidateImage string              `json:"candidate_image"`
	QueryItem      export.ObjectRecord `json:"query_item"`
	Candidate      export.ObjectRecord `json:"candidate"`
	CandidateRole  string              `json:"candidate_role"`
}

type group1EmbeddingTripletRecord struct {
	Split         string              `json:"split"`
	SampleID      string              `json:"sample_id"`
	AnchorImage   string              `json:"anchor_image"`
	PositiveImage string              `json:"positive_image"`
	NegativeImage string              `json:"negative_image"`
	Anchor        export.ObjectRecord `json:"anchor"`
	Positive      export.ObjectRecord `json:"positive"`
	Negative      export.ObjectRecord `json:"negative"`
	NegativeRole  string              `json:"negative_role"`
}

type group1EmbeddingCrop struct {
	RelativePath string
	Object       export.ObjectRecord
	Role         string
}

func prepareDatasetDir(task string, datasetDir string, force bool) error {
	var managedPaths []string
	switch task {
	case "group1":
		managedPaths = []string{
			filepath.Join(datasetDir, "query-yolo"),
			filepath.Join(datasetDir, "proposal-yolo"),
			filepath.Join(datasetDir, "embedding"),
			filepath.Join(datasetDir, "eval"),
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
			if err := os.MkdirAll(filepath.Join(datasetDir, "query-yolo", "images", split), 0o755); err != nil {
				return err
			}
			if err := os.MkdirAll(filepath.Join(datasetDir, "query-yolo", "labels", split), 0o755); err != nil {
				return err
			}
			if err := os.MkdirAll(filepath.Join(datasetDir, "proposal-yolo", "images", split), 0o755); err != nil {
				return err
			}
			if err := os.MkdirAll(filepath.Join(datasetDir, "proposal-yolo", "labels", split), 0o755); err != nil {
				return err
			}
			if err := os.MkdirAll(filepath.Join(datasetDir, "embedding", "queries", split), 0o755); err != nil {
				return err
			}
			if err := os.MkdirAll(filepath.Join(datasetDir, "embedding", "candidates", split), 0o755); err != nil {
				return err
			}
			if err := os.MkdirAll(filepath.Join(datasetDir, "eval", "query", split), 0o755); err != nil {
				return err
			}
			if err := os.MkdirAll(filepath.Join(datasetDir, "eval", "scene", split), 0o755); err != nil {
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

func writeGroup1Assignment(request BuildRequest, item assignment) (group1AssignmentArtifacts, error) {
	record := item.Record
	sceneSource := filepath.Join(request.BatchRoot, filepath.FromSlash(record.SceneImage))
	querySource := filepath.Join(request.BatchRoot, filepath.FromSlash(record.QueryImage))
	if _, err := os.Stat(sceneSource); err != nil {
		return group1AssignmentArtifacts{}, err
	}
	if _, err := os.Stat(querySource); err != nil {
		return group1AssignmentArtifacts{}, err
	}

	queryYOLOImageRelative := filepath.ToSlash(filepath.Join("query-yolo", "images", item.Split, filepath.Base(querySource)))
	proposalRelative := filepath.ToSlash(filepath.Join("proposal-yolo", "images", item.Split, filepath.Base(sceneSource)))
	evalSceneRelative := filepath.ToSlash(filepath.Join("eval", "scene", item.Split, filepath.Base(sceneSource)))
	evalQueryRelative := filepath.ToSlash(filepath.Join("eval", "query", item.Split, filepath.Base(querySource)))
	if err := copyFile(querySource, filepath.Join(request.DatasetDir, filepath.FromSlash(queryYOLOImageRelative))); err != nil {
		return group1AssignmentArtifacts{}, err
	}
	if err := copyFile(sceneSource, filepath.Join(request.DatasetDir, filepath.FromSlash(proposalRelative))); err != nil {
		return group1AssignmentArtifacts{}, err
	}
	if err := copyFile(sceneSource, filepath.Join(request.DatasetDir, filepath.FromSlash(evalSceneRelative))); err != nil {
		return group1AssignmentArtifacts{}, err
	}
	if err := copyFile(querySource, filepath.Join(request.DatasetDir, filepath.FromSlash(evalQueryRelative))); err != nil {
		return group1AssignmentArtifacts{}, err
	}

	queryWidth, queryHeight, err := imageSize(querySource)
	if err != nil {
		return group1AssignmentArtifacts{}, err
	}
	sceneWidth, sceneHeight, err := imageSize(sceneSource)
	if err != nil {
		return group1AssignmentArtifacts{}, err
	}

	queryLines := make([]string, 0, len(record.QueryTargets))
	for _, object := range record.QueryTargets {
		queryLines = append(queryLines, toYOLOLine(withClass(object, 0, "query_item"), queryWidth, queryHeight))
	}
	queryLabelPath := filepath.Join(request.DatasetDir, "query-yolo", "labels", item.Split, stringsTrimExt(filepath.Base(querySource))+".txt")
	if err := os.WriteFile(queryLabelPath, []byte(joinLines(queryLines)), 0o644); err != nil {
		return group1AssignmentArtifacts{}, err
	}

	sceneObjects := append([]export.ObjectRecord(nil), record.SceneTargets...)
	sceneObjects = append(sceneObjects, record.Distractors...)
	proposalLines := make([]string, 0, len(sceneObjects))
	for _, object := range sceneObjects {
		proposalLines = append(proposalLines, toYOLOLine(withClass(object, 0, "icon_object"), sceneWidth, sceneHeight))
	}
	proposalLabelPath := filepath.Join(request.DatasetDir, "proposal-yolo", "labels", item.Split, stringsTrimExt(filepath.Base(sceneSource))+".txt")
	if err := os.WriteFile(proposalLabelPath, []byte(joinLines(proposalLines)), 0o644); err != nil {
		return group1AssignmentArtifacts{}, err
	}

	queryImage, err := decodeImage(querySource)
	if err != nil {
		return group1AssignmentArtifacts{}, err
	}
	sceneImage, err := decodeImage(sceneSource)
	if err != nil {
		return group1AssignmentArtifacts{}, err
	}
	queryCrops, err := writeGroup1QueryCrops(request.DatasetDir, item.Split, record.SampleID, queryImage, record.QueryTargets)
	if err != nil {
		return group1AssignmentArtifacts{}, err
	}
	targetCrops, distractorCrops, err := writeGroup1CandidateCrops(request.DatasetDir, item.Split, record.SampleID, sceneImage, record.SceneTargets, record.Distractors)
	if err != nil {
		return group1AssignmentArtifacts{}, err
	}
	embeddingPairs, embeddingTriplets, err := buildGroup1EmbeddingRecords(item.Split, record.SampleID, queryCrops, targetCrops, distractorCrops)
	if err != nil {
		return group1AssignmentArtifacts{}, err
	}

	record.SceneImage = evalSceneRelative
	record.QueryImage = evalQueryRelative
	return group1AssignmentArtifacts{
		SplitRow:          record,
		EvalRow:           record,
		EmbeddingPairs:    embeddingPairs,
		EmbeddingTriplets: embeddingTriplets,
	}, nil
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

type group1DatasetConfig struct {
	Task             string                `json:"task"`
	Format           string                `json:"format"`
	Splits           map[string]string     `json:"splits"`
	QueryDetector    yoloComponentConfig   `json:"query_detector"`
	ProposalDetector yoloComponentConfig   `json:"proposal_detector"`
	Embedding        group1EmbeddingConfig `json:"embedding"`
	Eval             group1EvalConfig      `json:"eval"`
}

type group1EmbeddingConfig struct {
	Format        string `json:"format"`
	QueriesDir    string `json:"queries_dir"`
	CandidatesDir string `json:"candidates_dir"`
	PairsJSONL    string `json:"pairs_jsonl"`
	TripletsJSONL string `json:"triplets_jsonl"`
}

type group1EvalConfig struct {
	Format      string `json:"format"`
	LabelsJSONL string `json:"labels_jsonl"`
}

type group1InstanceObjectRecord struct {
	Order       int     `json:"order,omitempty"`
	AssetID     string  `json:"asset_id,omitempty"`
	TemplateID  string  `json:"template_id,omitempty"`
	VariantID   string  `json:"variant_id,omitempty"`
	BBox        [4]int  `json:"bbox"`
	Center      [2]int  `json:"center"`
	RotationDeg float64 `json:"rotation_deg"`
	Alpha       float64 `json:"alpha"`
	Scale       float64 `json:"scale"`
}

type group1InstanceSampleRecord struct {
	SampleID        string                       `json:"sample_id"`
	CaptchaType     string                       `json:"captcha_type"`
	Mode            string                       `json:"mode"`
	Backend         string                       `json:"backend"`
	MaterialSet     string                       `json:"material_set,omitempty"`
	QueryImage      string                       `json:"query_image"`
	SceneImage      string                       `json:"scene_image"`
	QueryItems      []group1InstanceObjectRecord `json:"query_items"`
	SceneTargets    []group1InstanceObjectRecord `json:"scene_targets"`
	Distractors     []group1InstanceObjectRecord `json:"distractors"`
	BackgroundID    string                       `json:"background_id"`
	StyleID         string                       `json:"style_id"`
	SourceSignature string                       `json:"source_signature,omitempty"`
	LabelSource     string                       `json:"label_source"`
	TruthChecks     *export.TruthChecks          `json:"truth_checks,omitempty"`
	SourceBatch     string                       `json:"source_batch"`
	Seed            int64                        `json:"seed"`
}

func writeGroup1DatasetConfig(path string) error {
	content, err := json.MarshalIndent(
		group1DatasetConfig{
			Task:   "group1",
			Format: "sinan.group1.instance_matching.v1",
			Splits: map[string]string{
				"train": "splits/train.jsonl",
				"val":   "splits/val.jsonl",
				"test":  "splits/test.jsonl",
			},
			QueryDetector: yoloComponentConfig{
				Format:      "yolo.detect.v1",
				DatasetYAML: "query-yolo/dataset.yaml",
			},
			ProposalDetector: yoloComponentConfig{
				Format:      "yolo.detect.v1",
				DatasetYAML: "proposal-yolo/dataset.yaml",
			},
			Embedding: group1EmbeddingConfig{
				Format:        "sinan.group1.embedding.v1",
				QueriesDir:    "embedding/queries",
				CandidatesDir: "embedding/candidates",
				PairsJSONL:    "embedding/pairs.jsonl",
				TripletsJSONL: "embedding/triplets.jsonl",
			},
			Eval: group1EvalConfig{
				Format:      "sinan.group1.eval.v1",
				LabelsJSONL: "eval/labels.jsonl",
			},
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
		if err := writeJSONL(filepath.Join(datasetDir, "splits", split+".jsonl"), toGroup1InstanceRows(splitRows[split])); err != nil {
			return err
		}
	}
	return nil
}

func writeGroup2SplitJSONL(datasetDir string, splitRows map[string][]export.SampleRecord) error {
	for _, split := range []string{"train", "val", "test"} {
		if err := writeJSONL(filepath.Join(datasetDir, "splits", split+".jsonl"), splitRows[split]); err != nil {
			return err
		}
	}
	return nil
}

func writeGroup1EvalJSONL(datasetDir string, rows []export.SampleRecord) error {
	return writeJSONL(filepath.Join(datasetDir, "eval", "labels.jsonl"), toGroup1InstanceRows(rows))
}

func writeGroup1EmbeddingJSONL(datasetDir string, pairs []group1EmbeddingPairRecord, triplets []group1EmbeddingTripletRecord) error {
	if err := writeJSONL(filepath.Join(datasetDir, "embedding", "pairs.jsonl"), pairs); err != nil {
		return err
	}
	return writeJSONL(filepath.Join(datasetDir, "embedding", "triplets.jsonl"), triplets)
}

func writeGroup1QueryCrops(datasetDir string, split string, sampleID string, queryImage image.Image, queryTargets []export.ObjectRecord) ([]group1EmbeddingCrop, error) {
	crops := make([]group1EmbeddingCrop, 0, len(queryTargets))
	for index, object := range queryTargets {
		order := object.Order
		if order <= 0 {
			order = index + 1
		}
		relativePath := filepath.ToSlash(filepath.Join("embedding", "queries", split, fmt.Sprintf("%s__query_%02d.png", sampleID, order)))
		if err := writeCroppedPNG(filepath.Join(datasetDir, filepath.FromSlash(relativePath)), queryImage, object.BBox); err != nil {
			return nil, err
		}
		crops = append(crops, group1EmbeddingCrop{
			RelativePath: relativePath,
			Object:       object,
			Role:         "query_item",
		})
	}
	return crops, nil
}

func writeGroup1CandidateCrops(datasetDir string, split string, sampleID string, sceneImage image.Image, sceneTargets []export.ObjectRecord, distractors []export.ObjectRecord) ([]group1EmbeddingCrop, []group1EmbeddingCrop, error) {
	targetCrops := make([]group1EmbeddingCrop, 0, len(sceneTargets))
	for index, object := range sceneTargets {
		order := object.Order
		if order <= 0 {
			order = index + 1
		}
		relativePath := filepath.ToSlash(filepath.Join("embedding", "candidates", split, fmt.Sprintf("%s__target_%02d.png", sampleID, order)))
		if err := writeCroppedPNG(filepath.Join(datasetDir, filepath.FromSlash(relativePath)), sceneImage, object.BBox); err != nil {
			return nil, nil, err
		}
		targetCrops = append(targetCrops, group1EmbeddingCrop{
			RelativePath: relativePath,
			Object:       object,
			Role:         "scene_target",
		})
	}

	distractorCrops := make([]group1EmbeddingCrop, 0, len(distractors))
	for index, object := range distractors {
		relativePath := filepath.ToSlash(filepath.Join("embedding", "candidates", split, fmt.Sprintf("%s__distractor_%02d.png", sampleID, index+1)))
		if err := writeCroppedPNG(filepath.Join(datasetDir, filepath.FromSlash(relativePath)), sceneImage, object.BBox); err != nil {
			return nil, nil, err
		}
		distractorCrops = append(distractorCrops, group1EmbeddingCrop{
			RelativePath: relativePath,
			Object:       object,
			Role:         "distractor",
		})
	}
	return targetCrops, distractorCrops, nil
}

func buildGroup1EmbeddingRecords(split string, sampleID string, queryCrops []group1EmbeddingCrop, targetCrops []group1EmbeddingCrop, distractorCrops []group1EmbeddingCrop) ([]group1EmbeddingPairRecord, []group1EmbeddingTripletRecord, error) {
	pairs := []group1EmbeddingPairRecord{}
	triplets := []group1EmbeddingTripletRecord{}
	for _, queryCrop := range queryCrops {
		positiveCrop, ok := findMatchingTargetCrop(queryCrop.Object, targetCrops)
		if !ok {
			return nil, nil, fmt.Errorf("group1 sample %s query order %d missing matching scene target", sampleID, queryCrop.Object.Order)
		}
		pairs = append(pairs, group1EmbeddingPairRecord{
			Split:          split,
			SampleID:       sampleID,
			Label:          1,
			QueryImage:     queryCrop.RelativePath,
			CandidateImage: positiveCrop.RelativePath,
			QueryItem:      queryCrop.Object,
			Candidate:      positiveCrop.Object,
			CandidateRole:  positiveCrop.Role,
		})

		negativeCrops := make([]group1EmbeddingCrop, 0, len(targetCrops)+len(distractorCrops))
		for _, targetCrop := range targetCrops {
			if targetCrop.RelativePath == positiveCrop.RelativePath {
				continue
			}
			negativeCrops = append(negativeCrops, targetCrop)
		}
		negativeCrops = append(negativeCrops, distractorCrops...)
		for _, negativeCrop := range negativeCrops {
			pairs = append(pairs, group1EmbeddingPairRecord{
				Split:          split,
				SampleID:       sampleID,
				Label:          0,
				QueryImage:     queryCrop.RelativePath,
				CandidateImage: negativeCrop.RelativePath,
				QueryItem:      queryCrop.Object,
				Candidate:      negativeCrop.Object,
				CandidateRole:  negativeCrop.Role,
			})
			triplets = append(triplets, group1EmbeddingTripletRecord{
				Split:         split,
				SampleID:      sampleID,
				AnchorImage:   queryCrop.RelativePath,
				PositiveImage: positiveCrop.RelativePath,
				NegativeImage: negativeCrop.RelativePath,
				Anchor:        queryCrop.Object,
				Positive:      positiveCrop.Object,
				Negative:      negativeCrop.Object,
				NegativeRole:  negativeCrop.Role,
			})
		}
	}
	return pairs, triplets, nil
}

func findMatchingTargetCrop(queryObject export.ObjectRecord, targetCrops []group1EmbeddingCrop) (group1EmbeddingCrop, bool) {
	for _, targetCrop := range targetCrops {
		if queryObject.Order > 0 && targetCrop.Object.Order == queryObject.Order {
			return targetCrop, true
		}
	}
	for _, targetCrop := range targetCrops {
		if targetCrop.Object.AssetID == queryObject.AssetID && targetCrop.Object.TemplateID == queryObject.TemplateID && targetCrop.Object.VariantID == queryObject.VariantID {
			return targetCrop, true
		}
	}
	return group1EmbeddingCrop{}, false
}

func toGroup1InstanceRows(rows []export.SampleRecord) []group1InstanceSampleRecord {
	projected := make([]group1InstanceSampleRecord, 0, len(rows))
	for _, row := range rows {
		projected = append(projected, group1InstanceSampleRecord{
			SampleID:        row.SampleID,
			CaptchaType:     row.CaptchaType,
			Mode:            row.Mode,
			Backend:         row.Backend,
			MaterialSet:     row.MaterialSet,
			QueryImage:      row.QueryImage,
			SceneImage:      row.SceneImage,
			QueryItems:      toGroup1InstanceObjects(row.QueryTargets),
			SceneTargets:    toGroup1InstanceObjects(row.SceneTargets),
			Distractors:     toGroup1InstanceObjects(row.Distractors),
			BackgroundID:    row.BackgroundID,
			StyleID:         row.StyleID,
			SourceSignature: row.SourceSignature,
			LabelSource:     row.LabelSource,
			TruthChecks:     row.TruthChecks,
			SourceBatch:     row.SourceBatch,
			Seed:            row.Seed,
		})
	}
	return projected
}

func toGroup1InstanceObjects(objects []export.ObjectRecord) []group1InstanceObjectRecord {
	projected := make([]group1InstanceObjectRecord, 0, len(objects))
	for _, object := range objects {
		projected = append(projected, group1InstanceObjectRecord{
			Order:       object.Order,
			AssetID:     object.AssetID,
			TemplateID:  object.TemplateID,
			VariantID:   object.VariantID,
			BBox:        object.BBox,
			Center:      object.Center,
			RotationDeg: object.RotationDeg,
			Alpha:       object.Alpha,
			Scale:       object.Scale,
		})
	}
	return projected
}

func writeJSONL[T any](path string, rows []T) error {
	content := make([]byte, 0, len(rows)*256)
	for _, row := range rows {
		line, err := json.Marshal(row)
		if err != nil {
			return err
		}
		content = append(content, line...)
		content = append(content, '\n')
	}
	return os.WriteFile(path, content, 0o644)
}

func withClass(object export.ObjectRecord, classID int, className string) export.ObjectRecord {
	object.ClassID = classID
	object.Class = className
	return object
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

func decodeImage(path string) (image.Image, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	imageData, _, err := image.Decode(file)
	if err != nil {
		return nil, err
	}
	return imageData, nil
}

func writeCroppedPNG(path string, source image.Image, bbox [4]int) error {
	x1, y1, x2, y2 := clampBBox(source.Bounds(), bbox)
	if x2 <= x1 || y2 <= y1 {
		return fmt.Errorf("invalid crop bbox: %v", bbox)
	}
	dst := image.NewRGBA(image.Rect(0, 0, x2-x1, y2-y1))
	draw.Draw(dst, dst.Bounds(), source, image.Point{X: x1, Y: y1}, draw.Src)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	return png.Encode(file, dst)
}

func clampBBox(bounds image.Rectangle, bbox [4]int) (int, int, int, int) {
	x1 := maxInt(bounds.Min.X, bbox[0])
	y1 := maxInt(bounds.Min.Y, bbox[1])
	x2 := minInt(bounds.Max.X, bbox[2])
	y2 := minInt(bounds.Max.Y, bbox[3])
	return x1, y1, x2, y2
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

func minInt(left int, right int) int {
	if left < right {
		return left
	}
	return right
}
