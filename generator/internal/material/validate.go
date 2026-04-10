package material

import (
	"errors"
	"fmt"
	"image"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

type ValidationSummary struct {
	SchemaVersion               int    `json:"schema_version"`
	MaterialsManifestPath       string `json:"materials_manifest_path"`
	Group1TemplatesManifestPath string `json:"group1_templates_manifest_path"`
	Group2ManifestPath          string `json:"group2_manifest_path"`
	BackgroundCount             int    `json:"background_count"`
	Group1TemplateCount         int    `json:"group1_template_count"`
	Group1VariantCount          int    `json:"group1_variant_count"`
	Group2ShapeCount            int    `json:"group2_shape_count"`
	Group2ShapeDirCount         int    `json:"group2_shape_dir_count"`
}

func Validate(root string) (ValidationSummary, error) {
	return validateForTask(root, "", true)
}

func ValidateForTask(root string, task string) (ValidationSummary, error) {
	return validateForTask(root, task, true)
}

func validateForTask(root string, task string, requireBackgrounds bool) (ValidationSummary, error) {
	summary := ValidationSummary{
		MaterialsManifestPath:       filepath.Join(root, "manifests", "materials.yaml"),
		Group1TemplatesManifestPath: filepath.Join(root, "manifests", "group1.templates.yaml"),
		Group2ManifestPath:          filepath.Join(root, "manifests", "group2.shapes.yaml"),
	}

	materialsManifest, err := LoadMaterialsManifest(summary.MaterialsManifestPath)
	if err != nil {
		return summary, err
	}
	if materialsManifest.SchemaVersion != CurrentSchemaVersion {
		return summary, fmt.Errorf("unsupported materials schema version: %d", materialsManifest.SchemaVersion)
	}
	summary.SchemaVersion = materialsManifest.SchemaVersion

	backgroundCount, err := countValidImageFiles(filepath.Join(root, "backgrounds"))
	if err != nil && !os.IsNotExist(err) {
		return summary, err
	}
	if requireBackgrounds && backgroundCount == 0 {
		return summary, errors.New("no background images found")
	}
	summary.BackgroundCount = backgroundCount

	switch strings.TrimSpace(task) {
	case "", "all":
		if err := validateGroup1(root, &summary); err != nil {
			return summary, err
		}
		if err := validateGroup2(root, &summary); err != nil {
			return summary, err
		}
	case "group1":
		if err := validateGroup1(root, &summary); err != nil {
			return summary, err
		}
	case "group2":
		if err := validateGroup2(root, &summary); err != nil {
			return summary, err
		}
	default:
		return summary, fmt.Errorf("unsupported materials task: %s", task)
	}

	return summary, nil
}

func validateGroup1(root string, summary *ValidationSummary) error {
	manifest, err := LoadGroup1TemplatesManifest(summary.Group1TemplatesManifestPath)
	if err != nil {
		return err
	}
	summary.Group1TemplateCount = len(manifest.Templates)
	if summary.Group1TemplateCount == 0 {
		return errors.New("group1 templates manifest is empty")
	}
	for _, template := range manifest.Templates {
		templateDir := filepath.Join(root, "group1", "icons", template.TemplateID)
		info, err := os.Stat(templateDir)
		if err != nil {
			if os.IsNotExist(err) {
				return errors.New("missing group1 template directory: " + template.TemplateID)
			}
			return err
		}
		if !info.IsDir() {
			return fmt.Errorf("group1 template path is not a directory: %s", templateDir)
		}
		for _, variant := range template.Variants {
			summary.Group1VariantCount++
			variantPath := filepath.Join(templateDir, variant.VariantID+".png")
			if err := validateImageFile(variantPath); err != nil {
				return fmt.Errorf("invalid group1 variant %s/%s: %w", template.TemplateID, variant.VariantID, err)
			}
		}
	}
	return nil
}

func validateGroup2(root string, summary *ValidationSummary) error {
	group2Entries, err := LoadGroup2Manifest(summary.Group2ManifestPath)
	if err != nil {
		return err
	}
	summary.Group2ShapeCount = len(group2Entries)
	if summary.Group2ShapeCount == 0 {
		return errors.New("group2 shapes manifest is empty")
	}
	for _, entry := range group2Entries {
		count, err := countValidImageFiles(filepath.Join(root, "group2", "shapes", entry.Name))
		if err != nil && !os.IsNotExist(err) {
			return err
		}
		if count == 0 {
			return errors.New("no group2 shape images found for shape: " + entry.Name)
		}
		summary.Group2ShapeDirCount++
	}
	return nil
}

func LoadMaterialsManifest(path string) (MaterialsManifest, error) {
	manifest := MaterialsManifest{}
	content, err := os.ReadFile(path)
	if err != nil {
		return manifest, err
	}
	for lineNumber, rawLine := range strings.Split(string(content), "\n") {
		line := strings.TrimSpace(rawLine)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		key, value, err := splitManifestField(line)
		if err != nil {
			return manifest, fmt.Errorf("invalid materials manifest line %d: %w", lineNumber+1, err)
		}
		switch key {
		case "schema_version":
			parsed, err := strconv.Atoi(value)
			if err != nil {
				return manifest, fmt.Errorf("invalid materials manifest line %d: %w", lineNumber+1, err)
			}
			manifest.SchemaVersion = parsed
		default:
			return manifest, fmt.Errorf("invalid materials manifest line %d: unsupported key: %s", lineNumber+1, key)
		}
	}
	if manifest.SchemaVersion == 0 {
		return manifest, errors.New("materials schema_version is required")
	}
	return manifest, nil
}

type Group1VariantEntry struct {
	VariantID string
	Source    string
	SourceRef string
	Style     string
}

type Group1TemplateEntry struct {
	TemplateID string
	ZhName     string
	Family     string
	Tags       []string
	Status     string
	Variants   []Group1VariantEntry
}

type Group1TemplatesManifest struct {
	SchemaVersion int
	Task          string
	Mode          string
	Templates     []Group1TemplateEntry
}

func LoadGroup1TemplatesManifest(path string) (Group1TemplatesManifest, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return Group1TemplatesManifest{}, err
	}
	return parseGroup1TemplatesManifest(content)
}

