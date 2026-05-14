#!/usr/bin/env python3
"""Utility entry points for jp-ln-ocr-epub.

This script provides the stable manifest foundation for review-first book OCR.
It scans an image folder, natural-sorts pages, creates numbered output
directories, and writes 00_manifest/manifest.json.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


IMAGE_PATTERNS = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp", "*.tif", "*.tiff")
OUTPUT_DIRS = (
    "00_manifest",
    "01_preprocessed",
    "02_ocr_raw",
    "03_ordered_jp",
    "04_cleaned_jp",
    "05_glossary",
    "06_translated_zh",
    "07_bilingual",
    "08_review",
    "logs",
)


def natural_key(value: str) -> list[Any]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise SystemExit("PyYAML is required for YAML configs. Install pyyaml or use JSON.") from exc
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"Config must be a YAML mapping: {path}")
    return data


@dataclass
class PageRecord:
    index: int
    file: str
    abs_path: str
    kind: str
    width: int | None = None
    height: int | None = None
    reason: str = ""
    ocr_status: str = "pending"
    translation_status: str = "not_started"


def ensure_output_dirs(output_dir: Path) -> None:
    for name in OUTPUT_DIRS:
        (output_dir / name).mkdir(parents=True, exist_ok=True)


def image_size(path: Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return None, None
    try:
        with Image.open(path) as img:
            return img.size
    except Exception:
        return None, None


def classify_page_by_name(path: Path, index_zero_based: int) -> tuple[str, str]:
    name = path.stem.lower()
    if any(token in name for token in ("cover", "front", "hyoushi", "coverpage")):
        return "cover", "filename suggests cover"
    if any(token in name for token in ("illust", "illustration", "insert", "color", "kuchie")):
        return "illustration", "filename suggests illustration"
    if any(token in name for token in ("toc", "contents", "mokuji")):
        return "toc", "filename suggests table of contents"
    if any(token in name for token in ("copyright", "colophon", "okuduke")):
        return "copyright", "filename suggests copyright/colophon"
    if index_zero_based == 0:
        return "cover", "first page fallback"
    return "unknown", "awaiting OCR-based classification"


def scan_images(input_dir: Path, patterns: list[str]) -> list[Path]:
    files: list[Path] = []
    for child in input_dir.iterdir():
        if not child.is_file():
            continue
        if any(fnmatch.fnmatch(child.name.lower(), pattern.lower()) for pattern in patterns):
            files.append(child)
    return sorted(files, key=lambda p: natural_key(p.name))


def create_manifest(input_dir: Path, output_dir: Path, patterns: list[str]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    ensure_output_dirs(output_dir)
    images = scan_images(input_dir, patterns)
    records: list[PageRecord] = []
    for index, path in enumerate(images, start=1):
        kind, reason = classify_page_by_name(path, index - 1)
        width, height = image_size(path)
        records.append(
            PageRecord(
                index=index,
                file=path.name,
                abs_path=str(path.resolve()),
                kind=kind,
                width=width,
                height=height,
                reason=reason,
                ocr_status="skipped" if kind in {"cover", "illustration", "blank"} else "pending",
            )
        )
    manifest = {
        "input_dir": str(input_dir.resolve()),
        "page_count": len(records),
        "review_stage": "manifest_created",
        "pages": [asdict(record) for record in records],
    }
    manifest_path = output_dir / "00_manifest" / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def init_config(target: Path) -> None:
    here = Path(__file__).resolve().parents[1]
    template = here / "assets" / "config.example.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template, target)


def cmd_scan(args: argparse.Namespace) -> None:
    config = load_yaml(Path(args.config)) if args.config else {}
    input_dir = Path(args.input_dir or config.get("input", {}).get("path", "")).expanduser()
    output_dir = Path(args.output_dir or config.get("output", {}).get("dir", "")).expanduser()
    patterns = config.get("input", {}).get("file_patterns", list(IMAGE_PATTERNS))
    if not input_dir.exists():
        raise SystemExit(f"Input directory not found: {input_dir}")
    if not output_dir:
        raise SystemExit("Output directory is required")
    manifest_path = create_manifest(input_dir, output_dir, list(patterns))
    print(f"Wrote manifest: {manifest_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JP LN OCR EPUB helper")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init-config", help="copy example config to a target path")
    init.add_argument("target")
    init.set_defaults(func=lambda args: init_config(Path(args.target)))

    scan = sub.add_parser("scan", help="scan image folder and create 00_manifest/manifest.json")
    scan.add_argument("--config")
    scan.add_argument("--input-dir")
    scan.add_argument("--output-dir")
    scan.set_defaults(func=cmd_scan)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
