#!/usr/bin/env python3
"""Run PaddleOCR for review-first Japanese light-novel batch OCR.

This stage reads manifest.json, OCRs selected pages, saves raw JSON, writes
right-to-left ordered Japanese text, updates manifest page metrics, and writes
a quality report. It intentionally stops before translation.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from env_bootstrap import configure_skill_local_env

SKIP_KINDS_DEFAULT = {"cover", "illustration", "blank"}


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise SystemExit("PyYAML is required for YAML configs. Install pyyaml.") from exc
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"Config must be a YAML mapping: {path}")
    return data


def read_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if "pages" not in data or not isinstance(data["pages"], list):
        raise SystemExit(f"Invalid manifest: {path}")
    return data


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def page_stem(index: int) -> str:
    return f"page_{index:04d}"


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if hasattr(value, "tolist"):
        try:
            return value.tolist()
        except Exception:
            pass
    for attr in ("json", "res"):
        if hasattr(value, attr):
            try:
                return jsonable(getattr(value, attr))
            except Exception:
                pass
    if hasattr(value, "to_json"):
        try:
            return jsonable(value.to_json())
        except Exception:
            pass
    return str(value)


def find_key(node: Any, key: str) -> Any:
    if isinstance(node, dict):
        if key in node:
            return node[key]
        for value in node.values():
            found = find_key(value, key)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = find_key(value, key)
            if found is not None:
                return found
    return None


def normalize_point(point: Any) -> tuple[float, float] | None:
    if isinstance(point, dict):
        x = point.get("x")
        y = point.get("y")
        if x is not None and y is not None:
            return float(x), float(y)
    if isinstance(point, (list, tuple)) and len(point) >= 2:
        return float(point[0]), float(point[1])
    return None


def normalize_box(box: Any) -> list[tuple[float, float]]:
    if box is None:
        return []
    if isinstance(box, dict):
        for key in ("points", "poly", "box"):
            if key in box:
                return normalize_box(box[key])
    if isinstance(box, (list, tuple)):
        if len(box) == 4 and all(isinstance(v, (int, float)) for v in box):
            x1, y1, x2, y2 = [float(v) for v in box]
            return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        points = [normalize_point(p) for p in box]
        return [p for p in points if p is not None]
    return []


def box_bounds(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    if not points:
        return 0.0, 0.0, 0.0, 0.0
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def box_area(points: list[tuple[float, float]]) -> float:
    x1, y1, x2, y2 = box_bounds(points)
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


@dataclass
class OCRLine:
    text: str
    score: float | None
    points: list[tuple[float, float]]

    @property
    def cx(self) -> float:
        x1, _, x2, _ = box_bounds(self.points)
        return (x1 + x2) / 2

    @property
    def cy(self) -> float:
        _, y1, _, y2 = box_bounds(self.points)
        return (y1 + y2) / 2


def extract_lines(raw: Any) -> list[OCRLine]:
    data = jsonable(raw)
    texts = find_key(data, "rec_texts") or find_key(data, "texts") or []
    scores = find_key(data, "rec_scores") or find_key(data, "scores") or []
    boxes = (
        find_key(data, "rec_polys")
        or find_key(data, "dt_polys")
        or find_key(data, "rec_boxes")
        or find_key(data, "boxes")
        or []
    )
    lines: list[OCRLine] = []
    for i, text in enumerate(texts):
        if text is None:
            continue
        score = None
        if i < len(scores):
            try:
                score = float(scores[i])
            except Exception:
                score = None
        points = normalize_box(boxes[i]) if i < len(boxes) else []
        lines.append(OCRLine(text=str(text), score=score, points=points))
    return lines


def order_vertical_rl(lines: list[OCRLine], column_threshold: float | None = None) -> list[OCRLine]:
    boxed = [line for line in lines if line.points]
    unboxed = [line for line in lines if not line.points]
    if not boxed:
        return lines
    widths = []
    for line in boxed:
        x1, _, x2, _ = box_bounds(line.points)
        widths.append(max(1.0, x2 - x1))
    threshold = column_threshold or max(18.0, statistics.median(widths) * 1.4)
    columns: list[list[OCRLine]] = []
    for line in sorted(boxed, key=lambda item: item.cx, reverse=True):
        for column in columns:
            if abs(column[0].cx - line.cx) <= threshold:
                column.append(line)
                break
        else:
            columns.append([line])
    ordered: list[OCRLine] = []
    for column in columns:
        ordered.extend(sorted(column, key=lambda item: item.cy))
    ordered.extend(unboxed)
    return ordered


def clean_ordered_text(lines: list[OCRLine]) -> str:
    chunks = []
    for line in lines:
        text = line.text.strip()
        if text:
            chunks.append(text)
    return "\n".join(chunks).strip() + ("\n" if chunks else "")


def compact_raw_result(lines: list[OCRLine]) -> dict[str, Any]:
    return {
        "lines": [
            {
                "text": line.text,
                "score": line.score,
                "points": [[round(x, 3), round(y, 3)] for x, y in line.points],
            }
            for line in lines
        ]
    }


def image_area(page: dict[str, Any]) -> float | None:
    width = page.get("width")
    height = page.get("height")
    if isinstance(width, (int, float)) and isinstance(height, (int, float)) and width > 0 and height > 0:
        return float(width) * float(height)
    return None


def classify_after_ocr(page: dict[str, Any], lines: list[OCRLine], text_density: float | None) -> tuple[str, str]:
    current = str(page.get("kind", "unknown"))
    if current in {"cover", "illustration"}:
        return current, "kept filename/manual classification"
    char_count = sum(len(line.text.strip()) for line in lines)
    box_count = len(lines)
    if box_count == 0 or char_count == 0:
        return "blank", "no OCR text detected"
    if box_count <= 3 and char_count <= 20:
        return "chapter", "short OCR text suggests chapter/title page"
    if text_density is not None and text_density < 0.01 and char_count < 80:
        return "illustration", "low text density suggests illustration"
    return "body", "OCR metrics suggest body text"


def make_ocr(device: str, lang: str, use_orientation: bool) -> Any:
    configure_skill_local_env()
    from paddleocr import PaddleOCR  # type: ignore

    kwargs: dict[str, Any] = {
        "lang": lang,
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": use_orientation,
    }
    if device:
        kwargs["device"] = device
    return PaddleOCR(**kwargs)


def run_page(ocr: Any, image_path: Path) -> Any:
    return ocr.predict(str(image_path))


def write_quality_report(output_dir: Path, manifest: dict[str, Any], threshold: float) -> None:
    logs = output_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    lines = ["# OCR Quality Report", ""]
    low_conf = []
    review = []
    for page in manifest.get("pages", []):
        mean_conf = page.get("mean_confidence")
        kind = page.get("kind")
        status = page.get("ocr_status")
        if isinstance(mean_conf, (int, float)) and mean_conf < threshold:
            low_conf.append(page)
        if kind in {"unknown", "chapter"} or status == "error":
            review.append(page)
    lines.append("## Summary")
    lines.append(f"- Pages: {manifest.get('page_count', len(manifest.get('pages', [])))}")
    lines.append(f"- Low confidence pages: {len(low_conf)}")
    lines.append(f"- Review candidate pages: {len(review)}")
    lines.append("")
    lines.append("## Low Confidence Pages")
    if low_conf:
        for page in low_conf:
            lines.append(
                f"- page {int(page.get('index', 0)):04d} `{page.get('file')}`: "
                f"confidence={page.get('mean_confidence')}, kind={page.get('kind')}"
            )
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Review Candidates")
    if review:
        for page in review:
            lines.append(
                f"- page {int(page.get('index', 0)):04d} `{page.get('file')}`: "
                f"kind={page.get('kind')}, status={page.get('ocr_status')}, reason={page.get('reason', '')}"
            )
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Next Step")
    lines.append("Review `03_ordered_jp/` and this report before translation.")
    (logs / "quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def resolve_manifest(output_dir: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    candidates = [
        output_dir / "00_manifest" / "manifest.json",
        output_dir / "manifest.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise SystemExit(f"No manifest found under {output_dir}. Run book_pipeline.py scan first.")


def cmd_ocr(args: argparse.Namespace) -> None:
    config = load_yaml(Path(args.config)) if args.config else {}
    output_dir = Path(args.output_dir or config.get("output", {}).get("dir", "")).expanduser()
    if not output_dir:
        raise SystemExit("Output directory is required")
    manifest_path = resolve_manifest(output_dir, args.manifest)
    manifest = read_manifest(manifest_path)

    ocr_cfg = config.get("ocr", {})
    device = args.device or ocr_cfg.get("device", "gpu")
    lang = args.lang or ocr_cfg.get("lang", "japan")
    confidence_threshold = float(args.confidence_threshold or ocr_cfg.get("confidence_threshold", 0.82))
    use_orientation = bool(ocr_cfg.get("detect_orientation", True))
    overwrite = bool(args.overwrite)
    start_page = args.start_page
    end_page = args.end_page

    raw_dir = output_dir / "02_ocr_raw"
    ordered_dir = output_dir / "03_ordered_jp"
    raw_dir.mkdir(parents=True, exist_ok=True)
    ordered_dir.mkdir(parents=True, exist_ok=True)

    ocr = make_ocr(device=device, lang=lang, use_orientation=use_orientation)
    errors: list[dict[str, Any]] = []

    for page in manifest["pages"]:
        index = int(page["index"])
        if start_page is not None and index < start_page:
            continue
        if end_page is not None and index > end_page:
            continue
        stem = page_stem(index)
        kind = str(page.get("kind", "unknown"))
        raw_path = raw_dir / f"{stem}.json"
        txt_path = ordered_dir / f"{stem}.txt"
        if kind in SKIP_KINDS_DEFAULT:
            page["ocr_status"] = "skipped"
            continue
        if raw_path.exists() and txt_path.exists() and not overwrite:
            page["ocr_status"] = "cached"
            continue
        image_path = Path(page["abs_path"])
        try:
            raw = run_page(ocr, image_path)
            raw_json = jsonable(raw)
            lines = extract_lines(raw_json)
            write_json(raw_path, compact_raw_result(lines))
            ordered = order_vertical_rl(lines)
            txt_path.write_text(clean_ordered_text(ordered), encoding="utf-8")

            scores = [line.score for line in lines if line.score is not None and not math.isnan(line.score)]
            mean_conf = round(sum(scores) / len(scores), 4) if scores else None
            area = image_area(page)
            density = None
            if area:
                density = round(sum(box_area(line.points) for line in lines) / area, 6)
            new_kind, reason = classify_after_ocr(page, lines, density)
            page.update(
                {
                    "kind": new_kind,
                    "reason": reason,
                    "ocr_status": "done",
                    "ocr_raw": str(raw_path),
                    "ordered_jp": str(txt_path),
                    "box_count": len(lines),
                    "char_count": sum(len(line.text.strip()) for line in lines),
                    "mean_confidence": mean_conf,
                    "text_density": density,
                }
            )
            print(f"OCR page {index:04d}: {page['file']} -> {new_kind}, conf={mean_conf}")
        except Exception as exc:
            page["ocr_status"] = "error"
            page["error"] = str(exc)
            errors.append({"index": index, "file": page.get("file"), "error": str(exc)})
            print(f"ERROR page {index:04d}: {exc}")

    manifest["review_stage"] = "ocr_ready_for_review"
    write_json(manifest_path, manifest)
    write_quality_report(output_dir, manifest, confidence_threshold)
    if errors:
        write_json(output_dir / "logs" / "errors.json", errors)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run PaddleOCR for a book manifest")
    parser.add_argument("--config")
    parser.add_argument("--manifest")
    parser.add_argument("--output-dir")
    parser.add_argument("--device", choices=["gpu", "cpu"])
    parser.add_argument("--lang")
    parser.add_argument("--confidence-threshold", type=float)
    parser.add_argument("--start-page", type=int)
    parser.add_argument("--end-page", type=int)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    cmd_ocr(args)


if __name__ == "__main__":
    main()
