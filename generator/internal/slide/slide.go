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

	sceneSource, err := loadImage(background.Path)
	if err != nil {
		return export.SampleRecord{}, nil, err
	}
	scene := coverResize(sceneSource, cfg.Canvas.SceneWidth, cfg.Canvas.SceneHeight)
	applySceneVeil(scene)

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

	tile := crop(scene, image.Rect(gapBBox[0], gapBBox[1], gapBBox[2], gapBBox[3]))
	drawBorder(tile, tileStroke)
	master := cloneRGBA(scene)
	carveGap(master, gapBBox)

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
		StyleID:      "default",
		LabelSource:  "gold",
		SourceBatch:  cfg.Project.BatchID,
		Seed:         sampleSeed,
	}

	return record, map[string]image.Image{
		record.MasterImage: master,
		record.TileImage:   tile,
	}, nil
}

func carveGap(img *image.RGBA, bbox [4]int) {
	x1, y1, x2, y2 := bbox[0], bbox[1], bbox[2], bbox[3]
	for y := y1; y < y2; y++ {
		for x := x1; x < x2; x++ {
			base := img.RGBAAt(x, y)
			img.SetRGBA(x, y, color.RGBA{
				R: blend(base.R, gapFillColor.R, gapFillColor.A),
				G: blend(base.G, gapFillColor.G, gapFillColor.A),
				B: blend(base.B, gapFillColor.B, gapFillColor.A),
				A: 255,
			})
		}
	}
	drawRectStroke(img, x1, y1, x2, y2, gapStrokeColor)
}

func drawRectStroke(img *image.RGBA, x1 int, y1 int, x2 int, y2 int, stroke color.RGBA) {
	for x := x1; x < x2; x++ {
		img.SetRGBA(x, y1, stroke)
		img.SetRGBA(x, y2-1, stroke)
	}
	for y := y1; y < y2; y++ {
		img.SetRGBA(x1, y, stroke)
		img.SetRGBA(x2-1, y, stroke)
	}
}

func drawBorder(img *image.RGBA, stroke color.RGBA) {
	bounds := img.Bounds()
	for x := bounds.Min.X; x < bounds.Max.X; x++ {
		img.SetRGBA(x, bounds.Min.Y, stroke)
		img.SetRGBA(x, bounds.Max.Y-1, stroke)
	}
	for y := bounds.Min.Y; y < bounds.Max.Y; y++ {
		img.SetRGBA(bounds.Min.X, y, stroke)
		img.SetRGBA(bounds.Max.X-1, y, stroke)
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

func applySceneVeil(img *image.RGBA) {
	bounds := img.Bounds()
	for x := bounds.Min.X; x < bounds.Max.X; x++ {
		for y := bounds.Min.Y; y < bounds.Max.Y; y++ {
			red, green, blue, alpha := img.At(x, y).RGBA()
			coolLift := uint8(clamp(int((x+y)%9), 0, 10))
			img.SetRGBA(x, y, color.RGBA{
				R: uint8(clamp(int((red>>8)*93/100)+int(coolLift), 0, 255)),
				G: uint8(clamp(int((green>>8)*94/100)+int(coolLift), 0, 255)),
				B: uint8(clamp(int((blue>>8)*97/100)+int(coolLift)+4, 0, 255)),
				A: uint8(alpha >> 8),
			})
		}
	}
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
