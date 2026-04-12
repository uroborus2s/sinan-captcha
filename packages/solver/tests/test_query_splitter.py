from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sinanz_query_splitter import split_query_icons


class SolverQuerySplitterTests(unittest.TestCase):
    def test_split_query_icons_returns_ordered_targets(self) -> None:
        image_module = _load_pillow()
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "query.png"
            image = image_module.new("RGBA", (120, 40), (0, 0, 0, 0))
            for x in range(8, 26):
                for y in range(8, 26):
                    image.putpixel((x, y), (15, 15, 15, 255))
            for x in range(60, 84):
                for y in range(7, 29):
                    image.putpixel((x, y), (15, 15, 15, 255))
            image.save(image_path)

            detections = split_query_icons(image_path)

        self.assertEqual([item.order for item in detections], [1, 2])
        self.assertEqual([item.center for item in detections], [(17, 17), (72, 18)])


def _load_pillow():
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise unittest.SkipTest("Pillow is required for query splitter tests") from exc
    return Image


if __name__ == "__main__":
    unittest.main()
