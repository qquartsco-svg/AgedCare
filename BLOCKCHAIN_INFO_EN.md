> **English.** Korean (정본): [BLOCKCHAIN_INFO.md](BLOCKCHAIN_INFO.md)

# BLOCKCHAIN_INFO — AgedCare_Stack

## Purpose

Here, **blockchain** means an **integrity / audit pattern**, not a public consensus network.

| Artifact | Role |
|----------|------|
| `SIGNATURE.sha256` | Per-file **SHA-256** manifest |
| This document | Scope, verification, release block summary |
| `PHAM_BLOCKCHAIN_LOG.md` | Human-readable release continuity |

## Repository

| | |
|---|---|
| GitHub | https://github.com/qquartsco-svg/AgedCare_Stack |
| Package | `aged-care-stack` (import `aged_care`) |
| Version | Keep `VERSION`, `pyproject.toml`, `aged_care.__version__` aligned |

## Signed scope

`python scripts/regenerate_signature.py` walks the tree (skips `.git`, caches, etc.).

- `aged_care/**/*.py`, `tests/**/*.py`, `examples/**/*.py`, `scripts/*.py`
- Root docs: `README.md`, `README_EN.md`, `CHANGELOG.md`, `VERSION`, `pyproject.toml`, `LICENSE`, `BLOCKCHAIN_INFO*.md`, `PHAM_BLOCKCHAIN_LOG.md`

**Excluded:** the manifest file `SIGNATURE.sha256` itself.

## Verification

```bash
cd AgedCare_Stack
python scripts/regenerate_signature.py
python scripts/verify_signature.py
python -m pytest tests/ -q
```

## Release block — v0.2.2

Wheelchair mobility foundation bridge (`vehicle_platform_foundation`, `wheelchair_transform_system`), signature scripts, README / README_EN / LICENSE refresh. Related: GitHub `4WD`, sibling `Wheelchair_Transform_System` in 00_BRAIN.

## Note

Not a medical device submission. Does not replace regulatory certification.