func LoadGroup2Manifest(path string) ([]CatalogEntry, error) {
	return loadCatalogEntries(path, "shapes")
}

func loadCatalogEntries(path string, section string) ([]CatalogEntry, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return parseCatalogEntries(content, section)
}

func countValidImageFiles(dir string) (int, error) {
	files, err := listImageFiles(dir)
	if err != nil {
		return 0, err
	}
	for _, path := range files {
		if err := validateImageFile(path); err != nil {
			return 0, fmt.Errorf("invalid image file %s: %w", path, err)
		}
	}
	return len(files), nil
}

func validateImageFile(path string) error {
	file, err := os.Open(path)
	if err != nil {
		return err
	}
	defer file.Close()

	img, _, err := image.Decode(file)
	if err != nil {
		return err
	}
	bounds := img.Bounds()
	if bounds.Dx() <= 0 || bounds.Dy() <= 0 {
		return fmt.Errorf("invalid image bounds %dx%d", bounds.Dx(), bounds.Dy())
	}
	return nil
}

func parseCatalogEntries(content []byte, section string) ([]CatalogEntry, error) {
	entries := make([]CatalogEntry, 0)
	inSection := false
	var current *CatalogEntry

	for lineNumber, rawLine := range strings.Split(string(content), "\n") {
		line := strings.TrimSpace(rawLine)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if line == section+":" {
			inSection = true
			continue
		}
		if !inSection {
			continue
		}
		if strings.HasSuffix(line, ":") && !strings.HasPrefix(line, "- ") {
			return nil, fmt.Errorf("invalid manifest line %d: unexpected section %s", lineNumber+1, line)
		}

		if strings.HasPrefix(line, "- ") {
			entries = append(entries, CatalogEntry{})
			current = &entries[len(entries)-1]
			line = strings.TrimSpace(strings.TrimPrefix(line, "- "))
			if line == "" {
				continue
			}
		}
		if current == nil {
			return nil, fmt.Errorf("invalid manifest line %d: item not started", lineNumber+1)
		}

		key, value, err := splitManifestField(line)
		if err != nil {
			return nil, fmt.Errorf("invalid manifest line %d: %w", lineNumber+1, err)
		}
		if err := assignCatalogEntryField(current, key, value); err != nil {
			return nil, fmt.Errorf("invalid manifest line %d: %w", lineNumber+1, err)
		}
	}

	return entries, nil
}

