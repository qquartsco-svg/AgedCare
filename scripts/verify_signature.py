#!/usr/bin/env python3
"""Verify tree against SIGNATURE.sha256."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "SIGNATURE.sha256"


def sha256_of(path: Path) -> str:
    d = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            d.update(chunk)
    return d.hexdigest()


def main() -> int:
    if not MANIFEST.exists():
        print("SIGNATURE.sha256: missing", file=sys.stderr)
        return 1
    ok = True
    n = 0
    for raw in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            continue
        digest, relpath = parts
        n += 1
        target = ROOT / relpath
        if not target.exists():
            print(f"MISSING {relpath}", file=sys.stderr)
            ok = False
            continue
        if sha256_of(target) != digest:
            print(f"MISMATCH {relpath}", file=sys.stderr)
            ok = False
    if ok:
        print(f"verify_signature: OK ({n} files)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
