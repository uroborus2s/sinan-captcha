package slide

import (
	"fmt"
	"image"
	"image/color"
	"image/draw"
	_ "image/jpeg"
	_ "image/png"
	"math"
	"math/rand"
	"os"
	"path/filepath"

	"sinan-captcha/generator/internal/config"
	"sinan-captcha/generator/internal/export"
	"sinan-captcha/generator/internal/imagefx"
	"sinan-captcha/generator/internal/material"
)

var (
	gapFillColor   = color.RGBA{242, 246, 250, 220}
	gapStrokeColor = color.RGBA{174, 186, 198, 255}
	tileStroke     = color.RGBA{71, 86, 104, 255}
)

func Generate(index int, cfg config.Config, catalog material.Catalog) (export.SampleRecord, map[string]image.Image, error) {
	if len(catalog.Backgrounds) == 0 {
		return export.SampleRecord{}, nil, fmt.Errorf("material catalog has no backgrounds")
	}

	sampleSeed := cfg.Project.Seed + int64(index)
	rng := rand.New(rand.NewSource(sampleSeed))
	sampleID := fmt.Sprintf("g2_%06d", index+1)
	background := catalog.Backgrounds[rng.Intn(len(catalog.Backgrounds))]
	shapeClass, shapeIcon, err := selectShapeAsset(catalog, rng)
	if err != nil {
		return export.SampleRecord{}, nil, err
	}

	sceneSource, err := loadImage(background.Path)
	if err != nil {
		return export.SampleRecord{}, nil, err
	}
	scene := coverResize(sceneSource, cfg.Canvas.SceneWidth, cfg.Canvas.SceneHeight)
	backgroundBlurRadius := imagefx.IntRange(rng, cfg.Effects.Common.BackgroundBlurRadiusMin, cfg.Effects.Common.BackgroundBlurRadiusMax)
	if backgroundBlurRadius > 0 {
		scene = imagefx.BlurRGBA(scene, backgroundBlurRadius)
	}
	imagefx.ApplySceneVeil(scene, cfg.Effects.Common.SceneVeilStrength)

	gapWidth := clampGapDimension(cfg.Slide.GapWidth, cfg.Canvas.SceneWidth, 52)
	gapHeight := clampGapDimension(cfg.Slide.GapHeight, cfg.Canvas.SceneHeight, 52)
	maxJitterY := cfg.Slide.MaxVerticalJitter
	if maxJitterY == 0 {
		maxJitterY = 4
	}

	xMin := max(12, cfg.Canvas.SceneWidth/3)
	xMax := cfg.Canvas.SceneWidth - gapWidth - 12
	if xMax <= xMin {
		xMin = 12
		xMax = cfg.Canvas.SceneWidth - gapWidth - 12
	}
	if xMax <= xMin {
		return export.SampleRecord{}, nil, fmt.Errorf("scene canvas is too small for slide gap")
	}

	baseY := (cfg.Canvas.SceneHeight - gapHeight) / 2
	yMin := 8
	yMax := cfg.Canvas.SceneHeight - gapHeight - 8
	if yMax <= yMin {
		yMin = 0
		yMax = cfg.Canvas.SceneHeight - gapHeight
	}
	if yMax < yMin {
		return export.SampleRecord{}, nil, fmt.Errorf("scene canvas is too small for slide gap height")
	}

	gapX := xMin + rng.Intn(xMax-xMin+1)
	gapY := clamp(baseY+signedBetween(rng, maxJitterY), yMin, yMax)
	gapBBox := [4]int{gapX, gapY, gapX + gapWidth, gapY + gapHeight}
	tileBBox := [4]int{0, gapY, gapWidth, gapY + gapHeight}

	iconMaskSource, err := loadImage(shapeIcon.Path)
	if err != nil {
		return export.SampleRecord{}, nil, err
	}
	iconMask := resizeNearest(iconMaskSource, gapWidth, gapHeight)
	tile := cropMasked(scene, iconMask, image.Rect(gapBBox[0], gapBBox[1], gapBBox[2], gapBBox[3]))
	drawMaskedStroke(tile, iconMask, image.Point{}, tileStroke)
	tileBlurRadius := imagefx.IntRange(rng, cfg.Effects.Slide.TileEdgeBlurRadiusMin, cfg.Effects.Slide.TileEdgeBlurRadiusMax)
	if tileBlurRadius > 0 {
		tile = imagefx.BlurRGBA(tile, tileBlurRadius)
	}
	master := cloneRGBA(scene)
	gapShadowAlpha := imagefx.FloatRange(rng, cfg.Effects.Slide.GapShadowAlphaMin, cfg.Effects.Slide.GapShadowAlphaMax)
	if gapShadowAlpha > 0 {
		shadowOffsetX := imagefx.IntRange(rng, cfg.Effects.Slide.GapShadowOffsetXMin, cfg.Effects.Slide.GapShadowOffsetXMax)
		shadowOffsetY := imagefx.IntRange(rng, cfg.Effects.Slide.GapShadowOffsetYMin, cfg.Effects.Slide.GapShadowOffsetYMax)
		drawGapShadow(master, iconMask, gapBBox, shadowOffsetX, shadowOffsetY, gapShadowAlpha)
	}
	carveGap(master, iconMask, gapBBox)

	center := [2]int{gapBBox[0] + gapWidth/2, gapBBox[1] + gapHeight/2}
	offsetX := gapBBox[0] - tileBBox[0]
	offsetY := gapBBox[1] - tileBBox[1]
	record := export.SampleRecord{
		SampleID:     sampleID,
		CaptchaType:  "group2_slider_gap_locate",
		Mode:         "slide",
		Backend:      "native",
		MasterImage:  filepath.ToSlash(filepath.Join("master", sampleID+".png")),
		TileImage:    filepath.ToSlash(filepath.Join("tile", sampleID+".png")),
		TargetGap:    &export.ObjectRecord{Class: "slider_gap", ClassID: 0, BBox: gapBBox, Center: center},
		TileBBox:     &tileBBox,
		OffsetX:      &offsetX,
		OffsetY:      &offsetY,
		BackgroundID: background.ID,
		StyleID:      shapeClass.Name,
		LabelSource:  "gold",
		SourceBatch:  cfg.Project.BatchID,
		Seed:         sampleSeed,
	}

	return record, map[string]image.Image{
		record.MasterImage: master,
		record.TileImage:   tile,
	}, nil
}

