package render

import (
	"image"
	"image/color"
	"image/draw"
	_ "image/jpeg"
	_ "image/png"
	"math"
	"math/rand"
	"os"

	"sinan-captcha/generator/internal/config"
	"sinan-captcha/generator/internal/export"
	"sinan-captcha/generator/internal/imagefx"
	"sinan-captcha/generator/internal/sampler"
)

var (
	queryOuterBackground = color.RGBA{236, 240, 245, 255}
	queryPanelBackground = color.RGBA{248, 250, 252, 255}
	queryBorder          = color.RGBA{214, 221, 230, 255}
	queryDivider         = color.RGBA{228, 233, 240, 255}
	iconTint             = color.RGBA{26, 40, 58, 255}
)

const (
	queryIconScaleMin = 0.78
	queryIconScaleMax = 0.90
	queryIconAlphaMin = 0.88
	queryIconAlphaMax = 0.98
	queryIconJitterX  = 1
	queryIconJitterY  = 1
)

func Build(plan sampler.SamplePlan, cfg config.Config) (image.Image, image.Image, []export.ObjectRecord, error) {
	scene, err := buildScene(plan, cfg)
	if err != nil {
		return nil, nil, nil, err
	}
	query, queryTargets, err := buildQuery(plan, cfg)
	if err != nil {
		return nil, nil, nil, err
	}
	return query, scene, queryTargets, nil
}

func buildScene(plan sampler.SamplePlan, cfg config.Config) (image.Image, error) {
	canvas := cfg.Canvas
	background, err := loadImage(plan.BackgroundPath)
	if err != nil {
		return nil, err
	}
	scene := coverResize(background, canvas.SceneWidth, canvas.SceneHeight)
	rng := rand.New(rand.NewSource(plan.Record.Seed))
	backgroundBlurRadius := imagefx.IntRange(rng, cfg.Effects.Common.BackgroundBlurRadiusMin, cfg.Effects.Common.BackgroundBlurRadiusMax)
	if backgroundBlurRadius > 0 {
		scene = imagefx.BlurRGBA(scene, backgroundBlurRadius)
	}
	imagefx.ApplySceneVeil(scene, cfg.Effects.Common.SceneVeilStrength)

	for _, object := range append(append([]sampler.PlacedObject{}, plan.Targets...), plan.Distractors...) {
		icon, err := loadImage(object.IconPath)
		if err != nil {
			return nil, err
		}
		sprite := tintAndResize(icon, object.BaseWidth, object.BaseHeight, object.Alpha)
		rotatedSprite := rotateRGBA(sprite, object.RotationDeg)
		iconBlurRadius := imagefx.IntRange(rng, cfg.Effects.Click.IconEdgeBlurRadiusMin, cfg.Effects.Click.IconEdgeBlurRadiusMax)
		if iconBlurRadius > 0 {
			rotatedSprite = imagefx.BlurRGBA(rotatedSprite, iconBlurRadius)
		}

		shadowAlpha := imagefx.FloatRange(rng, cfg.Effects.Click.IconShadowAlphaMin, cfg.Effects.Click.IconShadowAlphaMax)
		if shadowAlpha > 0 {
			shadow := imagefx.ShadowSprite(rotatedSprite, shadowAlpha)
			shadowOffsetX := imagefx.IntRange(rng, cfg.Effects.Click.IconShadowOffsetXMin, cfg.Effects.Click.IconShadowOffsetXMax)
			shadowOffsetY := imagefx.IntRange(rng, cfg.Effects.Click.IconShadowOffsetYMin, cfg.Effects.Click.IconShadowOffsetYMax)
			shadowPoint := image.Point{X: object.BBox[0] + shadowOffsetX, Y: object.BBox[1] + shadowOffsetY}
			shadowRect := image.Rectangle{Min: shadowPoint, Max: shadowPoint.Add(shadow.Bounds().Size())}
			draw.Draw(scene, shadowRect, shadow, image.Point{}, draw.Over)
		}

		spritePoint := image.Point{X: object.BBox[0], Y: object.BBox[1]}
		spriteRect := image.Rectangle{Min: spritePoint, Max: spritePoint.Add(rotatedSprite.Bounds().Size())}
		draw.Draw(scene, spriteRect, rotatedSprite, image.Point{}, draw.Over)
	}
	return scene, nil
}

