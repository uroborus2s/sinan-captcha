package imagefx

import (
	"image"
	"image/color"
	"math"
	"math/rand"
)

func ApplySceneVeil(img *image.RGBA, strength float64) {
	if img == nil || strength <= 0 {
		return
	}

	bounds := img.Bounds()
	redFactor := 1 - 0.07*strength
	greenFactor := 1 - 0.06*strength
	blueFactor := 1 - 0.03*strength
	blueBoost := int(math.Round(4 * strength))

	for y := bounds.Min.Y; y < bounds.Max.Y; y++ {
		for x := bounds.Min.X; x < bounds.Max.X; x++ {
			red, green, blue, alpha := img.At(x, y).RGBA()
			coolLift := int(math.Round(float64((x+y)%9) * strength))
			img.SetRGBA(x, y, color.RGBA{
				R: uint8(clampInt(int(math.Round(float64(red>>8)*redFactor))+coolLift, 0, 255)),
				G: uint8(clampInt(int(math.Round(float64(green>>8)*greenFactor))+coolLift, 0, 255)),
				B: uint8(clampInt(int(math.Round(float64(blue>>8)*blueFactor))+coolLift+blueBoost, 0, 255)),
				A: uint8(alpha >> 8),
			})
		}
	}
}

func BlurRGBA(src *image.RGBA, radius int) *image.RGBA {
	if src == nil || radius <= 0 {
		return src
	}

	current := cloneRGBA(src)
	for pass := 0; pass < radius; pass++ {
		current = boxBlurRGBA(current)
	}
	return current
}

func ShadowSprite(src *image.RGBA, alphaFactor float64) *image.RGBA {
	if src == nil || alphaFactor <= 0 {
		return image.NewRGBA(image.Rect(0, 0, 0, 0))
	}

	dst := image.NewRGBA(src.Bounds())
	for y := 0; y < src.Bounds().Dy(); y++ {
		for x := 0; x < src.Bounds().Dx(); x++ {
			_, _, _, alpha := src.At(x, y).RGBA()
			if alpha == 0 {
				continue
			}
			dst.SetRGBA(x, y, color.RGBA{
				R: 8,
				G: 12,
				B: 16,
				A: uint8(clampInt(int(math.Round(float64(alpha>>8)*alphaFactor)), 0, 255)),
			})
		}
	}
	return dst
}

func IntRange(rng *rand.Rand, minValue int, maxValue int) int {
	if maxValue <= minValue {
		return minValue
	}
	return minValue + rng.Intn(maxValue-minValue+1)
}

func FloatRange(rng *rand.Rand, minValue float64, maxValue float64) float64 {
	if maxValue <= minValue {
		return minValue
	}
	return minValue + rng.Float64()*(maxValue-minValue)
}

func boxBlurRGBA(src *image.RGBA) *image.RGBA {
	bounds := src.Bounds()
	dst := image.NewRGBA(bounds)

	for y := bounds.Min.Y; y < bounds.Max.Y; y++ {
		for x := bounds.Min.X; x < bounds.Max.X; x++ {
			var redSum int
			var greenSum int
			var blueSum int
			var alphaSum int
			var count int

			for yy := maxInt(bounds.Min.Y, y-1); yy <= minInt(bounds.Max.Y-1, y+1); yy++ {
				for xx := maxInt(bounds.Min.X, x-1); xx <= minInt(bounds.Max.X-1, x+1); xx++ {
					pixel := src.RGBAAt(xx, yy)
					redSum += int(pixel.R)
					greenSum += int(pixel.G)
					blueSum += int(pixel.B)
					alphaSum += int(pixel.A)
					count++
				}
			}

			dst.SetRGBA(x, y, color.RGBA{
				R: uint8(redSum / count),
				G: uint8(greenSum / count),
				B: uint8(blueSum / count),
				A: uint8(alphaSum / count),
			})
		}
	}
	return dst
}

func cloneRGBA(src *image.RGBA) *image.RGBA {
	dst := image.NewRGBA(src.Bounds())
	copy(dst.Pix, src.Pix)
	return dst
}

func clampInt(value int, lower int, upper int) int {
	if value < lower {
		return lower
	}
	if value > upper {
		return upper
	}
	return value
}

func minInt(left int, right int) int {
	if left < right {
		return left
	}
	return right
}

func maxInt(left int, right int) int {
	if left > right {
		return left
	}
	return right
}
