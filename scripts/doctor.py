#!/usr/bin/env python3
"""Print a concise environment report for Codex/OpenClaw runs."""

from __future__ import annotations

import importlib.metadata
import os
import sys
from pathlib import Path

from env_bootstrap import configure_skill_local_env


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def main() -> None:
    skill_root = Path(__file__).resolve().parents[1]
    cache = configure_skill_local_env()

    print("# jp-ln-ocr-epub doctor")
    print(f"skill_root: {skill_root}")
    print(f"python: {sys.executable}")
    print(f"python_version: {sys.version.split()[0]}")
    print(f"config.yaml: {(skill_root / 'config.yaml').exists()}")
    print(f"DEEPSEEK_API_KEY: {'set' if os.environ.get('DEEPSEEK_API_KEY') else 'not set'}")
    print(f"cache_root: {cache}")
    for key in ("PADDLE_HOME", "PADDLEOCR_HOME", "PADDLE_PDX_CACHE_HOME", "PADDLEX_HOME", "PIP_CACHE_DIR"):
        print(f"{key}: {os.environ.get(key, '')}")
    print(f"paddlepaddle: {package_version('paddlepaddle')}")
    print(f"paddlepaddle-gpu: {package_version('paddlepaddle-gpu')}")
    print(f"paddleocr: {package_version('paddleocr')}")

    try:
        import paddle  # type: ignore

        print(f"paddle_version: {paddle.__version__}")
        print(f"compiled_cuda: {paddle.device.is_compiled_with_cuda()}")
        print(f"device: {paddle.device.get_device()}")
        try:
            print(f"gpu_count: {paddle.device.cuda.device_count()}")
        except Exception as exc:  # pragma: no cover - hardware dependent
            print(f"gpu_count: unavailable ({exc})")
    except Exception as exc:
        print(f"paddle_import_error: {exc}")


if __name__ == "__main__":
    main()
