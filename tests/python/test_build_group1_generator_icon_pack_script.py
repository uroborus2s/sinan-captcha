from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import TestCase

from PIL import Image


def _load_script_module():
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "build_group1_generator_icon_pack.py"
    )
    spec = importlib.util.spec_from_file_location("build_group1_generator_icon_pack", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BuildGroup1GeneratorIconPackScriptTest(TestCase):
    def test_selected_cluster_members_filters_by_fingerprint(self) -> None:
        module = _load_script_module()
        cluster = {
            "members": [
                {"fingerprint": "fp_a", "sample_id": "a"},
                {"fingerprint": "fp_b", "sample_id": "b"},
                {"fingerprint": "fp_a", "sample_id": "c"},
            ]
        }

        actual = module.selected_cluster_members(
            {"member_fingerprints": ["fp_a"]},
            cluster,
        )

        self.assertEqual([member["sample_id"] for member in actual], ["a", "c"])

    def test_old_manifest_entries_discovers_legacy_icon_dirs(self) -> None:
        module = _load_script_module()
        root = Path(self.id().replace(".", "_"))
        (root / "icon_house").mkdir(parents=True, exist_ok=True)
        (root / "icon_house" / "001.png").write_bytes(b"fake")
        (root / "icon_bell").mkdir(parents=True, exist_ok=True)
        (root / "icon_bell" / "001.png").write_bytes(b"fake")
        try:
            actual = module.old_manifest_entries(root)
            names = [entry["class_name"] for entry in actual]
            self.assertEqual(names, ["icon_bell", "icon_house"])
        finally:
            for path in sorted(root.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()

    def test_normalize_icon_png_removes_white_background_and_keeps_foreground(self) -> None:
        module = _load_script_module()
        img = Image.new("RGBA", (8, 8), (255, 255, 255, 255))
        for y in range(2, 6):
            for x in range(3, 5):
                img.putpixel((x, y), (0, 0, 0, 255))

        actual = module.normalize_icon_png(img)

        self.assertLess(actual.size[0], 8 + 16)
        self.assertLess(actual.size[1], 8 + 16)
        alpha = actual.getchannel("A")
        self.assertEqual(alpha.getbbox() is not None, True)
        self.assertEqual(actual.getpixel((0, 0))[3], 0)

    def test_extract_member_icon_crops_bbox_and_normalizes_background(self) -> None:
        module = _load_script_module()
        root = Path(self.id().replace(".", "_"))
        root.mkdir(exist_ok=True)
        try:
            source = root / "source.png"
            img = Image.new("RGBA", (20, 20), (255, 255, 255, 255))
            for y in range(5, 15):
                for x in range(7, 13):
                    img.putpixel((x, y), (10, 20, 30, 255))
            img.save(source)

            actual = module.extract_member_icon(source_path=source, bbox=[5, 4, 15, 16])

            self.assertTrue(actual.size[0] > 0)
            self.assertTrue(actual.size[1] > 0)
            self.assertEqual(actual.getpixel((0, 0))[3], 0)
            self.assertIsNotNone(actual.getchannel("A").getbbox())
        finally:
            if root.exists():
                for path in sorted(root.glob("*"), reverse=True):
                    path.unlink()
                root.rmdir()
