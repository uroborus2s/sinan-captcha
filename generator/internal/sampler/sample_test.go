package sampler

import "testing"

func TestRotatedBoundsExpandForDiagonalAngles(t *testing.T) {
	size := rotatedBounds(40, 20, 15)
	if size.Width <= 40 {
		t.Fatalf("expected rotated width to grow, got %d", size.Width)
	}
	if size.Height <= 20 {
		t.Fatalf("expected rotated height to grow, got %d", size.Height)
	}
}

func TestRotatedBoundsKeepsIdentityAtZeroDegrees(t *testing.T) {
	size := rotatedBounds(40, 20, 0)
	if size.Width != 40 || size.Height != 20 {
		t.Fatalf("expected identity bounds, got %+v", size)
	}
}
