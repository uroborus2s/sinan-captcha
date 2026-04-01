package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"sinan-captcha/generator/internal/config"
	"sinan-captcha/generator/internal/export"
	"sinan-captcha/generator/internal/material"
	"sinan-captcha/generator/internal/qa"
	"sinan-captcha/generator/internal/render"
	"sinan-captcha/generator/internal/sampler"
)

func main() {
	if len(os.Args) < 2 {
		printUsage()
		os.Exit(1)
	}

	var err error
	switch os.Args[1] {
	case "validate-materials":
		err = runValidateMaterials(os.Args[2:])
	case "generate":
		err = runGenerate(os.Args[2:])
	case "qa":
		err = runQA(os.Args[2:])
	default:
		err = fmt.Errorf("unknown command: %s", os.Args[1])
	}

	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		printUsage()
		os.Exit(1)
	}
}

func printUsage() {
	fmt.Println("sinan-click-generator <validate-materials|generate|qa>")
}

func runValidateMaterials(args []string) error {
	fs := flag.NewFlagSet("validate-materials", flag.ContinueOnError)
	configPath := fs.String("config", "generator/configs/default.yaml", "path to generator config")
	materialsRoot := fs.String("materials-root", "materials", "path to materials root")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if _, err := config.Load(*configPath); err != nil {
		return err
	}
	summary, err := material.Validate(*materialsRoot)
	if err != nil {
		return err
	}
	return printJSON(summary)
}

func runGenerate(args []string) error {
	fs := flag.NewFlagSet("generate", flag.ContinueOnError)
	configPath := fs.String("config", "generator/configs/default.yaml", "path to generator config")
	materialsRoot := fs.String("materials-root", "materials", "path to materials root")
	outputRoot := fs.String("output-root", "generator/output/group1", "path to batch output root")
	if err := fs.Parse(args); err != nil {
		return err
	}

	cfg, err := config.Load(*configPath)
	if err != nil {
		return err
	}
	summary, err := material.Validate(*materialsRoot)
	if err != nil {
		return err
	}
	catalog, err := material.LoadCatalog(*materialsRoot)
	if err != nil {
		return err
	}
	writer, err := export.NewBatchWriter(*outputRoot, *configPath, cfg, summary)
	if err != nil {
		return err
	}
	for index := 0; index < cfg.Project.SampleCount; index++ {
		plan, err := sampler.BuildPlan(index, cfg, catalog)
		if err != nil {
			return err
		}
		queryImage, sceneImage, err := render.Build(plan, cfg.Canvas)
		if err != nil {
			return err
		}
		if err := writer.WriteSample(plan.Record, queryImage, sceneImage); err != nil {
			return err
		}
	}
	result, err := writer.Finalize()
	if err != nil {
		return err
	}
	return printJSON(result)
}

func runQA(args []string) error {
	fs := flag.NewFlagSet("qa", flag.ContinueOnError)
	configPath := fs.String("config", "generator/configs/default.yaml", "path to generator config")
	materialsRoot := fs.String("materials-root", "materials", "path to materials root")
	batchDir := fs.String("batch-dir", "", "path to generated batch root")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *batchDir == "" {
		return fmt.Errorf("--batch-dir is required")
	}
	if _, err := config.Load(*configPath); err != nil {
		return err
	}
	if _, err := material.Validate(*materialsRoot); err != nil {
		return err
	}
	summary, err := qa.InspectBatch(*batchDir)
	if err != nil {
		return err
	}
	return printJSON(summary)
}

func printJSON(value any) error {
	content, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	fmt.Println(string(content))
	return nil
}
