"""aged_care.monitor — 케어 모니터링 패키지.

CareMonitor (4인수 Ω): 기존 호환성 유지
OmegaMonitor (6인수 Ω): 배터리·인지 인수 추가
BatteryMonitor: 다중 플랫폼 배터리 통합 감시
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

from ..contracts.schemas import (
    AgentMemory, CareContext, EnvironmentFrame, VitalSigns
)


# ── 기존 CareMonitor (4인수) — 하위 호환 유지 ─────────────────────────────

@dataclass
class MonitorResult:
    omega: float
    verdict: str                    # SAFE / CAUTION / WARNING / EMERGENCY
    alerts: List[str]
    emergency: bool
    fall_detected: bool
    medication_due: bool


def _omega_verdict(omega: float) -> str:
    if omega >= 0.80: return "SAFE"
    if omega >= 0.50: return "CAUTION"
    if omega >= 0.25: return "WARNING"
    return "EMERGENCY"


class CareMonitor:
    """생체·환경·피로 복합 모니터 (4인수 Ω).

    플랫폼 독립 — PetPlatform / WheelchairPlatform / CarPlatform 모두 동일하게 호출.

    Ω = ω_vitals × ω_fatigue × ω_environment × ω_medication
    """

    MEDICATION_INTERVAL_S: float = 28800.0   # 8시간 (기본)
    MEAL_INTERVAL_S: float       = 21600.0   # 6시간
    FALL_ACCEL_THRESHOLD: float  = 3.0       # 낙상 감지 가속도 임계 (g)

    def tick(self, ctx: CareContext) -> MonitorResult:
        alerts: List[str] = []
        emergency = False
        fall_detected = False

        # ── 1. 생체 신호 감쇠 ω_vitals ────────────────────────────
        risk = ctx.vitals.risk_score()
        ω_vitals = (0.30 if risk > 0.80
                    else 0.60 if risk > 0.50
                    else 0.85 if risk > 0.25
                    else 1.0)
        if ctx.vitals.is_critical():
            emergency = True
            alerts.append(f"[긴급] 생체신호 위험: HR={ctx.vitals.heart_rate_bpm:.0f} "
                          f"SpO2={ctx.vitals.spo2_pct:.0f}%")

        # ── 2. 피로도 감쇠 ω_fatigue ──────────────────────────────
        fatigue = ctx.memory.fatigue_score
        ω_fatigue = (0.60 if fatigue > 0.80
                     else 0.80 if fatigue > 0.50
                     else 1.0)
        if fatigue > 0.75:
            alerts.append(f"[주의] 피로도 높음: {fatigue:.0%}")

        # ── 3. 환경 감쇠 ω_env ────────────────────────────────────
        ω_env = 1.0
        if ctx.environment.floor_hazard:
            ω_env *= 0.70
            alerts.append("[주의] 바닥 위험 감지 (젖음/경사)")
        if ctx.environment.obstacle_range_m < 0.5:
            ω_env *= 0.50
            alerts.append(f"[위험] 장애물 근접: {ctx.environment.obstacle_range_m:.1f}m")

        # ── 4. 낙상 감지 (임의 가속도 신호 시뮬레이션) ──────────────
        fall_accel = ctx.extra.get("accel_g", 0.0)
        if float(fall_accel) > self.FALL_ACCEL_THRESHOLD:
            fall_detected = True
            emergency = True
            ω_env *= 0.0
            alerts.append("[긴급] 낙상 감지!")

        # ── 5. 투약 알림 ω_medication ─────────────────────────────
        elapsed_med  = ctx.t_s - ctx.memory.last_medication_t_s
        medication_due = bool(ctx.profile.medical.medications
                          and elapsed_med > self.MEDICATION_INTERVAL_S)
        ω_medication = 0.85 if medication_due else 1.0
        if medication_due:
            alerts.append("[알림] 투약 시간이 지났습니다")

        # ── 6. 식사 알림 ──────────────────────────────────────────
        elapsed_meal = ctx.t_s - ctx.memory.last_meal_t_s
        if elapsed_meal > self.MEAL_INTERVAL_S:
            alerts.append("[알림] 식사 시간입니다")

        # ── 7. Ω 종합 ─────────────────────────────────────────────
        omega   = ω_vitals * ω_fatigue * ω_env * ω_medication
        verdict = _omega_verdict(omega)
        if verdict == "EMERGENCY":
            emergency = True

        return MonitorResult(
            omega=omega,
            verdict=verdict,
            alerts=alerts,
            emergency=emergency,
            fall_detected=fall_detected,
            medication_due=medication_due,
        )


# ── 새 확장 모니터 (6인수) ────────────────────────────────────────────────
from .omega import OmegaMonitor, OmegaReport
from .battery import BatteryMonitor

__all__ = [
    "CareMonitor", "MonitorResult",
    "OmegaMonitor", "OmegaReport",
    "BatteryMonitor",
]
