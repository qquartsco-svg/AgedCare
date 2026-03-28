#!/usr/bin/env python3
"""Regenerate SIGNATURE.sha256 for this repo (sorted paths, SHA-256 per file)."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIR_NAMES = frozenset({
    ".git", ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache",
    ".venv", "venv", "dist", "build",
})
SKIP_SUFFIXES = (".pyc",)
SKIP_TOP = frozenset({"SIGNATURE.sha256"})


def iter_files() -> list[Path]:
    out: list[Path] = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if any(part in SKIP_DIR_NAMES for part in rel.parts):
            continue
        if p.suffix in SKIP_SUFFIXES:
            continue
        if rel.name in SKIP_TOP and len(rel.parts) == 1:
            continue
        out.append(p)
    return sorted(out, key=lambda x: str(x).lower())


def main() -> None:
    lines: list[str] = []
    for path in iter_files():
        rel = path.relative_to(ROOT)
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{h}  {rel.as_posix()}\n")
    out = ROOT / "SIGNATURE.sha256"
    out.write_text("".join(lines), encoding="utf-8")
    print(f"Wrote {len(lines)} entries to {out}")


if __name__ == "__main__":
    main()
