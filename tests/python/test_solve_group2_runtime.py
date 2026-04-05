from __future__ import annotations

import inspect
import unittest

from core.solve import group2_runtime


class SolveGroup2RuntimeTests(unittest.TestCase):
    def test_runtime_module_does_not_depend_on_training_runner(self) -> None:
        source = inspect.getsource(group2_runtime)
        self.assertNotIn("core.train.group2.runner", source)

    def test_bbox_center_uses_center_coordinates(self) -> None:
        self.assertEqual(group2_runtime.bbox_center([80, 24, 120, 64]), [100, 44])


if __name__ == "__main__":
    unittest.main()
