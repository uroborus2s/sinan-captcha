package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"sinan-captcha/generator/internal/app"
	"sinan-captcha/generator/internal/materialset"
	"sinan-captcha/generator/internal/workspace"
)

func main() {
	code := run(os.Args[1:])
	os.Exit(code)
}

func run(args []string) int {
	if len(args) == 0 {
		state, err := workspace.Ensure("")
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			return 1
		}
		fmt.Printf("workspace ready: %s\n\n", state.Layout.Root)
		fmt.Print(usage())
		return 0
	}

	var err error
	switch args[0] {
	case "workspace":
		err = runWorkspace(args[1:])
	case "materials":
		err = runMaterials(args[1:])
	case "make-dataset":
		err = runMakeDataset(args[1:])
	case "help", "-h", "--help":
		fmt.Print(usage())
		return 0
	default:
		err = fmt.Errorf("unknown command: %s", args[0])
	}

	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		fmt.Fprintln(os.Stderr)
		fmt.Fprint(os.Stderr, usage())
		return 1
	}
	return 0
}

func usage() string {
	return "" +
		"sinan-generator <command>\n\n" +
		"PowerShell users should run .\\sinan-generator.exe when launching from the current directory.\n\n" +
		"Commands:\n" +
		"  workspace init                Create or refresh the fixed workspace.\n" +
		"  workspace show                Print workspace metadata.\n" +
		"  materials import              Import a local materials pack into the workspace.\n" +
		"  materials fetch               Fetch a zipped materials pack into the workspace.\n" +
		"  materials merge               Merge incoming raw images into an existing materials root.\n" +
		"  make-dataset                  Generate a ready-to-train YOLO dataset directory.\n\n" +
		"Notes:\n" +
		"  Presets: firstpass=200 samples, hard=200 samples, smoke=20 samples.\n" +
		"  make-dataset --preset accepts firstpass, hard, or smoke.\n" +
		"  make-dataset also accepts --override-file with JSON overrides for sample_count, sampling, and effects.\n" +
		"  Optional preset overrides are loaded from workspace\\presets\\smoke.yaml, group1.<preset>.yaml, or group2.<preset>.yaml.\n" +
		"  Materials can come from a local directory, a local zip, or an http(s) zip URL.\n" +
		"  materials import/fetch also accept --task group1|group2 when the materials pack only contains one task.\n" +
		"  Re-running make-dataset with --force overwrites the same dataset directory.\n\n" +
		"Examples:\n" +
		"  sinan-generator workspace init --workspace D:\\sinan-captcha-generator\\workspace\n" +
		"  sinan-generator materials import --workspace D:\\sinan-captcha-generator\\workspace --from D:\\materials-pack\n" +
		"  sinan-generator materials import --workspace D:\\sinan-captcha-generator\\workspace --from D:\\materials-pack-group1 --task group1\n" +
		"  sinan-generator materials fetch --workspace D:\\sinan-captcha-generator\\workspace --source https://example.com/materials-pack.zip\n" +
		"  sinan-generator materials merge --into D:\\materials-pack --from D:\\incoming-materials\n" +
		"  sinan-generator make-dataset --workspace D:\\sinan-captcha-generator\\workspace --task group1 --dataset-dir D:\\sinan-captcha-work\\datasets\\group1\\firstpass\\yolo\n"
}

func runWorkspace(args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("workspace subcommand is required")
	}
	switch args[0] {
	case "init":
		fs := flag.NewFlagSet("workspace init", flag.ContinueOnError)
		workspaceRoot := fs.String("workspace", "", "override workspace root")
		if err := fs.Parse(args[1:]); err != nil {
			return err
		}
		state, err := workspace.Ensure(*workspaceRoot)
		if err != nil {
			return err
		}
		return printJSON(state.Metadata)
	case "show":
		fs := flag.NewFlagSet("workspace show", flag.ContinueOnError)
		workspaceRoot := fs.String("workspace", "", "override workspace root")
		if err := fs.Parse(args[1:]); err != nil {
			return err
		}
		state, err := workspace.Ensure(*workspaceRoot)
		if err != nil {
			return err
		}
		return printJSON(struct {
			Metadata workspace.Metadata `json:"metadata"`
			Layout   workspace.Layout   `json:"layout"`
		}{
			Metadata: state.Metadata,
			Layout:   state.Layout,
		})
	default:
		return fmt.Errorf("unknown workspace subcommand: %s", args[0])
	}
}