func carveGap(img *image.RGBA, mask *image.RGBA, bbox [4]int) {
	for y := 0; y < mask.Bounds().Dy(); y++ {
		for x := 0; x < mask.Bounds().Dx(); x++ {
			if mask.RGBAAt(x, y).A == 0 {
				continue
			}
			absoluteX := bbox[0] + x
			absoluteY := bbox[1] + y
			base := img.RGBAAt(absoluteX, absoluteY)
			img.SetRGBA(absoluteX, absoluteY, color.RGBA{
				R: blend(base.R, gapFillColor.R, gapFillColor.A),
				G: blend(base.G, gapFillColor.G, gapFillColor.A),
				B: blend(base.B, gapFillColor.B, gapFillColor.A),
				A: 255,
			})
		}
	}
	drawMaskedStroke(img, mask, image.Point{X: bbox[0], Y: bbox[1]}, gapStrokeColor)
}

func drawGapShadow(img *image.RGBA, mask *image.RGBA, bbox [4]int, offsetX int, offsetY int, alphaFactor float64) {
	if alphaFactor <= 0 {
		return
	}

	alpha := uint8(clamp(int(math.Round(alphaFactor*255)), 0, 255))
	bounds := img.Bounds()
	for y := 0; y < mask.Bounds().Dy(); y++ {
		for x := 0; x < mask.Bounds().Dx(); x++ {
			if mask.RGBAAt(x, y).A == 0 {
				continue
			}
			absoluteX := bbox[0] + x + offsetX
			absoluteY := bbox[1] + y + offsetY
			if absoluteX < bounds.Min.X || absoluteX >= bounds.Max.X || absoluteY < bounds.Min.Y || absoluteY >= bounds.Max.Y {
				continue
			}
			base := img.RGBAAt(absoluteX, absoluteY)
			img.SetRGBA(absoluteX, absoluteY, color.RGBA{
				R: blend(base.R, 8, alpha),
				G: blend(base.G, 12, alpha),
				B: blend(base.B, 16, alpha),
				A: 255,
			})
		}
	}
}

func drawMaskedStroke(img *image.RGBA, mask *image.RGBA, origin image.Point, stroke color.RGBA) {
	for y := 0; y < mask.Bounds().Dy(); y++ {
		for x := 0; x < mask.Bounds().Dx(); x++ {
			if !isMaskBoundary(mask, x, y) {
				continue
			}
			img.SetRGBA(origin.X+x, origin.Y+y, stroke)
		}
	}
}

func cloneRGBA(src *image.RGBA) *image.RGBA {
	cloned := image.NewRGBA(src.Bounds())
	draw.Draw(cloned, cloned.Bounds(), src, src.Bounds().Min, draw.Src)
	return cloned
}

func crop(src *image.RGBA, rect image.Rectangle) *image.RGBA {
	dst := image.NewRGBA(image.Rect(0, 0, rect.Dx(), rect.Dy()))
	draw.Draw(dst, dst.Bounds(), src, rect.Min, draw.Src)
	return dst
}