func buildQuery(plan sampler.SamplePlan, cfg config.Config) (image.Image, []export.ObjectRecord, error) {
	canvas := cfg.Canvas
	query := image.NewRGBA(image.Rect(0, 0, canvas.QueryWidth, canvas.QueryHeight))
	draw.Draw(query, query.Bounds(), &image.Uniform{C: queryOuterBackground}, image.Point{}, draw.Src)
	drawPanel(query)

	if len(plan.Targets) == 0 {
		return query, nil, nil
	}

	padding := 8
	availableWidth := canvas.QueryWidth - padding*(len(plan.Targets)+1)
	cellWidth := max(16, availableWidth/len(plan.Targets))
	cellHeight := canvas.QueryHeight - padding*2 - 2
	queryTargets := make([]export.ObjectRecord, 0, len(plan.Targets))
	rng := rand.New(rand.NewSource(plan.Record.Seed + 17))

	for index, object := range plan.Targets {
		icon, err := loadImage(object.IconPath)
		if err != nil {
			return nil, nil, err
		}
		srcBounds := icon.Bounds()
		scale := math.Min(float64(cellWidth)/float64(srcBounds.Dx()), float64(cellHeight)/float64(srcBounds.Dy()))
		scale *= imagefx.FloatRange(rng, queryIconScaleMin, queryIconScaleMax)
		iconWidth := max(12, int(math.Round(float64(srcBounds.Dx())*scale)))
		iconHeight := max(12, int(math.Round(float64(srcBounds.Dy())*scale)))
		sprite := tintAndResize(icon, iconWidth, iconHeight, imagefx.FloatRange(rng, queryIconAlphaMin, queryIconAlphaMax))
		queryBlurRadius := imagefx.IntRange(rng, cfg.Effects.Click.IconEdgeBlurRadiusMin, cfg.Effects.Click.IconEdgeBlurRadiusMax)
		if queryBlurRadius > 0 {
			sprite = imagefx.BlurRGBA(sprite, queryBlurRadius)
		}

		cellX1 := padding + index*(cellWidth+padding)
		cellX2 := cellX1 + cellWidth
		x1 := cellX1 + (cellWidth-iconWidth)/2 + imagefx.IntRange(rng, -queryIconJitterX, queryIconJitterX)
		x1 = clamp(x1, cellX1, cellX2-iconWidth)
		yMin := padding + 1
		yMax := yMin + cellHeight - iconHeight
		y1 := yMin + (cellHeight-iconHeight)/2 + imagefx.IntRange(rng, -queryIconJitterY, queryIconJitterY)
		y1 = clamp(y1, yMin, yMax)
		rect := image.Rect(x1, y1, x1+iconWidth, y1+iconHeight)
		draw.Draw(query, rect, sprite, image.Point{}, draw.Over)
		order := object.Order
		if order == 0 {
			order = index + 1
		}
		queryTargets = append(queryTargets, export.ObjectRecord{
			Order:       order,
			Class:       object.Class,
			ClassID:     object.ClassID,
			BBox:        [4]int{rect.Min.X, rect.Min.Y, rect.Max.X, rect.Max.Y},
			Center:      [2]int{rect.Min.X + rect.Dx()/2, rect.Min.Y + rect.Dy()/2},
			RotationDeg: 0,
			Alpha:       1,
			Scale:       math.Round(scale*100) / 100,
		})
		if index < len(plan.Targets)-1 {
			dividerX := cellX1 + cellWidth + padding/2
			for y := 8; y < canvas.QueryHeight-8; y++ {
				query.SetRGBA(dividerX, y, queryDivider)
			}
		}
	}
	queryArtifactStrength := 0.28 + maxFloat(0, cfg.Effects.Common.SceneVeilStrength-1.0)*0.65
	if cfg.Effects.Click.IconEdgeBlurRadiusMax > 0 {
		queryArtifactStrength += 0.18
	}
	imagefx.ApplyQueryArtifacts(query, plan.Record.Seed+31, minFloat(queryArtifactStrength, 0.85))
	return query, queryTargets, nil
}

