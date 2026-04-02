from __future__ import annotations

import csv
import struct
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path

from core.common.images import get_image_size
from core.materials.service import (
    BackgroundSourceConfig,
    ClassSpec,
    IconSourceConfig,
    MaterialsPackSpec,
    build_offline_pack,
    choose_best_google_icon_entry,
    load_materials_pack_spec,
)


def _write_png(path: Path, width: int, height: int, color: tuple[int, int, int]) -> None:
    raw_rows = []
    pixel = bytes(color)
    for _ in range(height):
        raw_rows.append(b"\x00" + pixel * width)
    payload = zlib.compress(b"".join(raw_rows))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack("!I", len(data))
            + kind
            + data
            + struct.pack("!I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    png = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            chunk(b"IDAT", payload),
            chunk(b"IEND", b""),
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


class MaterialsServiceTests(unittest.TestCase):
    def test_choose_best_google_icon_entry_prefers_highest_web_scale(self) -> None:
        entries = [
            "material-design-icons-main/png/communication/call/materialicons/1x_web/ic_call_black_24dp.png",
            "material-design-icons-main/png/communication/call/materialicons/2x_web/ic_call_black_24dp.png",
            "material-design-icons-main/png/communication/call/materialicons/4x_web/ic_call_black_24dp.png",
        ]

        result = choose_best_google_icon_entry(entries, "call")

        self.assertEqual(
            result,
            "material-design-icons-main/png/communication/call/materialicons/4x_web/ic_call_black_24dp.png",
        )

    def test_build_offline_pack_with_local_backgrounds_and_google_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            background_source = root / "background-source"
            _write_png(background_source / "lake.png", 1600, 900, (120, 160, 210))
            _write_png(background_source / "bridge.png", 1600, 900, (140, 180, 220))

            archive_path = root / "material-design-icons.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                low_res_phone = root / "phone-1x.png"
                high_res_phone = root / "phone-4x.png"
                satellite = root / "satellite-2x.png"
                _write_png(low_res_phone, 24, 24, (20, 20, 20))
                _write_png(high_res_phone, 96, 96, (30, 30, 30))
                _write_png(satellite, 48, 48, (40, 40, 40))
                archive.write(
                    low_res_phone,
                    "material-design-icons-main/png/communication/call/materialicons/1x_web/ic_call_black_24dp.png",
                )
                archive.write(
                    high_res_phone,
                    "material-design-icons-main/png/communication/call/materialicons/4x_web/ic_call_black_24dp.png",
                )
                archive.write(
                    satellite,
                    "material-design-icons-main/png/maps/satellite_alt/materialicons/2x_web/ic_satellite_alt_black_24dp.png",
                )

            spec = MaterialsPackSpec(
                backgrounds=BackgroundSourceConfig(provider="local", source_dir=background_source),
                icons=IconSourceConfig(
                    provider="google_material_design_icons",
                    archive_path=archive_path,
                ),
                classes=(
                    ClassSpec(
                        id=0,
                        name="icon_phone",
                        zh_name="电话",
                        source_icons=("call",),
                    ),
                    ClassSpec(
                        id=1,
                        name="icon_satellite",
                        zh_name="卫星",
                        source_icons=("satellite_alt",),
                    ),
                ),
            )

            output_root = root / "materials"
            result = build_offline_pack(spec, output_root=output_root, cache_dir=root / "cache")

            self.assertEqual(result.background_count, 2)
            self.assertEqual(result.class_count, 2)
            self.assertEqual(result.icon_file_count, 2)

            class_manifest = (output_root / "manifests" / "classes.yaml").read_text(encoding="utf-8")
            self.assertIn("icon_phone", class_manifest)
            self.assertIn("icon_satellite", class_manifest)

            phone_icon = output_root / "icons" / "icon_phone" / "001.png"
            satellite_icon = output_root / "icons" / "icon_satellite" / "001.png"
            self.assertEqual(get_image_size(phone_icon), (96, 96))
            self.assertEqual(get_image_size(satellite_icon), (48, 48))

            with (output_root / "manifests" / "backgrounds.csv").open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["provider"], "local")

            with (output_root / "manifests" / "icons.csv").open("r", encoding="utf-8", newline="") as handle:
                icon_rows = list(csv.DictReader(handle))
            self.assertEqual(len(icon_rows), 2)
            self.assertEqual(icon_rows[0]["provider"], "google_material_design_icons")

    def test_load_materials_pack_spec_from_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "materials-pack.toml"
            path.write_text(
                """
[backgrounds]
provider = "local"
source_dir = "/tmp/backgrounds"

[icons]
provider = "google_material_design_icons"
archive_path = "/tmp/icons.zip"

[[classes]]
id = 0
name = "icon_phone"
zh_name = "电话"
source_icons = ["call", "phone_in_talk"]
""".strip()
                + "\n",
                encoding="utf-8",
            )

            spec = load_materials_pack_spec(path)

            self.assertEqual(spec.backgrounds.provider, "local")
            self.assertEqual(spec.backgrounds.source_dir, Path("/tmp/backgrounds"))
            self.assertEqual(spec.icons.archive_path, Path("/tmp/icons.zip"))
            self.assertEqual(spec.classes[0].source_icons, ("call", "phone_in_talk"))


if __name__ == "__main__":
    unittest.main()
