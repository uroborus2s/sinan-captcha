from __future__ import annotations

import inspect
import unittest

from solve import group2_runtime


class SolveGroup2RuntimeTests(unittest.TestCase):
    def test_runtime_module_does_not_depend_on_training_runner(self) -> None:
        source = inspect.getsource(group2_runtime)
        self.assertNotIn("train.group2.runner", source)

    def test_bbox_center_uses_center_coordinates(self) -> None:
        self.assertEqual(group2_runtime.bbox_center([80, 24, 120, 64]), [100, 44])

    def test_derive_alpha_grid_from_opaque_rgb_grid_uses_border_background(self) -> None:
        rgb_grid = [
            [(0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)],
            [(0, 0, 0), (20, 160, 40), (20, 160, 40), (20, 160, 40), (0, 0, 0)],
            [(0, 0, 0), (20, 160, 40), (255, 255, 255), (20, 160, 40), (0, 0, 0)],
            [(0, 0, 0), (20, 160, 40), (20, 160, 40), (20, 160, 40), (0, 0, 0)],
            [(0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)],
        ]

        alpha = group2_runtime.derive_alpha_grid_from_rgb_grid(rgb_grid)

        self.assertEqual(len(alpha), 5)
        self.assertEqual(len(alpha[0]), 5)
        self.assertLess(alpha[0][0], 0.01)
        self.assertGreater(alpha[2][2], 0.99)
        self.assertGreater(alpha[1][1], 0.99)


if __name__ == "__main__":
    unittest.main()
