"""MemoryEngine — 공간·에피소드 기억 관리.

해마 모델 (Hippocampus):
  - Place cells: 위치별 가우시안 활성화
  - 기억 강도: m(t) = m₀ × exp(-t/τ), τ = 망각 시정수
  - Hopfield 패턴 완성: recall from partial cue

외부 엔진: HippocampusEngine (ENGINE_HUB/20_LIMBIC_LAYER/Hippocampus_Engine)
폴백: 단순 최근 기억 버퍼 (recency-weighted)
"""
from __future__ import annotations
import sys, os, math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

ENGINE_HUB_PATH = os.path.join(
    os.path.dirname(__file__), "../../../../02_SYSTEMS/ENGINE_HUB/2_operational"
)

@dataclass
class MemoryTrace:
    content: str
    location: Optional[Tuple[float, float]] = None
    strength: float = 1.0              # m₀
    t_encoded_s: float = 0.0
    tau_s: float = 86400.0             # 망각 시정수 (기본 24시간)
    tags: List[str] = field(default_factory=list)

    def current_strength(self, t_now_s: float) -> float:
        """m(t) = m₀ × exp(-(t-t₀)/τ)"""
        dt = max(0.0, t_now_s - self.t_encoded_s)
        return self.strength * math.exp(-dt / self.tau_s)

class MemoryEngine:
    """에피소드·공간 기억 엔진.

    HippocampusEngine 미설치 시 폴백:
      단순 최근-우선(recency-weighted) 기억 목록
    """
    CONSOLIDATION_TAU_S = 3600.0   # 1시간 → 장기 기억 강화

    def __init__(self):
        self._hippo = self._try_load_hippocampus()
        self._traces: List[MemoryTrace] = []
        self._max_traces = 200

    def _try_load_hippocampus(self):
        try:
            hippo_dir = os.path.join(
                ENGINE_HUB_PATH, "20_LIMBIC_LAYER/Hippocampus_Engine"
            )
            sys.path.insert(0, hippo_dir)
            from core import HippocampusEngine
            return HippocampusEngine()
        except Exception:
            return None

    def encode(self, content: str, location: Optional[Tuple[float, float]],
               t_s: float, tags: Optional[List[str]] = None, importance: float = 1.0) -> MemoryTrace:
        """기억 인코딩."""
        trace = MemoryTrace(
            content=content,
            location=location,
            strength=importance,
            t_encoded_s=t_s,
            tags=tags or [],
        )
        if self._hippo and location:
            try:
                x, y = location
                self._hippo.encode(x, y, content, t_s)
            except Exception:
                pass
        self._traces.append(trace)
        # 최대 용량 초과 시 가장 약한 기억 제거
        if len(self._traces) > self._max_traces:
            self._traces.sort(key=lambda tr: tr.current_strength(t_s))
            self._traces = self._traces[-self._max_traces:]
        return trace

    def recall_by_location(self, location: Tuple[float, float],
                            radius_m: float, t_s: float) -> List[MemoryTrace]:
        """위치 기반 기억 회상."""
        if self._hippo:
            try:
                x, y = location
                result = self._hippo.recall_from_position(x, y, noise=0.0)
                if result:
                    return [t for t in self._traces
                            if t.location and _dist(t.location, location) <= radius_m]
            except Exception:
                pass
        # 폴백: 거리 필터
        return [t for t in self._traces
                if t.location and _dist(t.location, location) <= radius_m
                and t.current_strength(t_s) > 0.1]

    def recall_by_tag(self, tag: str, t_s: float) -> List[MemoryTrace]:
        return [t for t in self._traces
                if tag in t.tags and t.current_strength(t_s) > 0.05]

    def strongest_recent(self, n: int, t_s: float) -> List[MemoryTrace]:
        ranked = sorted(self._traces, key=lambda tr: tr.current_strength(t_s), reverse=True)
        return ranked[:n]

def _dist(a: Tuple[float,float], b: Tuple[float,float]) -> float:
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)
