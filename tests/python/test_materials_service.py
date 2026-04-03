from __future__ import annotations

import csv
import io
import json
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import zlib
from http.client import IncompleteRead, RemoteDisconnected
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request

from core.common.images import get_image_size
from core.materials.service import (
    BackgroundSourceConfig,
    ClassSpec,
    IconSourceConfig,
    MaterialsPackSpec,
    _download_binary,
    _ensure_google_icons_archive,
    _load_google_icons_json,
    build_offline_pack,
    choose_best_google_icon_entry,
    load_materials_pack_spec,
    _open_with_retries,
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
    def test_load_google_icons_json_recovers_from_invalid_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache_path = cache_dir / "google-material-icons-tree.json"
            cache_path.write_text('{"tree":[{"path":"png', encoding="utf-8")
            payload = {
                "tree": [
                    {
                        "path": "png/communication/call/materialicons/4x_web/ic_call_black_24dp.png",
                        "type": "blob",
                    }
                ]
            }

            with patch("core.materials.service._open_with_retries") as open_with_retries:
                open_with_retries.return_value.__enter__.return_value = io.BytesIO(
                    json.dumps(payload).encode("utf-8")
                )
                result = _load_google_icons_json(
                    cache_path,
                    "https://example.com/tree.json",
                    description="test tree payload",
                )

            self.assertEqual(result, payload)
            self.assertEqual(json.loads(cache_path.read_text(encoding="utf-8")), payload)

    def test_load_google_icons_json_recovers_from_incomplete_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "google-material-icons-tree.json"
            payload = {"tree": [{"path": "png/action/home/materialicons/24dp/2x/baseline_home_black_24dp.png"}]}

            class _Response:
                def __init__(self, data: bytes, *, fail: bool = False) -> None:
                    self._data = data
                    self._fail = fail

                def __enter__(self) -> "_Response":
                    return self

                def __exit__(self, exc_type, exc, tb) -> None:
                    return None

                def read(self) -> bytes:
                    if self._fail:
                        raise IncompleteRead(b'{"tree":[', len(self._data))
                    return self._data

            with patch(
                "core.materials.service._open_with_retries",
                side_effect=[
                    _Response(b"{}", fail=True),
                    _Response(json.dumps(payload).encode("utf-8")),
                ],
            ):
                result = _load_google_icons_json(
                    cache_path,
                    "https://example.com/tree.json",
                    description="test tree payload",
                )

            self.assertEqual(result, payload)
            self.assertEqual(json.loads(cache_path.read_text(encoding="utf-8")), payload)

    def test_ensure_google_icons_archive_resumes_from_invalid_cached_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            destination = cache_dir / "master.zip"

            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr("icons/example.txt", "ok")
            payload = buffer.getvalue()
            partial = payload[: len(payload) // 2]
            destination.write_bytes(partial)
            requests: list[str | None] = []

            class _Response:
                def __init__(self, data: bytes) -> None:
                    self._data = data

                def __enter__(self) -> "_Response":
                    return self

                def __exit__(self, exc_type, exc, tb) -> None:
                    return None

                @property
                def headers(self) -> dict[str, str]:
                    start = len(partial)
                    end = len(payload) - 1
                    return {"Content-Range": f"bytes {start}-{end}/{len(payload)}"}

                @property
                def status(self) -> int:
                    return 206

                def read(self, size: int = -1) -> bytes:
                    if not self._data:
                        return b""
                    if size < 0 or size >= len(self._data):
                        chunk = self._data
                        self._data = b""
                    else:
                        chunk = self._data[:size]
                        self._data = self._data[size:]
                    return chunk

            def fake_urlopen(request: Request, timeout: float | None = None) -> _Response:
                range_header = request.headers.get("Range")
                requests.append(range_header)
                self.assertEqual(range_header, f"bytes={len(partial)}-")
                return _Response(payload[len(partial) :])

            config = IconSourceConfig(
                provider="google_material_design_icons",
                archive_url="https://example.com/master.zip",
            )

            with patch("core.materials.service.urlopen", side_effect=fake_urlopen):
                archive_path = _ensure_google_icons_archive(config, cache_dir)

            self.assertEqual(archive_path, destination)
            with zipfile.ZipFile(archive_path, "r") as archive:
                self.assertEqual(archive.namelist(), ["icons/example.txt"])
            self.assertEqual(requests, [f"bytes={len(partial)}-"])
            self.assertFalse(destination.with_suffix(".zip.part").exists())

    def test_download_binary_resumes_partial_download_after_disconnect(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "master.zip"
            payload = b"abcdefghij"
            requests: list[str | None] = []

            class _Response:
                def __init__(
                    self,
                    data: bytes,
                    *,
                    status: int = 200,
                    headers: dict[str, str] | None = None,
                    fail_after_first_chunk: bool = False,
                ) -> None:
                    self._data = data
                    self._headers = headers or {}
                    self._status = status
                    self._failed = False
                    self._first_chunk_delivered = False
                    self._fail_after_first_chunk = fail_after_first_chunk

                def __enter__(self) -> "_Response":
                    return self

                def __exit__(self, exc_type, exc, tb) -> None:
                    return None

                @property
                def headers(self) -> dict[str, str]:
                    return self._headers

                @property
                def status(self) -> int:
                    return self._status

                def read(self, size: int = -1) -> bytes:
                    if self._fail_after_first_chunk and self._first_chunk_delivered and not self._failed:
                        self._failed = True
                        raise RemoteDisconnected("stream interrupted")
                    if not self._data:
                        return b""
                    if size < 0 or size >= len(self._data):
                        chunk = self._data
                        self._data = b""
                    else:
                        chunk = self._data[:size]
                        self._data = self._data[size:]
                    self._first_chunk_delivered = True
                    return chunk

            def fake_urlopen(request: Request, timeout: float | None = None) -> _Response:
                range_header = request.headers.get("Range")
                requests.append(range_header)
                if range_header is None:
                    return _Response(payload[:4], fail_after_first_chunk=True)
                self.assertEqual(range_header, "bytes=4-")
                return _Response(
                    payload[4:],
                    status=206,
                    headers={"Content-Range": "bytes 4-9/10"},
                )

            with patch("core.materials.service.urlopen", side_effect=fake_urlopen):
                _download_binary("https://example.com/master.zip", destination)

            self.assertEqual(requests, [None, "bytes=4-"])
            self.assertEqual(destination.read_bytes(), payload)
            self.assertFalse(destination.with_suffix(".zip.part").exists())

    def test_download_binary_resumes_after_incomplete_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "master.zip"
            payload = b"abcdefghij"
            requests: list[str | None] = []

            class _Response:
                def __init__(
                    self,
                    data: bytes,
                    *,
                    status: int = 200,
                    headers: dict[str, str] | None = None,
                    fail_after_partial: bytes | None = None,
                ) -> None:
                    self._data = data
                    self._headers = headers or {}
                    self._status = status
                    self._fail_after_partial = fail_after_partial
                    self._failed = False

                def __enter__(self) -> "_Response":
                    return self

                def __exit__(self, exc_type, exc, tb) -> None:
                    return None

                @property
                def headers(self) -> dict[str, str]:
                    return self._headers

                @property
                def status(self) -> int:
                    return self._status

                def read(self, size: int = -1) -> bytes:
                    if self._fail_after_partial is not None and not self._failed:
                        self._failed = True
                        partial = self._fail_after_partial
                        self._data = self._data[len(partial) :]
                        raise IncompleteRead(partial, len(self._data))
                    if not self._data:
                        return b""
                    if size < 0 or size >= len(self._data):
                        chunk = self._data
                        self._data = b""
                    else:
                        chunk = self._data[:size]
                        self._data = self._data[size:]
                    return chunk

            def fake_urlopen(request: Request, timeout: float | None = None) -> _Response:
                range_header = request.headers.get("Range")
                requests.append(range_header)
                if range_header is None:
                    return _Response(payload, fail_after_partial=b"abcdef")
                self.assertEqual(range_header, "bytes=6-")
                return _Response(
                    payload[6:],
                    status=206,
                    headers={"Content-Range": "bytes 6-9/10"},
                )

            with patch("core.materials.service.urlopen", side_effect=fake_urlopen):
                _download_binary("https://example.com/master.zip", destination)

            self.assertEqual(requests, [None, "bytes=6-"])
            self.assertEqual(destination.read_bytes(), payload)
            self.assertFalse(destination.with_suffix(".zip.part").exists())

    def test_open_with_retries_recovers_from_transient_url_error(self) -> None:
        request = Request("https://example.com/test")

        class _Response:
            def __enter__(self) -> "_Response":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def read(self) -> bytes:
                return b"ok"

        attempts = {"count": 0}

        def fake_urlopen(_request: Request, timeout: float | None = None) -> _Response:
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise URLError("temporary network issue")
            return _Response()

        with patch("core.materials.service.urlopen", side_effect=fake_urlopen):
            with _open_with_retries(request, description="test") as response:
                self.assertEqual(response.read(), b"ok")

        self.assertEqual(attempts["count"], 3)

    def test_open_with_retries_recovers_from_remote_disconnect(self) -> None:
        request = Request("https://example.com/test")

        class _Response:
            def __enter__(self) -> "_Response":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def read(self) -> bytes:
                return b"ok"

        attempts = {"count": 0}

        def fake_urlopen(_request: Request, timeout: float | None = None) -> _Response:
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise RemoteDisconnected("remote end closed")
            return _Response()

        with patch("core.materials.service.urlopen", side_effect=fake_urlopen):
            with _open_with_retries(request, description="test") as response:
                self.assertEqual(response.read(), b"ok")

        self.assertEqual(attempts["count"], 3)

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

    def test_choose_best_google_icon_entry_prefers_exact_name_over_partial_match(self) -> None:
        entries = [
            "png/home/broadcast_on_home/materialicons/24dp/2x/baseline_broadcast_on_home_black_24dp.png",
            "png/home/home/materialicons/24dp/2x/baseline_home_black_24dp.png",
        ]

        result = choose_best_google_icon_entry(entries, "home")

        self.assertEqual(
            result,
            "png/home/home/materialicons/24dp/2x/baseline_home_black_24dp.png",
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

    def test_build_offline_pack_reuses_existing_local_background_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output_root = root / "materials"
            backgrounds_dir = output_root / "backgrounds"
            backgrounds_dir.mkdir(parents=True, exist_ok=True)
            _write_png(backgrounds_dir / "bg_local_0001.png", 1600, 900, (120, 160, 210))
            _write_png(backgrounds_dir / "bg_local_0002.png", 1600, 900, (140, 180, 220))

            archive_path = root / "material-design-icons.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                phone = root / "phone-4x.png"
                _write_png(phone, 96, 96, (30, 30, 30))
                archive.write(
                    phone,
                    "material-design-icons-main/png/communication/call/materialicons/4x_web/ic_call_black_24dp.png",
                )

            spec = MaterialsPackSpec(
                backgrounds=BackgroundSourceConfig(provider="local", source_dir=backgrounds_dir),
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
                ),
            )

            result = build_offline_pack(spec, output_root=output_root, cache_dir=root / "cache")

            self.assertEqual(result.background_count, 2)
            self.assertEqual(len(list(backgrounds_dir.glob("*.png"))), 2)

    def test_build_offline_pack_skips_missing_optional_source_icons(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            background_source = root / "background-source"
            _write_png(background_source / "lake.png", 1600, 900, (120, 160, 210))

            archive_path = root / "material-design-icons.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                phone = root / "phone-4x.png"
                _write_png(phone, 96, 96, (30, 30, 30))
                archive.write(
                    phone,
                    "material-design-icons-main/png/communication/call/materialicons/4x_web/ic_call_black_24dp.png",
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
                        source_icons=("call", "missing_icon"),
                    ),
                ),
            )

            output_root = root / "materials"
            result = build_offline_pack(spec, output_root=output_root, cache_dir=root / "cache")

            self.assertEqual(result.icon_file_count, 1)
            self.assertTrue((output_root / "icons" / "icon_phone" / "001.png").exists())

    def test_build_offline_pack_with_local_backgrounds_and_remote_google_icons(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            background_source = root / "background-source"
            _write_png(background_source / "lake.png", 1600, 900, (120, 160, 210))

            spec = MaterialsPackSpec(
                backgrounds=BackgroundSourceConfig(provider="local", source_dir=background_source),
                icons=IconSourceConfig(provider="google_material_design_icons"),
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

            resolved_entries = {
                "call": "png/communication/call/materialicons/4x_web/ic_call_black_24dp.png",
                "satellite_alt": "png/maps/satellite_alt/materialicons/2x_web/ic_satellite_alt_black_24dp.png",
            }

            def fake_download(url: str, destination: Path) -> None:
                if "call" in url:
                    _write_png(destination, 96, 96, (30, 30, 30))
                    return
                if "satellite_alt" in url:
                    _write_png(destination, 48, 48, (40, 40, 40))
                    return
                raise AssertionError(f"unexpected icon download url: {url}")

            output_root = root / "materials"
            with patch(
                "core.materials.service._resolve_google_icon_entry",
                side_effect=lambda icon_name, cache_dir: resolved_entries[icon_name],
            ):
                with patch("core.materials.service._download_binary", side_effect=fake_download):
                    result = build_offline_pack(spec, output_root=output_root, cache_dir=root / "cache")

            self.assertEqual(result.background_count, 1)
            self.assertEqual(result.class_count, 2)
            self.assertEqual(result.icon_file_count, 2)

            phone_icon = output_root / "icons" / "icon_phone" / "001.png"
            satellite_icon = output_root / "icons" / "icon_satellite" / "001.png"
            self.assertEqual(get_image_size(phone_icon), (96, 96))
            self.assertEqual(get_image_size(satellite_icon), (48, 48))

            with (output_root / "manifests" / "icons.csv").open("r", encoding="utf-8", newline="") as handle:
                icon_rows = list(csv.DictReader(handle))
            self.assertEqual(len(icon_rows), 2)
            self.assertEqual(icon_rows[0]["provider"], "google_material_design_icons")
            self.assertIn("source_path", icon_rows[0])

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