func parseGroup1TemplatesManifest(content []byte) (Group1TemplatesManifest, error) {
	manifest := Group1TemplatesManifest{}
	inTemplates := false
	var currentTemplate *Group1TemplateEntry
	var currentVariant *Group1VariantEntry

	for lineNumber, rawLine := range strings.Split(string(content), "\n") {
		if strings.ContainsRune(rawLine, '\t') {
			return manifest, fmt.Errorf("invalid manifest line %d: tabs are not supported", lineNumber+1)
		}
		line := strings.TrimSpace(rawLine)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		indent := len(rawLine) - len(strings.TrimLeft(rawLine, " "))

		if !inTemplates {
			if line == "templates:" {
				inTemplates = true
				continue
			}
			key, value, err := splitManifestField(line)
			if err != nil {
				return manifest, fmt.Errorf("invalid manifest line %d: %w", lineNumber+1, err)
			}
			switch key {
			case "schema_version":
				parsed, err := strconv.Atoi(value)
				if err != nil {
					return manifest, fmt.Errorf("invalid manifest line %d: %w", lineNumber+1, err)
				}
				manifest.SchemaVersion = parsed
			case "task":
				manifest.Task = value
			case "mode":
				manifest.Mode = value
			default:
				return manifest, fmt.Errorf("invalid manifest line %d: unsupported key: %s", lineNumber+1, key)
			}
			continue
		}

		switch {
		case indent == 2 && strings.HasPrefix(line, "- "):
			manifest.Templates = append(manifest.Templates, Group1TemplateEntry{})
			currentTemplate = &manifest.Templates[len(manifest.Templates)-1]
			currentVariant = nil
			remainder := strings.TrimSpace(strings.TrimPrefix(line, "- "))
			if remainder == "" {
				continue
			}
			key, value, err := splitManifestField(remainder)
			if err != nil {
				return manifest, fmt.Errorf("invalid manifest line %d: %w", lineNumber+1, err)
			}
			if err := assignGroup1TemplateField(currentTemplate, key, value); err != nil {
				return manifest, fmt.Errorf("invalid manifest line %d: %w", lineNumber+1, err)
			}
		case indent == 4 && line == "variants:":
			if currentTemplate == nil {
				return manifest, fmt.Errorf("invalid manifest line %d: variants block before template", lineNumber+1)
			}
			currentVariant = nil
		case indent == 4:
			if currentTemplate == nil {
				return manifest, fmt.Errorf("invalid manifest line %d: template field before template item", lineNumber+1)
			}
			key, value, err := splitManifestField(line)
			if err != nil {
				return manifest, fmt.Errorf("invalid manifest line %d: %w", lineNumber+1, err)
			}
			if err := assignGroup1TemplateField(currentTemplate, key, value); err != nil {
				return manifest, fmt.Errorf("invalid manifest line %d: %w", lineNumber+1, err)
			}
		case indent == 6 && strings.HasPrefix(line, "- "):
			if currentTemplate == nil {
				return manifest, fmt.Errorf("invalid manifest line %d: variant item before template item", lineNumber+1)
			}
			currentTemplate.Variants = append(currentTemplate.Variants, Group1VariantEntry{})
			currentVariant = &currentTemplate.Variants[len(currentTemplate.Variants)-1]
			remainder := strings.TrimSpace(strings.TrimPrefix(line, "- "))
			if remainder == "" {
				continue
			}
			key, value, err := splitManifestField(remainder)
			if err != nil {
				return manifest, fmt.Errorf("invalid manifest line %d: %w", lineNumber+1, err)
			}
			if err := assignGroup1VariantField(currentVariant, key, value); err != nil {
				return manifest, fmt.Errorf("invalid manifest line %d: %w", lineNumber+1, err)
			}
		case indent == 8:
			if currentVariant == nil {
				return manifest, fmt.Errorf("invalid manifest line %d: variant field before variant item", lineNumber+1)
			}
			key, value, err := splitManifestField(line)
			if err != nil {
				return manifest, fmt.Errorf("invalid manifest line %d: %w", lineNumber+1, err)
			}
			if err := assignGroup1VariantField(currentVariant, key, value); err != nil {
				return manifest, fmt.Errorf("invalid manifest line %d: %w", lineNumber+1, err)
			}
		default:
			return manifest, fmt.Errorf("invalid manifest line %d: unsupported indentation or structure", lineNumber+1)
		}
	}

	if manifest.SchemaVersion == 0 {
		return manifest, errors.New("group1 templates schema_version is required")
	}
	if manifest.Task != "group1" {
		return manifest, fmt.Errorf("group1 templates manifest task must be group1, got %q", manifest.Task)
	}
	if strings.TrimSpace(manifest.Mode) == "" {
		return manifest, errors.New("group1 templates manifest mode is required")
	}
	if len(manifest.Templates) == 0 {
		return manifest, errors.New("group1 templates manifest is empty")
	}

	seenTemplates := make(map[string]struct{}, len(manifest.Templates))
	for index, template := range manifest.Templates {
		if err := validateGroup1ID("template_id", template.TemplateID); err != nil {
			return manifest, fmt.Errorf("group1 templates[%d]: %w", index, err)
		}
		if _, exists := seenTemplates[template.TemplateID]; exists {
			return manifest, fmt.Errorf("duplicate group1 template_id: %s", template.TemplateID)
		}
		seenTemplates[template.TemplateID] = struct{}{}
		if len(template.Variants) == 0 {
			return manifest, fmt.Errorf("group1 template %s has no variants", template.TemplateID)
		}
		seenVariants := make(map[string]struct{}, len(template.Variants))
		for variantIndex, variant := range template.Variants {
			if err := validateGroup1ID("variant_id", variant.VariantID); err != nil {
				return manifest, fmt.Errorf("group1 template %s variant[%d]: %w", template.TemplateID, variantIndex, err)
			}
			if _, exists := seenVariants[variant.VariantID]; exists {
				return manifest, fmt.Errorf("duplicate group1 variant_id under %s: %s", template.TemplateID, variant.VariantID)
			}
			seenVariants[variant.VariantID] = struct{}{}
		}
	}

	return manifest, nil
}

