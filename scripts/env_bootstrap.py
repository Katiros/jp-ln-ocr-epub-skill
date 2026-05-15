"""Skill-local runtime environment helpers.

Keep virtualenv, model caches, wheels, and CUDA DLL discovery local to the
skill folder so Codex/OpenClaw can share one environment on the same machine.
"""

from __future__ import annotations

import os
import site
from pathlib import Path


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def configure_skill_local_env() -> Path:
    root = skill_root()
    cache = root / ".cache"
    paths = {
        "PADDLE_HOME": cache / "paddle",
        "PADDLEOCR_HOME": cache / "paddleocr",
        "PADDLE_PDX_CACHE_HOME": cache / "paddlex",
        "PADDLEX_HOME": cache / "paddlex",
        "HF_HOME": cache / "huggingface",
        "MODELSCOPE_CACHE": cache / "modelscope",
        "PIP_CACHE_DIR": cache / "pip",
    }
    for key, path in paths.items():
        os.environ.setdefault(key, str(path))
        Path(os.environ[key]).mkdir(parents=True, exist_ok=True)
    add_nvidia_dll_dirs()
    return cache


def add_nvidia_dll_dirs() -> None:
    """Make pip-installed CUDA runtime DLLs visible on Windows."""
    if os.name != "nt":
        return
    candidates: list[Path] = []
    for site_dir in site.getsitepackages():
        base = Path(site_dir) / "nvidia"
        candidates.extend([base / "cu13" / "bin", base / "cu13" / "bin" / "x86_64", base / "cudnn" / "bin"])
    existing = [path for path in candidates if path.exists()]
    for path in existing:
        try:
            os.add_dll_directory(str(path))
        except (AttributeError, OSError):
            pass
    if existing:
        os.environ["PATH"] = os.pathsep.join([str(path) for path in existing] + [os.environ.get("PATH", "")])

