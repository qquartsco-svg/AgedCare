"""CareChain — SHA-256 연결 감사 체인.

모든 케어 이벤트를 불변의 블록으로 기록:
  h_n = SHA-256(h_{n-1} || event_type || platform || t_s || data)

SYD_DRIFT CommandChain, marine-propulsion CommandChain과 동일 패턴.

기록 이벤트:
  - 핸드오프 (플랫폼 전환)
  - 긴급 상황
  - 투약/식사
  - 목적지 도착
  - 케어 결정 (speak, alert)
"""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from ..contracts.schemas import PlatformType

@dataclass
class CareBlock:
    index: int
    event_type: str
    platform: str
    t_s: float
    data: Dict[str, Any]
    prev_hash: str
    block_hash: str

    def to_dict(self) -> dict:
        return {
            "index":      self.index,
            "event_type": self.event_type,
            "platform":   self.platform,
            "t_s":        round(self.t_s, 3),
            "data":       self.data,
            "prev_hash":  self.prev_hash,
            "block_hash": self.block_hash,
        }

def _make_hash(prev_hash: str, event_type: str, platform: str,
               t_s: float, data: Dict) -> str:
    raw = f"{prev_hash}|{event_type}|{platform}|{t_s:.3f}|{json.dumps(data, sort_keys=True)}"
    return hashlib.sha256(raw.encode()).hexdigest()

class CareChain:
    """SHA-256 연결 케어 감사 체인.

    사용법::
        chain = CareChain()
        chain.record("handoff", PlatformType.PET, 0.0, {"to": "wheelchair"})
        chain.record("vitals_alert", PlatformType.WHEELCHAIR, 5.0, {"hr": 130})
        print(chain.verify())  # True
        chain.export_json("care_log.json")
    """

    GENESIS_HASH = "0" * 64

    def __init__(self):
        self._blocks: List[CareBlock] = []
        self._head_hash = self.GENESIS_HASH

    def record(self, event_type: str, platform: PlatformType,
               t_s: float, data: Optional[Dict[str, Any]] = None) -> CareBlock:
        """이벤트 기록 — 불변 블록 생성."""
        data = data or {}
        h = _make_hash(self._head_hash, event_type, platform.value, t_s, data)
        block = CareBlock(
            index=len(self._blocks),
            event_type=event_type,
            platform=platform.value,
            t_s=t_s,
            data=data,
            prev_hash=self._head_hash,
            block_hash=h,
        )
        self._blocks.append(block)
        self._head_hash = h
        return block

    def verify(self) -> bool:
        """체인 무결성 검증."""
        prev = self.GENESIS_HASH
        for blk in self._blocks:
            expected = _make_hash(prev, blk.event_type, blk.platform,
                                   blk.t_s, blk.data)
            if expected != blk.block_hash:
                return False
            prev = blk.block_hash
        return True

    def export_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump([b.to_dict() for b in self._blocks], f,
                      ensure_ascii=False, indent=2)

    @property
    def length(self) -> int:
        return len(self._blocks)

    @property
    def head_hash(self) -> str:
        return self._head_hash

    def summary(self) -> str:
        event_counts: Dict[str, int] = {}
        for b in self._blocks:
            event_counts[b.event_type] = event_counts.get(b.event_type, 0) + 1
        lines = [f"[CareChain] {self.length}개 블록 | 무결성={self.verify()}"]
        for etype, cnt in sorted(event_counts.items()):
            lines.append(f"  {etype}: {cnt}건")
        return "\n".join(lines)
