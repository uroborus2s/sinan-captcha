"""Image metadata helpers using the Python standard library only."""

from __future__ import annotations

import struct
from pathlib import Path


def get_image_size(path: Path) -> tuple[int, int]:
    """Return `(width, height)` for PNG and JPEG images."""

    with path.open("rb") as handle:
        header = handle.read(24)
        if len(header) < 24:
            raise ValueError(f"Image file is too small: {path}")

        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            width, height = struct.unpack(">II", header[16:24])
            return width, height

        if header[:2] == b"\xff\xd8":
            handle.seek(2)
            return _read_jpeg_size(handle, path)

    raise ValueError(f"Unsupported image format: {path}")


def _read_jpeg_size(handle, path: Path) -> tuple[int, int]:
    while True:
        marker_prefix = handle.read(1)
        if not marker_prefix:
            break
        if marker_prefix != b"\xff":
            continue

        marker = handle.read(1)
        while marker == b"\xff":
            marker = handle.read(1)
        if not marker:
            break

        marker_value = marker[0]
        if marker_value in {0xD8, 0xD9}:
            continue

        segment_length_raw = handle.read(2)
        if len(segment_length_raw) != 2:
            break
        segment_length = struct.unpack(">H", segment_length_raw)[0]
        if segment_length < 2:
            raise ValueError(f"Invalid JPEG segment length: {path}")

        if marker_value in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            segment = handle.read(segment_length - 2)
            if len(segment) < 5:
                break
            height, width = struct.unpack(">HH", segment[1:5])
            return width, height

        handle.seek(segment_length - 2, 1)

    raise ValueError(f"Could not determine JPEG size: {path}")
