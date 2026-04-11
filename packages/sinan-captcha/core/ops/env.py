"""Cross-platform environment checks for training hosts."""

from __future__ import annotations

import argparse
import importlib
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class EnvironmentReport:
    python_executable: str
    uv_found: bool
    yolo_found: bool
    nvidia_smi_found: bool
    nvidia_smi_ok: bool
    nvidia_smi_excerpt: str
    torch_installed: bool
    torch_version: str | None
    torch_cuda_version: str | None
    torch_cuda_available: bool | None
    torch_device_name: str | None
    ultralytics_installed: bool
    ultralytics_version: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def collect_environment_report() -> EnvironmentReport:
    uv_found = shutil.which("uv") is not None
    yolo_found = shutil.which("yolo") is not None
    nvidia_smi_path = shutil.which("nvidia-smi")

    nvidia_smi_ok = False
    nvidia_smi_excerpt = ""
    if nvidia_smi_path is not None:
        try:
            result = subprocess.run(
                [nvidia_smi_path],
                check=True,
                capture_output=True,
                text=True,
            )
            nvidia_smi_ok = True
            nvidia_smi_excerpt = _first_non_empty_line(result.stdout)
        except subprocess.CalledProcessError as exc:
            nvidia_smi_excerpt = _first_non_empty_line(exc.stdout or exc.stderr or "")

    torch_installed = False
    torch_version = None
    torch_cuda_version = None
    torch_cuda_available = None
    torch_device_name = None
    try:
        torch = importlib.import_module("torch")
        torch_installed = True
        torch_version = getattr(torch, "__version__", None)
        torch_cuda_version = getattr(getattr(torch, "version", None), "cuda", None)
        torch_cuda_available = bool(torch.cuda.is_available())
        if torch_cuda_available:
            torch_device_name = str(torch.cuda.get_device_name(0))
    except Exception:
        pass

    ultralytics_installed = False
    ultralytics_version = None
    try:
        ultralytics = importlib.import_module("ultralytics")
        ultralytics_installed = True
        ultralytics_version = getattr(ultralytics, "__version__", None)
    except Exception:
        pass

    return EnvironmentReport(
        python_executable=sys.executable,
        uv_found=uv_found,
        yolo_found=yolo_found,
        nvidia_smi_found=nvidia_smi_path is not None,
        nvidia_smi_ok=nvidia_smi_ok,
        nvidia_smi_excerpt=nvidia_smi_excerpt,
        torch_installed=torch_installed,
        torch_version=torch_version,
        torch_cuda_version=torch_cuda_version,
        torch_cuda_available=torch_cuda_available,
        torch_device_name=torch_device_name,
        ultralytics_installed=ultralytics_installed,
        ultralytics_version=ultralytics_version,
    )


def _first_non_empty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Check whether a training host is ready for YOLO jobs.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    report = collect_environment_report()
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
