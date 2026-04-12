package main

import (
	"strings"
	"testing"
)

func TestUsageIncludesCurrentUserGuidance(t *testing.T) {
	text := usage()

	checks := []string{
		"PowerShell users should run .\\sinan-generator.exe",
		"make-dataset                  Generate a ready-to-train YOLO dataset directory.",
		"Presets: smoke=200 samples, v1=10000 samples, firstpass=200 samples (legacy), hard=200 samples.",
		"Optional preset overrides are loaded from workspace\\presets\\smoke.yaml, group1.<preset>.yaml, or group2.<preset>.yaml.",
		"make-dataset --preset accepts smoke, v1, firstpass, or hard.",
		"make-dataset also accepts --override-file with JSON overrides for sample_count, sampling, and effects.",
		"Without --materials, make-dataset samples from every task-compatible pack in the workspace.",
		"Pass --runtime-seed to reproduce one specific generation run.",
		"materials import/fetch also accept --task group1|group2 when the materials pack only contains one task.",
		"Re-running make-dataset with --force overwrites the same dataset directory.",
		"sinan-generator materials import --workspace D:\\sinan-captcha-generator\\workspace --from D:\\materials-pack-v3-group1 --task group1",
		"sinan-generator make-dataset --workspace D:\\sinan-captcha-generator\\workspace --task group1 --preset v1 --dataset-dir D:\\sinan-captcha-work\\datasets\\group1\\v1\\yolo",
	}

	for _, want := range checks {
		if !strings.Contains(text, want) {
			t.Fatalf("usage() missing %q\nfull text:\n%s", want, text)
		}
	}
}