func runMaterials(args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("materials subcommand is required")
	}
	switch args[0] {
	case "import":
		fs := flag.NewFlagSet("materials import", flag.ContinueOnError)
		workspaceRoot := fs.String("workspace", "", "override workspace root")
		sourceDir := fs.String("from", "", "path to a local materials directory")
		name := fs.String("name", "", "optional materials set name")
		task := fs.String("task", "", "optional task-scoped validation: group1 or group2")
		if err := fs.Parse(args[1:]); err != nil {
			return err
		}
		if *sourceDir == "" {
			return fmt.Errorf("--from is required")
		}
		state, err := workspace.Ensure(*workspaceRoot)
		if err != nil {
			return err
		}
		result, err := materialset.ImportLocal(state, *sourceDir, *name, *task)
		if err != nil {
			return err
		}
		return printJSON(result)
	case "fetch":
		fs := flag.NewFlagSet("materials fetch", flag.ContinueOnError)
		workspaceRoot := fs.String("workspace", "", "override workspace root")
		source := fs.String("source", "", "http(s) URL, file URL, or local zip path")
		name := fs.String("name", "", "optional materials set name")
		task := fs.String("task", "", "optional task-scoped validation: group1 or group2")
		if err := fs.Parse(args[1:]); err != nil {
			return err
		}
		if *source == "" {
			return fmt.Errorf("--source is required")
		}
		state, err := workspace.Ensure(*workspaceRoot)
		if err != nil {
			return err
		}
		result, err := materialset.FetchArchive(state, *source, *name, *task)
		if err != nil {
			return err
		}
		return printJSON(result)
	case "merge":
		fs := flag.NewFlagSet("materials merge", flag.ContinueOnError)
		targetRoot := fs.String("into", "", "path to an existing materials root")
		incomingRoot := fs.String("from", "", "path to an incoming directory with backgrounds/, group1/, and group2/")
		if err := fs.Parse(args[1:]); err != nil {
			return err
		}
		if *targetRoot == "" {
			return fmt.Errorf("--into is required")
		}
		if *incomingRoot == "" {
			return fmt.Errorf("--from is required")
		}
		result, err := materialset.Merge(*targetRoot, *incomingRoot)
		if err != nil {
			return err
		}
		return printJSON(result)
	default:
		return fmt.Errorf("unknown materials subcommand: %s", args[0])
	}
}

func runMakeDataset(args []string) error {
	fs := flag.NewFlagSet("make-dataset", flag.ContinueOnError)
	task := fs.String("task", "group1", "dataset task: group1 or group2")
	presetName := fs.String("preset", "firstpass", "preset name: firstpass, hard, or smoke")
	datasetDir := fs.String("dataset-dir", "", "path to the output dataset directory")
	workspaceRoot := fs.String("workspace", "", "override workspace root")
	materialsSelector := fs.String("materials", "", "materials selector in the form official/name or local/name")
	materialSource := fs.String("materials-source", "", "optional local dir, local zip, file URL, or http(s) URL")
	overrideFile := fs.String("override-file", "", "optional JSON override file for sample_count, sampling, and effects")
	force := fs.Bool("force", false, "overwrite generated files in the training directory")
	if err := fs.Parse(args); err != nil {
		return err
	}

	result, err := app.MakeDataset(app.MakeDatasetRequest{
		Task:           *task,
		Preset:         *presetName,
		WorkspaceRoot:  *workspaceRoot,
		DatasetDir:     *datasetDir,
		Materials:      *materialsSelector,
		MaterialSource: *materialSource,
		OverrideFile:   *overrideFile,
		Force:          *force,
		Writer:         os.Stdout,
	})
	if err != nil {
		return err
	}
	return printJSON(result)
}

func printJSON(value any) error {
	content, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	fmt.Println(string(content))
	return nil
}
