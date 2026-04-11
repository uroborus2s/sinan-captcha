"""Shared image input helpers for standalone solver services."""

from __future__ import annotations

import base64
import binascii
import io
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from sinanz_errors import SolverInputError
from sinanz_types import ImageInput

MAX_IMAGE_BYTES = 20 * 1024 * 1024
REMOTE_TIMEOUT_SECONDS = 8.0
REMOTE_MAX_REDIRECTS = 5
_BASE64_CHARS_RE = re.compile(r"^[A-Za-z0-9+/=_-]+$")


@contextmanager
def resolved_image_path(image: ImageInput, *, field: str) -> Iterator[Path]:
    """Normalize image input to a readable local path for runtime inference."""
    temp_path: Path | None = None
    try:
        if isinstance(image, Path):
            path = image.expanduser()
            _require_existing_file(path=path, field=field)
            yield path
            return

        if isinstance(image, str):
            raw = image.strip()
            if not raw:
                raise SolverInputError(f"`{field}` 必须是非空输入。")

            if _is_remote_url(raw):
                payload = _fetch_remote_image_bytes(raw, field=field)
                temp_path = _write_temp_image_bytes(payload, field=field)
                yield temp_path
                return

            if raw.startswith("data:"):
                payload = _decode_data_uri(raw, field=field)
                temp_path = _write_temp_image_bytes(payload, field=field)
                yield temp_path
                return

            if _looks_like_base64_payload(raw):
                payload = _decode_base64_payload(raw, field=field)
                temp_path = _write_temp_image_bytes(payload, field=field)
                yield temp_path
                return

            path = Path(raw).expanduser()
            _require_existing_file(path=path, field=field)
            yield path
            return

        if isinstance(image, (bytes, bytearray, memoryview)):
            payload = bytes(image)
            temp_path = _write_temp_image_bytes(payload, field=field)
            yield temp_path
            return

        raise SolverInputError(f"`{field}` 输入类型不支持：{type(image).__name__}。")
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _require_existing_file(*, path: Path, field: str) -> None:
    if not path.is_file():
        raise SolverInputError(f"`{field}` 指向的文件不存在：{path}")


def _is_remote_url(raw: str) -> bool:
    lowered = raw.lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def _looks_like_base64_payload(raw: str) -> bool:
    normalized = "".join(raw.split())
    if len(normalized) < 64:
        return False
    if normalized.startswith(("http://", "https://", "data:")):
        return False
    if re.match(r"^[A-Za-z]:[\\/].+", normalized):
        return False
    return _BASE64_CHARS_RE.fullmatch(normalized) is not None


def _decode_data_uri(raw: str, *, field: str) -> bytes:
    header, separator, payload = raw.partition(",")
    if separator == "":
        raise SolverInputError(f"`{field}` 的 data URI 缺少 `,` 分隔符。")
    if ";base64" not in header.lower():
        raise SolverInputError(f"`{field}` 的 data URI 仅支持 base64 编码。")
    return _decode_base64_payload(payload, field=field)


def _decode_base64_payload(raw: str, *, field: str) -> bytes:
    normalized = "".join(raw.split())
    padded = normalized + "=" * (-len(normalized) % 4)

    for decoder in (_std_b64decode, _urlsafe_b64decode):
        try:
            payload = decoder(padded)
        except (ValueError, binascii.Error):
            continue
        if not payload:
            raise SolverInputError(f"`{field}` 的 base64 解码结果为空。")
        if len(payload) > MAX_IMAGE_BYTES:
            raise SolverInputError(f"`{field}` 图片大小超过限制（>{MAX_IMAGE_BYTES} bytes）。")
        _validate_image_bytes(payload, field=field)
        return payload

    raise SolverInputError(f"`{field}` 不是合法的 base64 图片内容。")


def _std_b64decode(value: str) -> bytes:
    return base64.b64decode(value, validate=True)


def _urlsafe_b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value)


def _fetch_remote_image_bytes(url: str, *, field: str) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise SolverInputError(f"`{field}` URL 协议不支持：{parsed.scheme}")
    if not parsed.netloc:
        raise SolverInputError(f"`{field}` URL 非法：{url}")

    opener = build_opener(_LimitedRedirectHandler(max_redirects=REMOTE_MAX_REDIRECTS))
    request = Request(url, headers={"User-Agent": "sinanz/0.1"})
    try:
        with opener.open(request, timeout=REMOTE_TIMEOUT_SECONDS) as response:
            raw_length = response.headers.get("Content-Length")
            if raw_length not in {None, ""}:
                try:
                    declared = int(str(raw_length))
                except ValueError:
                    declared = None
                if declared is not None and declared > MAX_IMAGE_BYTES:
                    raise SolverInputError(
                        f"`{field}` 远程图片超过大小限制（>{MAX_IMAGE_BYTES} bytes）。"
                    )
            payload = _read_limited_stream(response, limit=MAX_IMAGE_BYTES, field=field)
    except SolverInputError:
        raise
    except Exception as exc:
        raise SolverInputError(f"`{field}` URL 下载失败：{exc}") from exc

    if not payload:
        raise SolverInputError(f"`{field}` URL 下载结果为空。")
    _validate_image_bytes(payload, field=field)
    return payload


def _read_limited_stream(response: Any, *, limit: int, field: str) -> bytes:
    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = response.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise SolverInputError(f"`{field}` 图片大小超过限制（>{limit} bytes）。")
        chunks.append(bytes(chunk))
    return b"".join(chunks)


def _write_temp_image_bytes(payload: bytes, *, field: str) -> Path:
    if len(payload) > MAX_IMAGE_BYTES:
        raise SolverInputError(f"`{field}` 图片大小超过限制（>{MAX_IMAGE_BYTES} bytes）。")
    _validate_image_bytes(payload, field=field)
    with tempfile.NamedTemporaryFile(prefix="sinanz_input_", suffix=".img", delete=False) as handle:
        handle.write(payload)
        temp_name = handle.name
    return Path(temp_name)


def _validate_image_bytes(payload: bytes, *, field: str) -> None:
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise SolverInputError("当前环境缺少 Pillow，无法解码图片输入。") from exc

    try:
        with Image.open(io.BytesIO(payload)) as image:
            image.load()
    except Exception as exc:
        raise SolverInputError(
            f"`{field}` 不是可解码的图片内容。"
            "支持范围为 Pillow 可解码图片格式（如 JPEG/PNG/WebP/BMP/GIF/TIFF）。"
        ) from exc


class _LimitedRedirectHandler(HTTPRedirectHandler):
    def __init__(self, *, max_redirects: int) -> None:
        self.max_redirects = max_redirects

    def redirect_request(
        self,
        req: Any,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Any:
        current = int(getattr(req, "_sinanz_redirects", 0))
        if current >= self.max_redirects:
            raise SolverInputError(f"URL 重定向次数超过限制（>{self.max_redirects}）。")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None:
            redirected._sinanz_redirects = current + 1
        return redirected
