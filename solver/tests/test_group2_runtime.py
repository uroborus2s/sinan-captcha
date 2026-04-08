from __future__ import annotations

import unittest

from sinanz.group2 import runtime


class Group2RuntimeTest(unittest.TestCase):
    def test_decode_bbox_maps_response_index_back_to_original_space(self) -> None:
        bbox = runtime.decode_bbox(
            _FakeResponse(index=7),
            {
                "response_width": 4,
                "response_height": 4,
                "scale_x": 2.0,
                "scale_y": 2.0,
                "tile_width": 40,
                "tile_height": 20,
                "master_width": 160,
                "master_height": 120,
            },
        )

        self.assertEqual(bbox, [6, 2, 46, 22])

    def test_bbox_center_uses_target_center_coordinates(self) -> None:
        self.assertEqual(runtime.bbox_center([80, 24, 120, 64]), [100, 44])


class _FakeIndex:
    def __init__(self, value: int) -> None:
        self._value = value

    def item(self) -> int:
        return self._value


class _FakeArgMax:
    def __init__(self, value: int) -> None:
        self._value = value

    def argmax(self) -> _FakeIndex:
        return _FakeIndex(self._value)


class _FakeResponse:
    def __init__(self, index: int) -> None:
        self._index = index

    def flatten(self) -> _FakeArgMax:
        return _FakeArgMax(self._index)


if __name__ == "__main__":
    unittest.main()
