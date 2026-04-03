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
		"Commands:\n" +
		"  workspace init                Create or refresh the fixed workspace.\n" +
		"  workspace show                Print workspace metadata.\n" +
		"  materials import              Import a local materials pack into the workspace.\n" +
		"  materials fetch               Fetch a zipped materials pack into the workspace.\n" +
		"  make-dataset                  Generate a ready-to-train YOLO dataset directory.\n\n" +
		"Examples:\n" +
		"  sinan-generator workspace init\n" +
		"  sinan-generator materials import --from D:\\materials-pack\n" +
		"  sinan-generator make-dataset --task group1 --dataset-dir D:\\datasets\\group1\\firstpass\\yolo\n"
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
		result, err := materialset.ImportLocal(state, *sourceDir, *name)
		if err != nil {
			return err
		}
		return printJSON(result)
	case "fetch":
		fs := flag.NewFlagSet("materials fetch", flag.ContinueOnError)
		workspaceRoot := fs.String("workspace", "", "override workspace root")
		source := fs.String("source", "", "http(s) URL, file URL, or local zip path")
		name := fs.String("name", "", "optional materials set name")
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
		result, err := materialset.FetchArchive(state, *source, *name)
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
	presetName := fs.String("preset", "firstpass", "preset name: firstpass or smoke")
	datasetDir := fs.String("dataset-dir", "", "path to the output dataset directory")
	workspaceRoot := fs.String("workspace", "", "override workspace root")
	materialsSelector := fs.String("materials", "", "materials selector in the form official/name or local/name")
	materialSource := fs.String("materials-source", "", "optional local dir, local zip, file URL, or http(s) URL")
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
