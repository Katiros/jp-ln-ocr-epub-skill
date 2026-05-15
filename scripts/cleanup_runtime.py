#!/usr/bin/env python3
"""Remove disposable temp/cache files without touching review artifacts."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


OUTPUT_TEMP_DIR_NAMES = {
    ".tmp",
    "tmp",
    "temp",
    "__pycache__",
}
OUTPUT_TEMP_SUFFIXES = {
    ".tmp",
    ".temp",
    ".pyc",
    ".pyo",
}
RUNTIME_TEMP_NAMES = {
    "._____temp",
    "temp",
    "tmp",
}


def remove_path(path: Path, dry_run: bool) -> int:
    if not path.exists():
        return 0
    if dry_run:
        print(f"would remove: {path}")
        return 1
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    print(f"removed: {path}")
    return 1


def cleanup_output(output_dir: Path, dry_run: bool) -> int:
    if not output_dir.exists():
        return 0
    removed = 0
    for path in sorted(output_dir.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        name = path.name.lower()
        if path.is_dir() and name in OUTPUT_TEMP_DIR_NAMES:
            removed += remove_path(path, dry_run)
            continue
        if path.is_file() and (name in OUTPUT_TEMP_DIR_NAMES or path.suffix.lower() in OUTPUT_TEMP_SUFFIXES):
            removed += remove_path(path, dry_run)
    return removed


def cleanup_runtime(skill_root: Path, dry_run: bool, include_venv_pycache: bool) -> int:
    removed = 0
    cache_root = skill_root / ".cache"
    if cache_root.exists():
        for path in sorted(cache_root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
            if path.name.lower() in RUNTIME_TEMP_NAMES:
                removed += remove_path(path, dry_run)

    for path in (skill_root / "scripts").rglob("__pycache__"):
        removed += remove_path(path, dry_run)

    if include_venv_pycache:
        venv = skill_root / ".venv"
        for path in venv.rglob("__pycache__"):
            removed += remove_path(path, dry_run)
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean disposable runtime temp files")
    parser.add_argument("--output-dir", help="Output directory to clean")
    parser.add_argument("--skill-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--runtime", action="store_true", help="Clean skill .cache temp folders and script pycache")
    parser.add_argument("--include-venv-pycache", action="store_true", help="Also remove .venv __pycache__ folders")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    removed = 0
    if args.output_dir:
        removed += cleanup_output(Path(args.output_dir), args.dry_run)
    if args.runtime:
        removed += cleanup_runtime(Path(args.skill_root), args.dry_run, args.include_venv_pycache)
    print(f"cleanup_count: {removed}")


if __name__ == "__main__":
    main()