func splitManifestField(line string) (string, string, error) {
	parts := strings.SplitN(line, ":", 2)
	if len(parts) != 2 {
		return "", "", fmt.Errorf("expected key: value")
	}
	key := strings.TrimSpace(parts[0])
	value := strings.Trim(strings.TrimSpace(parts[1]), "\"'")
	if key == "" || value == "" {
		return "", "", fmt.Errorf("expected non-empty key and value")
	}
	return key, value, nil
}

func assignCatalogEntryField(entry *CatalogEntry, key string, value string) error {
	switch key {
	case "id":
		parsed, err := strconv.Atoi(value)
		if err != nil {
			return err
		}
		entry.ID = parsed
	case "name":
		entry.Name = value
	case "zh_name":
		entry.ZhName = value
	default:
		return fmt.Errorf("unsupported key: %s", key)
	}
	return nil
}

func assignGroup1TemplateField(entry *Group1TemplateEntry, key string, value string) error {
	switch key {
	case "template_id":
		entry.TemplateID = value
	case "zh_name":
		entry.ZhName = value
	case "family":
		entry.Family = value
	case "tags":
		parsed, err := parseInlineList(value)
		if err != nil {
			return err
		}
		entry.Tags = parsed
	case "status":
		entry.Status = value
	default:
		return fmt.Errorf("unsupported template key: %s", key)
	}
	return nil
}

func assignGroup1VariantField(entry *Group1VariantEntry, key string, value string) error {
	switch key {
	case "variant_id":
		entry.VariantID = value
	case "source":
		entry.Source = value
	case "source_ref":
		entry.SourceRef = value
	case "style":
		entry.Style = value
	default:
		return fmt.Errorf("unsupported variant key: %s", key)
	}
	return nil
}

func parseInlineList(value string) ([]string, error) {
	value = strings.TrimSpace(value)
	if value == "[]" {
		return nil, nil
	}
	if !strings.HasPrefix(value, "[") || !strings.HasSuffix(value, "]") {
		return nil, fmt.Errorf("expected inline list like [a, b]")
	}
	inner := strings.TrimSpace(value[1 : len(value)-1])
	if inner == "" {
		return nil, nil
	}
	parts := strings.Split(inner, ",")
	values := make([]string, 0, len(parts))
	for _, part := range parts {
		item := strings.Trim(strings.TrimSpace(part), "\"'")
		if item == "" {
			return nil, fmt.Errorf("inline list contains empty item")
		}
		values = append(values, item)
	}
	return values, nil
}

func validateGroup1ID(kind string, value string) error {
	value = strings.TrimSpace(value)
	if value == "" {
		return fmt.Errorf("%s is required", kind)
	}
	if strings.ContainsAny(value, "/\\") {
		return fmt.Errorf("%s must not contain path separators: %s", kind, value)
	}
	if filepath.Ext(value) != "" {
		return fmt.Errorf("%s must not include a file extension: %s", kind, value)
	}
	return nil
}
