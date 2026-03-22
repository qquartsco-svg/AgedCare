"""PlatformBase — 모든 플랫폼의 공통 인터페이스.

PetPlatform / WheelchairPlatform / CarPlatform 이 상속한다.

설계 원칙:
  - 모든 플랫폼은 동일한 tick() 인터페이스
  - AI 에이전트(CareAgent)를 attach/detach
  - HandoffToken으로 상태 인수인계
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional

from ..contracts.schemas import (
    CareContext, CareDecision, HandoffToken, PlatformType
)


class PlatformBase(ABC):
    """모든 케어 플랫폼의 기본 클래스."""

    platform_type: PlatformType = PlatformType.NONE

    def __init__(self):
        self._agent = None
        self._connected = False

    def attach(self, agent) -> bool:
        """AI 에이전트 연결."""
        self._agent = agent
        self._connected = True
        return True

    def detach(self) -> Optional[object]:
        """AI 에이전트 분리 — 핸드오프 전 호출."""
        agent = self._agent
        self._agent = None
        self._connected = False
        return agent

    @property
    def connected(self) -> bool:
        return self._connected

    @abstractmethod
    def tick(self, ctx: CareContext) -> CareDecision:
        """한 틱 실행 — 플랫폼별 구현."""
        ...

    def resume_from_token(self, token: HandoffToken, ctx: CareContext) -> CareContext:
        """HandoffToken에서 컨텍스트 복원."""
        ctx.memory = token.agent_memory
        if token.vitals_snapshot:
            ctx = CareContext(
                profile=ctx.profile,
                platform=self.platform_type,
                vitals=token.vitals_snapshot,
                environment=ctx.environment,
                memory=token.agent_memory,
                destination=token.destination or ctx.destination,
                t_s=ctx.t_s,
            )
        return ctx
