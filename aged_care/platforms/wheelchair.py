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
from ..bridges.wheelchair_physics import evaluate_wheelchair_mobility_foundation


class WheelchairConfig:
    """휠체어 운행 + 00_BRAIN 기초 물리(`vehicle_platform_foundation`) 파라미터."""

    max_speed_ms: float = 1.5
    max_accel_ms2: float = 0.3
    obstacle_stop_m: float = 0.8
    tilt_limit_deg: float = 8.0
    car_dock_range_m: float = 1.0

    rider_mass_kg: float = 70.0
    chair_frame_mass_kg: float = 85.0
    wheelbase_m: float = 0.68
    track_width_m: float = 0.58
    cg_height_m: float = 0.38
    cg_longitudinal_from_rear_m: float = 0.34
    tire_rolling_radius_m: float = 0.14
    tire_mu_long: float = 0.72
    rolling_resistance_coef: float = 0.018
    aero_cd: float = 0.95
    frontal_area_m2: float = 0.55
    motor_peak_torque_nm: float = 28.0
    motor_peak_power_kw: float = 0.75
    motor_max_shaft_rpm: float = 2500.0
    overall_drive_ratio: float = 14.0
    drivetrain_efficiency: float = 0.86
    physics_assess_shaft_rpm: float = 600.0
    torque_front_fraction: float = 0.5


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
        self._speed_cap_ms = self._cfg.max_speed_ms
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
        # ── 0. 휠체어 기초 물리·FSM (AgedCare 이동 바디 = 휠체어 실체) ──
        mob = evaluate_wheelchair_mobility_foundation(ctx, self._cfg)
        ctx.extra["wheelchair_mobility_layer"] = mob
        self._speed_cap_ms = float(mob.get("suggested_max_speed_ms", self._cfg.max_speed_ms))

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
            spd = min(self._cfg.max_speed_ms * 0.6, self._speed_cap_ms)
            return WheelchairActuator(speed_ms=spd)

        # 폴백: 목적지 방향으로 저속 이동
        if ctx.destination:
            dx = ctx.destination[0] - self._pos[0]
            dy = ctx.destination[1] - self._pos[1]
            dist = (dx**2 + dy**2) ** 0.5
            spd  = min(self._cfg.max_speed_ms, dist * 0.5)
            spd = min(spd, self._speed_cap_ms)
            return WheelchairActuator(speed_ms=spd)
        return WheelchairActuator()
