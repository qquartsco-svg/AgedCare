"""HandoffProtocol — 플랫폼 간 AI 에이전트 전환 프로토콜.

플랫폼이 바뀌어도 AI의 기억과 케어 상태는 끊기지 않는다.

전환 흐름:
  1. initiate()  — 전환 시작, HandoffToken 발급
  2. [신규 플랫폼 준비 완료 확인]
  3. confirm()   — 전환 확정, AI 에이전트 이동
  4. abort()     — 실패 시 원래 플랫폼으로 복귀 (Fail-safe)

허용 전환 경로:
  PET  ↔  WHEELCHAIR  ↔  CAR
  (직접 PET→CAR 전환 불허: 반드시 WHEELCHAIR 경유)
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Dict, Optional

from ..contracts.schemas import (
    AgentMemory, CareContext, HandoffToken, PlatformType, VitalSigns
)


# ── 허용 전환 경로 ────────────────────────────────────────────────────
ALLOWED_TRANSITIONS = {
    (PlatformType.PET,        PlatformType.WHEELCHAIR),
    (PlatformType.WHEELCHAIR, PlatformType.PET),
    (PlatformType.WHEELCHAIR, PlatformType.CAR),
    (PlatformType.CAR,        PlatformType.WHEELCHAIR),
}


def _token_id(from_p: PlatformType, to_p: PlatformType, t_s: float) -> str:
    raw = f"{from_p}|{to_p}|{t_s:.3f}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class HandoffProtocol:
    """플랫폼 전환 프로토콜 관리자.

    사용법::
        proto = HandoffProtocol()
        token = proto.initiate(ctx, to_platform=PlatformType.WHEELCHAIR)
        if token and proto.confirm(token.token_id):
            new_platform.resume(token)
    """

    def __init__(self):
        self._pending: Dict[str, HandoffToken] = {}

    def initiate(
        self,
        ctx: CareContext,
        to_platform: PlatformType,
    ) -> Optional[HandoffToken]:
        """전환 시작 — HandoffToken 발급.

        허용되지 않는 전환 경로는 None 반환 (안전 차단).
        """
        from_platform = ctx.platform
        if (from_platform, to_platform) not in ALLOWED_TRANSITIONS:
            return None   # 직접 PET→CAR 같은 불허 경로 차단

        tid = _token_id(from_platform, to_platform, ctx.t_s)
        token = HandoffToken(
            token_id=tid,
            from_platform=from_platform,
            to_platform=to_platform,
            agent_memory=ctx.memory,
            vitals_snapshot=ctx.vitals,
            destination=ctx.destination,
            confirmed=False,
            aborted=False,
            t_s=ctx.t_s,
        )
        self._pending[tid] = token
        return token

    def confirm(self, token_id: str) -> Optional[HandoffToken]:
        """전환 확정 — 신규 플랫폼이 준비됐을 때 호출."""
        token = self._pending.get(token_id)
        if token is None or token.aborted:
            return None
        confirmed = HandoffToken(
            token_id=token.token_id,
            from_platform=token.from_platform,
            to_platform=token.to_platform,
            agent_memory=token.agent_memory,
            vitals_snapshot=token.vitals_snapshot,
            destination=token.destination,
            confirmed=True,
            aborted=False,
            t_s=token.t_s,
        )
        self._pending.pop(token_id, None)
        return confirmed

    def abort(self, token_id: str) -> bool:
        """전환 중단 — 원래 플랫폼 유지 (Fail-safe)."""
        token = self._pending.get(token_id)
        if token is None:
            return False
        aborted = HandoffToken(
            token_id=token.token_id,
            from_platform=token.from_platform,
            to_platform=token.to_platform,
            agent_memory=token.agent_memory,
            vitals_snapshot=token.vitals_snapshot,
            destination=token.destination,
            confirmed=False,
            aborted=True,
            t_s=token.t_s,
        )
        self._pending[token_id] = aborted
        return True

    def pending_count(self) -> int:
        return len(self._pending)

    @staticmethod
    def is_allowed(from_p: PlatformType, to_p: PlatformType) -> bool:
        return (from_p, to_p) in ALLOWED_TRANSITIONS
