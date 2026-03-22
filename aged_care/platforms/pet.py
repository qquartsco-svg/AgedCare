"""PetPlatform — 홈 AI 펫 (집 내부 케어).

역할:
  - 주인을 따라다니며 생체·환경 모니터링
  - 대화 / 약 알림 / 낙상 감지
  - 외출 감지 시 휠체어로 핸드오프 준비

연동:
  - CareMonitor (생체 판정)
  - CareAgent (AI 대화·결정)
  - 실제 하드웨어: 소형 로봇 / 스마트 스피커 + 카메라
"""
from __future__ import annotations

import math
from typing import Optional

from .base import PlatformBase
from ..contracts.schemas import (
    CareContext, CareDecision, PlatformType
)
from ..monitor import CareMonitor
from ..monitor.omega import OmegaMonitor


class PetPlatform(PlatformBase):
    """홈 AI 펫 플랫폼.

    사용법::
        pet = PetPlatform()
        pet.attach(care_agent)
        decision = pet.tick(ctx)
    """
    platform_type = PlatformType.PET

    def __init__(self):
        super().__init__()
        self._monitor = OmegaMonitor()   # 6인수 Ω (배터리·인지 포함)
        self._follow_distance_m = 1.0    # 주인과 유지할 거리
        self._tick_count = 0

    def tick(self, ctx: CareContext) -> CareDecision:
        """홈 케어 틱.

        파이프라인:
          1. 생체·환경 모니터링
          2. 위험 감지 → 즉각 알림
          3. 루틴 케어 (투약·식사 알림)
          4. 외출 요청 감지 → 휠체어 핸드오프 준비
          5. 동반 이동 (follow)
        """
        self._tick_count += 1
        bat_omega = float(ctx.extra.get("battery_omega", 1.0))
        cog_omega = float(ctx.extra.get("cognitive_omega", 1.0))
        result = self._monitor.tick(ctx, bat_omega, cog_omega)
        decision = CareDecision()

        # ── 1. 긴급 상황 ───────────────────────────────────────────
        if result.emergency:
            decision.emergency = True
            decision.alert = " | ".join(result.alerts)
            decision.speak = "위험 상황이 감지됐어요. 보호자에게 연락할게요."
            decision.action = "emergency"
            return decision

        # ── 2. 낙상 감지 ───────────────────────────────────────────
        if result.fall_detected:
            decision.emergency = True
            decision.speak = "괜찮으세요? 도움이 필요하시면 말씀해주세요."
            decision.alert = "[긴급] 낙상 감지 — 응급 연락 필요"
            return decision

        # ── 3. 루틴 알림 ───────────────────────────────────────────
        if result.medication_due:
            decision.speak = "약 드실 시간이에요. 도와드릴까요?"
            decision.action = "remind"
        elif result.alerts:
            decision.speak = result.alerts[0]
            decision.action = "remind"

        # ── 4. 외출 요청 감지 (환경 or 에이전트 결정) ─────────────
        go_out = ctx.extra.get("go_out", False)
        if go_out and ctx.destination:
            decision.request_handoff = PlatformType.WHEELCHAIR
            decision.speak = "나가실 준비 할게요. 휠체어를 불러드릴게요."
            decision.action = "initiate_handoff"
            return decision

        # ── 5. 정상 — 동반 케어 ────────────────────────────────────
        if not decision.speak:
            greetings = [
                "오늘 기분은 어떠세요?",
                "물 한 잔 드시겠어요?",
                "잠시 쉬어가실까요?",
            ]
            idx = self._tick_count % len(greetings)
            if self._tick_count % 100 == 0:
                decision.speak = greetings[idx]

        decision.action = "follow"
        return decision
