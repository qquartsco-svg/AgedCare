"""CarPlatform — 자율 자동차.

역할:
  - 목적지까지 자율주행 (SYD_DRIFT / Autonomy_Runtime_Stack 연동)
  - 탑승자(노인) 안전 모니터링 (충격·급감속·생체)
  - 목적지 도착 시 WheelchairPlatform으로 핸드오프
  - AI 에이전트는 차 안에서도 계속 케어

SYD_DRIFT 연동 포인트:
  - SydDriftRunner → 도심 자율주행
  - CommandChain → SHA-256 감사 로그 (이동 이력)
  - CityRoadPreset → 노인 보호 속도 프리셋 (낮은 가속·부드러운 제동)
"""
from __future__ import annotations

from typing import Optional

from .base import PlatformBase
from ..contracts.schemas import (
    CareContext, CareDecision, PlatformType
)
from ..monitor import CareMonitor


class CarConfig:
    """노인 동승 자율주행 설정 — 일반 자율주행보다 보수적."""
    max_speed_ms: float   = 13.89    # 50 km/h (도심 제한)
    max_accel_ms2: float  = 1.5      # 부드러운 가속 (일반의 절반)
    max_decel_ms2: float  = 2.0      # 부드러운 제동
    comfort_speed_ms: float = 8.33   # 30 km/h (기본 순항)
    jerk_limit: float     = 0.5      # 급가속 제한 (m/s³)
    arrival_range_m: float = 10.0    # 도착 판정 거리 (m)


class CarPlatform(PlatformBase):
    """자율 자동차 플랫폼.

    SYD_DRIFT 사용 시::
        from syd_drift import SydDriftRunner, RunnerConfig, get_preset
        runner = SydDriftRunner(preset=get_preset("cbd"), ...)
        # CarPlatform 내부에서 runner 사용

    미설치 시 폴백 내장 제어기로 동작.
    """
    platform_type = PlatformType.CAR

    def __init__(self, config: Optional[CarConfig] = None):
        super().__init__()
        self._cfg     = config or CarConfig()
        self._monitor = CareMonitor()
        self._pos     = (0.0, 0.0)
        self._speed   = 0.0
        self._tick    = 0
        self._runner  = self._try_load_runner()

    def _try_load_runner(self):
        try:
            from syd_drift import SydDriftRunner, RunnerConfig, get_preset
            # 노인 케어용 보수적 프리셋 (CBD 저속)
            return SydDriftRunner(
                preset=get_preset("cbd"),
                config=RunnerConfig(steps=9999, dt_s=0.05, chain_enabled=True),
            )
        except ImportError:
            return None

    def tick(self, ctx: CareContext) -> CareDecision:
        """자동차 제어 틱.

        파이프라인:
          1. 생체 모니터링 (이동 중 지속)
          2. 충격 감지 → 비상 정차 + 보호자 알림
          3. 목적지 도착 → 휠체어 핸드오프
          4. 자율주행 (SYD_DRIFT 또는 폴백)
          5. 차 내 케어 대화
        """
        self._tick += 1
        result   = self._monitor.tick(ctx)
        decision = CareDecision()

        # ── 1. 긴급 (생체 이상) ───────────────────────────────────
        if result.emergency:
            decision.emergency = True
            decision.alert  = " | ".join(result.alerts)
            decision.speak  = "이상 징후가 감지됐어요. 가장 가까운 병원으로 이동할게요."
            decision.action = "emergency_route"
            return decision

        # ── 2. 충격 감지 (사고/급제동) ────────────────────────────
        shock_g = float(ctx.extra.get("shock_g", 0.0))
        if shock_g > 2.0:
            decision.emergency = True
            decision.alert  = f"[긴급] 충격 감지: {shock_g:.1f}g — 보호자 연락"
            decision.speak  = "괜찮으세요? 지금 바로 확인할게요."
            decision.action = "emergency_stop"
            return decision

        # ── 3. 목적지 도착 → 휠체어 핸드오프 ─────────────────────
        arrived = ctx.extra.get("arrived", False)
        if arrived:
            decision.request_handoff = PlatformType.WHEELCHAIR
            decision.speak  = "도착했어요. 휠체어 내려드릴게요."
            decision.action = "initiate_handoff"
            return decision

        # ── 4. 자율주행 실행 ──────────────────────────────────────
        if ctx.destination:
            decision.action = "navigate"
            decision.navigation_goal = ctx.destination
            if self._runner is not None:
                # SYD_DRIFT 실제 연동 (설치된 경우)
                pass  # runner.step() 호출 위치
        else:
            decision.action = "idle"

        # ── 5. 차 내 케어 ─────────────────────────────────────────
        if result.medication_due and not decision.speak:
            decision.speak = "도착하면 약 드시는 거 잊지 마세요."
        elif self._tick % 200 == 0 and not decision.speak:
            decision.speak = "불편한 건 없으세요? 온도나 속도 조절해 드릴게요."

        return decision
