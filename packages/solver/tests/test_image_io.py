from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sinanz_errors import SolverInputError
from sinanz_image_io import MAX_IMAGE_BYTES, resolved_image_path

_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Y2ioAAAAASUVORK5CYII="
)


class ImageIoTest(unittest.TestCase):
    def test_resolved_image_path_accepts_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.png"
            path.write_bytes(_PNG_BYTES)

            with resolved_image_path(path, field="background_image") as resolved:
                self.assertEqual(resolved, path)

    def test_resolved_image_path_accepts_raw_bytes_and_cleans_up(self) -> None:
        temp_path: Path | None = None
        with resolved_image_path(_PNG_BYTES, field="background_image") as resolved:
            temp_path = resolved
            self.assertTrue(resolved.exists())

        self.assertIsNotNone(temp_path)
        self.assertFalse(temp_path.exists())

    def test_resolved_image_path_accepts_base64_string(self) -> None:
        payload = base64.b64encode(_PNG_BYTES).decode("ascii")
        with resolved_image_path(payload, field="background_image") as resolved:
            self.assertTrue(resolved.exists())

    def test_resolved_image_path_accepts_data_uri(self) -> None:
        payload = base64.b64encode(_PNG_BYTES).decode("ascii")
        data_uri = f"data:image/png;base64,{payload}"
        with resolved_image_path(data_uri, field="background_image") as resolved:
            self.assertTrue(resolved.exists())

    def test_resolved_image_path_accepts_https_url(self) -> None:
        fake_opener = _FakeOpener(response=_FakeResponse(payload=_PNG_BYTES))
        with patch("sinanz_image_io.build_opener", return_value=fake_opener):
            with resolved_image_path(
                "https://example.com/a.png",
                field="background_image",
            ) as resolved:
                self.assertTrue(resolved.exists())
        self.assertIsNotNone(fake_opener.last_request)
        self.assertEqual(fake_opener.last_timeout, 8.0)
        self.assertEqual(fake_opener.last_request.full_url, "https://example.com/a.png")

    def test_resolved_image_path_rejects_large_remote_payload(self) -> None:
        fake_opener = _FakeOpener(
            response=_FakeResponse(
                payload=_PNG_BYTES,
                headers={"Content-Length": str(MAX_IMAGE_BYTES + 1)},
            )
        )
        with patch("sinanz_image_io.build_opener", return_value=fake_opener):
            with self.assertRaises(SolverInputError):
                with resolved_image_path("https://example.com/a.png", field="background_image"):
                    self.fail("expected SolverInputError")

    def test_resolved_image_path_rejects_missing_local_file(self) -> None:
        with self.assertRaises(SolverInputError):
            with resolved_image_path("/tmp/does-not-exist.png", field="background_image"):
                self.fail("expected SolverInputError")


class _FakeResponse:
    def __init__(self, *, payload: bytes, headers: dict[str, str] | None = None) -> None:
        self._payload = payload
        self.headers = dict(headers or {})
        self._offset = 0

    def read(self, size: int = -1) -> bytes:
        if size == 0:
            return b""
        if self._offset >= len(self._payload):
            return b""
        if size < 0:
            chunk = self._payload[self._offset :]
            self._offset = len(self._payload)
            return chunk
        end = min(len(self._payload), self._offset + size)
        chunk = self._payload[self._offset : end]
        self._offset = end
        return chunk

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeOpener:
    def __init__(self, *, response: _FakeResponse) -> None:
        self._response = response
        self.last_request = None
        self.last_timeout = None

    def open(self, request, timeout: float):  # type: ignore[no-untyped-def]
        self.last_request = request
        self.last_timeout = timeout
        return self._response


if __name__ == "__main__":
    unittest.main()
