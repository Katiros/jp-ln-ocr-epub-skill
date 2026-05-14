#!/usr/bin/env python3
"""Write a Chinese README_OUTPUTS.md into an output workspace."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Write Chinese output guide")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    skill_root = Path(__file__).resolve().parents[1]
    template = skill_root / "assets" / "README_OUTPUTS.zh.md"
    output = Path(args.output_dir) / "README_OUTPUTS.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template, output)
    print(output)


if __name__ == "__main__":
    main()

