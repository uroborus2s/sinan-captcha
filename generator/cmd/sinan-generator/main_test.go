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
		"Presets: firstpass=200 samples, hard=200 samples, smoke=20 samples.",
		"Optional preset overrides are loaded from workspace\\presets\\smoke.yaml, group1.<preset>.yaml, or group2.<preset>.yaml.",
		"make-dataset --preset accepts firstpass, hard, or smoke.",
		"Re-running make-dataset with --force overwrites the same dataset directory.",
		"sinan-generator make-dataset --workspace D:\\sinan-captcha-generator\\workspace --task group1 --dataset-dir D:\\sinan-captcha-work\\datasets\\group1\\firstpass\\yolo",
	}

	for _, want := range checks {
		if !strings.Contains(text, want) {
			t.Fatalf("usage() missing %q\nfull text:\n%s", want, text)
		}
	}
}
