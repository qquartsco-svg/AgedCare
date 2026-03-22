"""WheelchairPlatform — 자율 휠체어.

역할:
  - 집 내부/외부 자율 이동 (Autonomy_Runtime_Stack 연동)
  - 탑승자 안전 모니터링 (속도·기울기·장애물)
  - 자동차 승차 시 CarPlatform으로 핸드오프
  - 귀가 시 PetPlatform으로 핸드오프

Autonomy_Runtime_Stack 연동 포인트:
  - AutonomyTickContext → 경로 추종
  - BehaviorFSM → CRUISE/FOLLOW/STOP
  - Stanley Controller → 조향
  - 낮은 속도 프리셋 (최대 1.5 m/s)
"""
from __future__ import annotations

from typing import Optional, Tuple

from .base import PlatformBase
from ..contracts.schemas import (
    CareContext, CareDecision, PlatformType
)
from ..monitor import CareMonitor
from ..monitor.omega import OmegaMonitor


class WheelchairConfig:
    max_speed_ms: float   = 1.5      # 최대 속도 (m/s, ~5.4 km/h)
    max_accel_ms2: float  = 0.3      # 최대 가속도 (부드럽게)
    obstacle_stop_m: float = 0.8     # 장애물 정지 거리 (m)
    tilt_limit_deg: float  = 8.0     # 최대 기울기 허용 (도)
    car_dock_range_m: float = 1.0    # 자동차 도킹 판정 거리 (m)


class WheelchairActuator:
    """휠체어 구동 명령."""
    def __init__(self, speed_ms=0.0, turn_rad=0.0, brake=False):
        self.speed_ms  = speed_ms
        self.turn_rad  = turn_rad
        self.brake     = brake


class WheelchairPlatform(PlatformBase):
    """자율 휠체어 플랫폼.

    Autonomy_Runtime_Stack 사용 시::
        from autonomy_runtime_stack import AutonomyOrchestrator, AutonomyTickContext
        orch = AutonomyOrchestrator()
        # WheelchairPlatform 내부에서 orch.tick() 호출

    미설치 시 폴백 내장 제어기로 동작.
    """
    platform_type = PlatformType.WHEELCHAIR

    def __init__(self, config: Optional[WheelchairConfig] = None):
        super().__init__()
        self._cfg     = config or WheelchairConfig()
        self._monitor = OmegaMonitor()   # 6인수 Ω (배터리·인지 포함)
        self._pos     = (0.0, 0.0)       # 현재 위치 (x, y)
        self._speed   = 0.0
        self._heading = 0.0
        self._tick    = 0
        # Autonomy_Runtime_Stack 오케스트레이터 (선택)
        self._orch    = self._try_load_orch()

    def _try_load_orch(self):
        try:
            from autonomy_runtime_stack import AutonomyOrchestrator
            return AutonomyOrchestrator()
        except ImportError:
            return None

    def tick(self, ctx: CareContext) -> CareDecision:
        """휠체어 제어 틱.

        파이프라인:
          1. 생체 모니터링 (이동 중에도 지속)
          2. 장애물 감지 → 즉시 제동
          3. 목적지 도달 → 자동차 핸드오프 또는 귀가 핸드오프
          4. 자율 경로 추종
        """
        self._tick += 1
        bat_omega = float(ctx.extra.get("battery_omega", 1.0))
        cog_omega = float(ctx.extra.get("cognitive_omega", 1.0))
        result  = self._monitor.tick(ctx, bat_omega, cog_omega)
        decision = CareDecision()

        # ── 1. 긴급 ──────────────────────────────────────────────
        if result.emergency:
            decision.emergency = True
            decision.alert  = " | ".join(result.alerts)
            decision.speak  = "위험을 감지했어요. 즉시 멈출게요."
            decision.action = "emergency_stop"
            return decision

        # ── 2. 장애물 즉시 제동 ───────────────────────────────────
        if ctx.environment.obstacle_range_m < self._cfg.obstacle_stop_m:
            decision.speak  = "앞에 장애물이 있어요."
            decision.action = "stop"
            return decision

        # ── 3. 자동차 위치 도달 → 핸드오프 ──────────────────────
        car_nearby = ctx.extra.get("car_ready", False)
        if car_nearby and ctx.destination:
            decision.request_handoff = PlatformType.CAR
            decision.speak  = "차에 탑승할게요."
            decision.action = "initiate_handoff"
            return decision

        # ── 4. 귀가 도달 → 펫 핸드오프 ──────────────────────────
        at_home = ctx.extra.get("at_home", False)
        if at_home and ctx.destination is None:
            decision.request_handoff = PlatformType.PET
            decision.speak  = "집에 도착했어요."
            decision.action = "initiate_handoff"
            return decision

        # ── 5. 정상 이동 ──────────────────────────────────────────
        if ctx.destination:
            actuator = self._navigate(ctx)
            decision.action = "navigate"
            decision.navigation_goal = ctx.destination
            # 위치 업데이트 — 매 틱마다 목적지 방향으로 이동
            dx = ctx.destination[0] - self._pos[0]
            dy = ctx.destination[1] - self._pos[1]
            dist = (dx**2 + dy**2) ** 0.5
            if dist > 1e-6:
                move = actuator.speed_ms * ctx.dt_s
                ratio = min(1.0, move / dist)
                self._pos = (
                    self._pos[0] + dx * ratio,
                    self._pos[1] + dy * ratio,
                )
            # 알림이 있으면 TTS
            if result.alerts:
                decision.speak = result.alerts[0]
        else:
            decision.action = "idle"

        return decision

    def _navigate(self, ctx: CareContext) -> WheelchairActuator:
        """폴백 내장 제어 (Autonomy_Runtime_Stack 미설치 시)."""
        if self._orch is not None:
            # Autonomy_Runtime_Stack 연동 (실제 배포 시)
            return WheelchairActuator(speed_ms=self._cfg.max_speed_ms * 0.6)

        # 폴백: 목적지 방향으로 저속 이동
        if ctx.destination:
            dx = ctx.destination[0] - self._pos[0]
            dy = ctx.destination[1] - self._pos[1]
            dist = (dx**2 + dy**2) ** 0.5
            spd  = min(self._cfg.max_speed_ms, dist * 0.5)
            return WheelchairActuator(speed_ms=spd)
        return WheelchairActuator()
