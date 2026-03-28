"""00_BRAIN 동위 스테이징 패키지를 PYTHONPATH에 넣어 연동 테스트를 켠다."""
from __future__ import annotations

import sys
from pathlib import Path

_STAGING = Path(__file__).resolve().parents[2]
for _name in ("Vehicle_Platform_Foundation", "Wheelchair_Transform_System"):
    _p = _STAGING / _name
    if _p.is_dir():
        sys.path.insert(0, str(_p))
