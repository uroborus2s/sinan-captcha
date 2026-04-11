package layout

import (
	"fmt"
	"math"
	"math/rand"
)

type Size struct {
	Width  int
	Height int
}

type Rect struct {
	X1 int
	Y1 int
	X2 int
	Y2 int
}

func (r Rect) Width() int {
	return r.X2 - r.X1
}

func (r Rect) Height() int {
	return r.Y2 - r.Y1
}

func Place(canvasWidth int, canvasHeight int, sizes []Size, rng *rand.Rand) ([]Rect, error) {
	const margin = 6
	const maxAttempts = 240
	const maxOverlapRatio = 0.12

	placed := make([]Rect, 0, len(sizes))
	for index, size := range sizes {
		if size.Width <= 0 || size.Height <= 0 {
			return nil, fmt.Errorf("invalid size at index %d", index)
		}
		if size.Width+margin*2 > canvasWidth || size.Height+margin*2 > canvasHeight {
			return nil, fmt.Errorf("object %d does not fit canvas", index)
		}

		var candidate Rect
		success := false
		for attempt := 0; attempt < maxAttempts; attempt++ {
			x1 := margin + rng.Intn(canvasWidth-size.Width-margin*2+1)
			y1 := margin + rng.Intn(canvasHeight-size.Height-margin*2+1)
			candidate = Rect{
				X1: x1,
				Y1: y1,
				X2: x1 + size.Width,
				Y2: y1 + size.Height,
			}
			if isPlacementSafe(candidate, placed, maxOverlapRatio) {
				success = true
				break
			}
		}
		if !success {
			return nil, fmt.Errorf("could not place object %d after %d attempts", index, maxAttempts)
		}
		placed = append(placed, candidate)
	}
	return placed, nil
}

func isPlacementSafe(candidate Rect, existing []Rect, maxOverlapRatio float64) bool {
	for _, current := range existing {
		if overlapRatio(candidate, current) > maxOverlapRatio {
			return false
		}
	}
	return true
}

func overlapRatio(left Rect, right Rect) float64 {
	intersectionWidth := max(0, min(left.X2, right.X2)-max(left.X1, right.X1))
	intersectionHeight := max(0, min(left.Y2, right.Y2)-max(left.Y1, right.Y1))
	if intersectionWidth == 0 || intersectionHeight == 0 {
		return 0
	}

	intersectionArea := intersectionWidth * intersectionHeight
	smallerArea := min(left.Width()*left.Height(), right.Width()*right.Height())
	if smallerArea == 0 {
		return 0
	}
	return float64(intersectionArea) / float64(smallerArea)
}

func min(left int, right int) int {
	return int(math.Min(float64(left), float64(right)))
}

func max(left int, right int) int {
	return int(math.Max(float64(left), float64(right)))
}