func cropMasked(src *image.RGBA, mask *image.RGBA, rect image.Rectangle) *image.RGBA {
	dst := image.NewRGBA(image.Rect(0, 0, rect.Dx(), rect.Dy()))
	for y := 0; y < rect.Dy(); y++ {
		for x := 0; x < rect.Dx(); x++ {
			if mask.RGBAAt(x, y).A == 0 {
				continue
			}
			dst.SetRGBA(x, y, src.RGBAAt(rect.Min.X+x, rect.Min.Y+y))
		}
	}
	return dst
}

func blend(base uint8, overlay uint8, alpha uint8) uint8 {
	opacity := float64(alpha) / 255
	return uint8(clamp(int(math.Round(float64(base)*(1-opacity)+float64(overlay)*opacity)), 0, 255))
}

func signedBetween(rng *rand.Rand, magnitude int) int {
	if magnitude <= 0 {
		return 0
	}
	return rng.Intn(magnitude*2+1) - magnitude
}

func clampGapDimension(value int, canvas int, fallback int) int {
	if value <= 0 {
		value = fallback
	}
	maxAllowed := max(18, canvas-24)
	return clamp(value, 18, maxAllowed)
}

func selectShapeAsset(catalog material.Catalog, rng *rand.Rand) (material.ClassAssets, material.IconAsset, error) {
	candidates := make([]material.ClassAssets, 0, len(catalog.Classes))
	for _, classAssets := range catalog.Classes {
		if len(classAssets.Icons) == 0 {
			continue
		}
		candidates = append(candidates, classAssets)
	}
	if len(candidates) == 0 {
		return material.ClassAssets{}, material.IconAsset{}, fmt.Errorf("material catalog has no icon masks for slide mode")
	}

	selectedClass := candidates[rng.Intn(len(candidates))]
	selectedIcon := selectedClass.Icons[rng.Intn(len(selectedClass.Icons))]
	return selectedClass, selectedIcon, nil
}

func loadImage(path string) (image.Image, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	img, _, err := image.Decode(file)
	if err != nil {
		return nil, err
	}
	return img, nil
}

func coverResize(src image.Image, width int, height int) *image.RGBA {
	srcBounds := src.Bounds()
	scale := math.Max(float64(width)/float64(srcBounds.Dx()), float64(height)/float64(srcBounds.Dy()))
	scaledWidth := max(width, int(math.Ceil(float64(srcBounds.Dx())*scale)))
	scaledHeight := max(height, int(math.Ceil(float64(srcBounds.Dy())*scale)))
	scaled := resizeNearest(src, scaledWidth, scaledHeight)
	offsetX := (scaledWidth - width) / 2
	offsetY := (scaledHeight - height) / 2
	dst := image.NewRGBA(image.Rect(0, 0, width, height))
	draw.Draw(dst, dst.Bounds(), scaled, image.Point{X: offsetX, Y: offsetY}, draw.Src)
	return dst
}

func resizeNearest(src image.Image, width int, height int) *image.RGBA {
	srcBounds := src.Bounds()
	dst := image.NewRGBA(image.Rect(0, 0, width, height))
	scaleX := float64(srcBounds.Dx()) / float64(width)
	scaleY := float64(srcBounds.Dy()) / float64(height)
	for y := 0; y < height; y++ {
		sourceY := srcBounds.Min.Y + min(int(math.Floor(float64(y)*scaleY)), srcBounds.Dy()-1)
		for x := 0; x < width; x++ {
			sourceX := srcBounds.Min.X + min(int(math.Floor(float64(x)*scaleX)), srcBounds.Dx()-1)
			dst.Set(x, y, src.At(sourceX, sourceY))
		}
	}
	return dst
}

func isMaskBoundary(mask *image.RGBA, x int, y int) bool {
	if mask.RGBAAt(x, y).A == 0 {
		return false
	}
	for _, delta := range [][2]int{{-1, 0}, {1, 0}, {0, -1}, {0, 1}} {
		nx := x + delta[0]
		ny := y + delta[1]
		if nx < 0 || ny < 0 || nx >= mask.Bounds().Dx() || ny >= mask.Bounds().Dy() {
			return true
		}
		if mask.RGBAAt(nx, ny).A == 0 {
			return true
		}
	}
	return false
}

func clamp(value int, lower int, upper int) int {
	if value < lower {
		return lower
	}
	if value > upper {
		return upper
	}
	return value
}

func min(left int, right int) int {
	if left < right {
		return left
	}
	return right
}

func max(left int, right int) int {
	if left > right {
		return left
	}
	return right
}
