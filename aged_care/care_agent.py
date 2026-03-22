"""CareAgent — 지속 AI 에이전트.

하드웨어(플랫폼)가 바뀌어도 AI 에이전트는 하나다.
PetPlatform → WheelchairPlatform → CarPlatform → ... 어디서든 같은 에이전트.

역할:
  - 케어 프로파일 보유 (주인 정보 + 기억)
  - 각 플랫폼의 CareDecision을 상위에서 통합
  - 핸드오프 조율 (HandoffProtocol 호출)
  - 하루 루틴 스케줄 관리

설계: 이 에이전트는 Claude API (Anthropic) 연동 확장 포인트를 갖는다.
  현재는 규칙 기반 폴백으로 동작.
  future: CareAgent._llm_decide() → anthropic.messages.create()
"""
from __future__ import annotations

import math
from typing import Optional

from .contracts.schemas import (
    AgentMemory, CareContext, CareDecision, CareProfile,
    HandoffToken, PlatformType, VitalSigns
)
from .handoff.protocol import HandoffProtocol
from .platforms.base import PlatformBase
from .platforms.pet import PetPlatform
from .platforms.wheelchair import WheelchairPlatform
from .platforms.car import CarPlatform
from .monitor import CareMonitor


class CareAgent:
    """지속 AI 케어 에이전트.

    사용법::
        profile = CareProfile(person_id="001", name="홍길동", age=78)
        agent = CareAgent(profile)

        # 집에서 시작 (펫 모드)
        ctx = agent.start_session()
        for _ in range(100):
            ctx, decision = agent.tick(ctx)

        # 외출 → 휠체어 전환
        ctx.extra["go_out"] = True
        ctx.destination = (100.0, 200.0)
        ctx, decision = agent.tick(ctx)  # → request_handoff = WHEELCHAIR

        # 핸드오프 실행
        agent.execute_handoff(ctx, decision)
    """

    def __init__(self, profile: CareProfile):
        self.profile   = profile
        self.memory    = AgentMemory()
        self._proto    = HandoffProtocol()
        self._monitor  = CareMonitor()

        # 플랫폼 인스턴스
        self._platforms = {
            PlatformType.PET:        PetPlatform(),
            PlatformType.WHEELCHAIR: WheelchairPlatform(),
            PlatformType.CAR:        CarPlatform(),
        }
        self._current_platform: PlatformType = PlatformType.PET
        self._platforms[PlatformType.PET].attach(self)

        self._t_s = 0.0
        self._pending_token: Optional[HandoffToken] = None

    @property
    def current_platform(self) -> PlatformType:
        return self._current_platform

    # ── 세션 시작 ─────────────────────────────────────────────────────

    def start_session(self) -> CareContext:
        return CareContext(
            profile=self.profile,
            platform=self._current_platform,
            memory=self.memory,
            t_s=self._t_s,
        )

    # ── 메인 틱 ──────────────────────────────────────────────────────

    def tick(self, ctx: CareContext) -> tuple[CareContext, CareDecision]:
        """에이전트 한 틱.

        1. 컨텍스트 동기화
        2. 현재 플랫폼 tick()
        3. 핸드오프 요청 처리
        4. 기억 업데이트
        """
        self._t_s += ctx.dt_s
        ctx.t_s    = self._t_s
        ctx.platform = self._current_platform
        ctx.memory   = self.memory

        # 현재 플랫폼 실행
        platform = self._platforms[self._current_platform]
        decision = platform.tick(ctx)

        # 핸드오프 요청 처리
        if decision.request_handoff and not self._pending_token:
            token = self._proto.initiate(ctx, decision.request_handoff)
            if token:
                self._pending_token = token
                decision.action = "handoff_initiated"

        # 기억 업데이트 (피로 누적 등)
        self._update_memory(ctx, decision)

        return ctx, decision

    # ── 핸드오프 실행 ─────────────────────────────────────────────────

    def execute_handoff(self, ctx: CareContext) -> bool:
        """대기 중인 핸드오프 확정 실행.

        Returns True if handoff completed, False if aborted.
        """
        if not self._pending_token:
            return False

        confirmed = self._proto.confirm(self._pending_token.token_id)
        if not confirmed:
            self._pending_token = None
            return False

        # 기존 플랫폼에서 분리
        old_platform = self._platforms[self._current_platform]
        old_platform.detach()

        # 새 플랫폼으로 이동
        new_type     = confirmed.to_platform
        new_platform = self._platforms[new_type]
        new_platform.attach(self)

        # 컨텍스트 복원
        new_platform.resume_from_token(confirmed, ctx)

        self._current_platform = new_type
        self._pending_token    = None
        return True

    def abort_handoff(self) -> bool:
        """핸드오프 중단 — 원래 플랫폼 유지."""
        if not self._pending_token:
            return False
        self._proto.abort(self._pending_token.token_id)
        self._pending_token = None
        return True

    # ── 기억 업데이트 ─────────────────────────────────────────────────

    def _update_memory(self, ctx: CareContext, decision: CareDecision) -> None:
        # 피로도 누적 (이동 중 더 빠르게)
        if ctx.platform == PlatformType.PET:
            self.memory.fatigue_score = min(1.0, self.memory.fatigue_score + 0.00001)
        else:
            self.memory.fatigue_score = min(1.0, self.memory.fatigue_score + 0.00003)

        # 투약 기록
        if "약 복용" in (decision.speak or ""):
            self.memory.last_medication_t_s = self._t_s

        # 대화 이력 기록
        if decision.speak:
            self.memory.conversation_history.append(
                f"[{self._t_s:.1f}s][{ctx.platform}] {decision.speak}"
            )
            # 최근 50개만 유지
            if len(self.memory.conversation_history) > 50:
                self.memory.conversation_history = self.memory.conversation_history[-50:]

        # 알림 누적
        if decision.alert:
            self.memory.alerts_today.append(decision.alert)

    # ── Claude API 연동 확장 포인트 ────────────────────────────────────

    def _llm_decide(self, ctx: CareContext) -> Optional[str]:
        """Claude API 연동 포인트 (미래 확장).

        현재: 규칙 기반 폴백
        향후: anthropic.messages.create() 호출

        예시::
            import anthropic
            client = anthropic.Anthropic()
            message = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=256,
                system=f"당신은 {ctx.profile.name}님의 AI 케어 보조입니다.",
                messages=[{"role": "user", "content": care_summary(ctx)}]
            )
            return message.content[0].text
        """
        return None   # 폴백: 규칙 기반 사용

    # ── 상태 요약 ─────────────────────────────────────────────────────

    def summary(self) -> str:
        lines = [
            f"[CareAgent] {self.profile.name} (만 {self.profile.age}세)",
            f"  현재 플랫폼: {self._current_platform.value}",
            f"  피로도:     {self.memory.fatigue_score:.1%}",
            f"  오늘 알림:  {len(self.memory.alerts_today)}건",
            f"  대화 이력:  {len(self.memory.conversation_history)}개",
            f"  운영 시간:  {self._t_s:.0f}초",
        ]
        return "\n".join(lines)
