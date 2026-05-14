#!/usr/bin/env python3
"""Environment check helper for PaddleOCR.

This does not run OCR. It reports whether the expected imports are available,
so an agent can decide whether to install dependencies or use an existing env.
"""

from __future__ import annotations

import importlib.util


def status(module: str) -> str:
    return "ok" if importlib.util.find_spec(module) else "missing"


def main() -> None:
    print(f"paddle: {status('paddle')}")
    print(f"paddleocr: {status('paddleocr')}")
    print(f"PIL: {status('PIL')}")
    print(f"docx: {status('docx')}")
    print("Expected OCR engine: PaddleOCR(lang='japan', use_angle_cls=True)")
    print("For full-book work, run manifest scan first, then OCR only body pages.")


if __name__ == "__main__":
    main()