func drawPanel(img *image.RGBA) {
	bounds := img.Bounds()
	panel := image.Rect(2, 2, bounds.Max.X-2, bounds.Max.Y-2)
	draw.Draw(img, panel, &image.Uniform{C: queryPanelBackground}, image.Point{}, draw.Src)
	for x := panel.Min.X; x < panel.Max.X; x++ {
		img.SetRGBA(x, panel.Min.Y, queryBorder)
		img.SetRGBA(x, panel.Max.Y-1, queryBorder)
	}
	for y := panel.Min.Y; y < panel.Max.Y; y++ {
		img.SetRGBA(panel.Min.X, y, queryBorder)
		img.SetRGBA(panel.Max.X-1, y, queryBorder)
	}

	for x := 4; x < bounds.Max.X-4; x++ {
		img.SetRGBA(x, 3, color.RGBA{255, 255, 255, 100})
	}
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

func tintAndResize(src image.Image, width int, height int, alphaFactor float64) *image.RGBA {
	resized := resizeNearest(src, width, height)
	dst := image.NewRGBA(resized.Bounds())
	for y := 0; y < resized.Bounds().Dy(); y++ {
		for x := 0; x < resized.Bounds().Dx(); x++ {
			_, _, _, a := resized.At(x, y).RGBA()
			if a == 0 {
				continue
			}
			alpha := uint8(clamp(int(math.Round(float64(a>>8)*alphaFactor)), 0, 255))
			dst.SetRGBA(x, y, color.RGBA{
				R: iconTint.R,
				G: iconTint.G,
				B: iconTint.B,
				A: alpha,
			})
		}
	}
	return dst
}

func rotateRGBA(src *image.RGBA, degrees float64) *image.RGBA {
	if math.Abs(degrees) < 0.05 {
		return src
	}

	dstWidth, dstHeight := rotatedBounds(src.Bounds().Dx(), src.Bounds().Dy(), degrees)
	dst := image.NewRGBA(image.Rect(0, 0, dstWidth, dstHeight))
	radians := degrees * math.Pi / 180
	sinValue := math.Sin(-radians)
	cosValue := math.Cos(-radians)
	srcCenterX := float64(src.Bounds().Dx()) / 2
	srcCenterY := float64(src.Bounds().Dy()) / 2
	dstCenterX := float64(dstWidth) / 2
	dstCenterY := float64(dstHeight) / 2

	for y := 0; y < dstHeight; y++ {
		translatedY := float64(y) + 0.5 - dstCenterY
		for x := 0; x < dstWidth; x++ {
			translatedX := float64(x) + 0.5 - dstCenterX
			sourceX := translatedX*cosValue - translatedY*sinValue + srcCenterX - 0.5
			sourceY := translatedX*sinValue + translatedY*cosValue + srcCenterY - 0.5
			if sourceX < 0 || sourceY < 0 || sourceX >= float64(src.Bounds().Dx()) || sourceY >= float64(src.Bounds().Dy()) {
				continue
			}
			pixel := src.RGBAAt(min(int(math.Round(sourceX)), src.Bounds().Dx()-1), min(int(math.Round(sourceY)), src.Bounds().Dy()-1))
			if pixel.A == 0 {
				continue
			}
			dst.SetRGBA(x, y, pixel)
		}
	}
	return dst
}

func rotatedBounds(width int, height int, degrees float64) (int, int) {
	if degrees == 0 {
		return width, height
	}
	radians := math.Abs(degrees) * math.Pi / 180
	sinValue := math.Abs(math.Sin(radians))
	cosValue := math.Abs(math.Cos(radians))
	return max(1, int(math.Ceil(float64(width)*cosValue+float64(height)*sinValue))),
		max(1, int(math.Ceil(float64(width)*sinValue+float64(height)*cosValue)))
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

func clamp(value int, minValue int, maxValue int) int {
	if value < minValue {
		return minValue
	}
	if value > maxValue {
		return maxValue
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

func maxFloat(left float64, right float64) float64 {
	if left > right {
		return left
	}
	return right
}

func minFloat(left float64, right float64) float64 {
	if left < right {
		return left
	}
	return right
}
