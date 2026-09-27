#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


OFFICIAL_ENTRY = '{ 0x35c, "947ae944f3de4ed4c21a7e4f7953ecf351bfa2b36239da37a34111ad29993eef" }, // SukiSU'


def die(msg: str) -> None:
    raise SystemExit(f"ERROR: {msg}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sukisu_source", type=Path)
    ap.add_argument("--size", required=True)
    ap.add_argument("--sha256", required=True)
    ap.add_argument("--label", default="Nova Utility")
    args = ap.parse_args()

    size = args.size.lower()
    sha = args.sha256.lower()

    if not re.fullmatch(r"0x[0-9a-f]+", size):
        die(f"invalid certificate size: {args.size}")
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        die(f"invalid certificate sha256: {args.sha256}")

    path = args.sukisu_source.resolve() / "kernel/manager/apk_sign.c"
    if not path.is_file():
        die(f"missing {path}")

    text = path.read_text(encoding="utf-8")

    if OFFICIAL_ENTRY not in text:
        die("audited official SukiSU certificate entry not found")

    if sha in text:
        die("custom certificate hash is already present before injection")

    custom = f'    {{ {size}, "{sha}" }}, // {args.label} final manager'
    marker = "    " + OFFICIAL_ENTRY
    if text.count(marker) != 1:
        die(f"expected exactly one official certificate marker, found {text.count(marker)}")

    text = text.replace(marker, marker + "\n" + custom, 1)
    path.write_text(text, encoding="utf-8")

    verify = path.read_text(encoding="utf-8")
    if verify.count(sha) != 1:
        die("custom certificate injection verification failed")

    print(f"PASS: added trusted manager certificate size={size} sha256={sha}")
    print(f"file={path}")


if __name__ == "__main__":
    main()
