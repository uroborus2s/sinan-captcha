from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from inference.query_splitter import split_group1_query_image


class Group1QuerySplitterTests(unittest.TestCase):
    def test_splitter_recovers_left_to_right_query_items_from_transparent_strip(self) -> None:
        image_module = _load_pillow()
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "query.png"
            image = image_module.new("RGBA", (120, 40), (0, 0, 0, 0))
            for x in range(10, 31):
                for y in range(8, 29):
                    image.putpixel((x, y), (20, 20, 20, 255))
            for x in range(65, 86):
                for y in range(6, 31):
                    image.putpixel((x, y), (20, 20, 20, 255))
            image.save(image_path)

            items = split_group1_query_image(image_path)

        self.assertEqual([item["order"] for item in items], [1, 2])
        self.assertEqual(items[0]["center"], [20, 18])
        self.assertEqual(items[1]["center"], [76, 18])

    def test_splitter_can_use_border_background_for_opaque_query_image(self) -> None:
        image_module = _load_pillow()
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "query_opaque.png"
            image = image_module.new("RGBA", (100, 36), (245, 245, 245, 255))
            for x in range(12, 29):
                for y in range(10, 27):
                    image.putpixel((x, y), (30, 30, 30, 255))
            for x in range(56, 77):
                for y in range(9, 28):
                    image.putpixel((x, y), (40, 40, 40, 255))
            image.save(image_path)

            items = split_group1_query_image(image_path)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["bbox"], [12, 10, 29, 27])
        self.assertEqual(items[1]["bbox"], [56, 9, 77, 28])


def _load_pillow():
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise unittest.SkipTest("Pillow is required for query splitter tests") from exc
    return Image


if __name__ == "__main__":
    unittest.main()
