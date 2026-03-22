"""OmegaMonitor — 확장 Ω 케어 안전 지수 (6인수).

Ω_care = Ω_vitals × Ω_fatigue × Ω_env × Ω_medication × Ω_battery × Ω_cognitive

인수별 계산:
  Ω_vitals     ← VitalSigns.risk_score() (생체신호 위험도)
  Ω_fatigue    ← fatigue_score (피로도)
  Ω_env        ← obstacle_range, floor_hazard (환경 위험)
  Ω_medication ← elapsed_medication_time (투약 준수)
  Ω_battery    ← wheelchair/car battery SoC
  Ω_cognitive  ← CognitiveReport.cognitive_omega (감정/인지)

판정:
  SAFE       Ω ≥ 0.80 — 정상 케어
  CAUTION    Ω ≥ 0.50 — 주의
  WARNING    Ω ≥ 0.25 — 경고 (보호자 알림)
  EMERGENCY  Ω < 0.25 — 긴급 (119 + 보호자)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from ..contracts.schemas import CareContext

@dataclass
class OmegaReport:
    # 6개 Ω 인수
    omega_vitals: float      = 1.0
    omega_fatigue: float     = 1.0
    omega_env: float         = 1.0
    omega_medication: float  = 1.0
    omega_battery: float     = 1.0
    omega_cognitive: float   = 1.0
    # 종합
    omega: float             = 1.0
    verdict: str             = "SAFE"
    alerts: List[str]        = field(default_factory=list)
    emergency: bool          = False
    # 보조
    medication_due: bool     = False
    fall_detected: bool      = False

    def as_dict(self) -> dict:
        return {
            "Ω_vitals":     round(self.omega_vitals, 3),
            "Ω_fatigue":    round(self.omega_fatigue, 3),
            "Ω_env":        round(self.omega_env, 3),
            "Ω_medication": round(self.omega_medication, 3),
            "Ω_battery":    round(self.omega_battery, 3),
            "Ω_cognitive":  round(self.omega_cognitive, 3),
            "Ω_care":       round(self.omega, 3),
            "verdict":      self.verdict,
        }

MEDICATION_INTERVAL_S = 28800.0   # 8시간
MEAL_INTERVAL_S       = 21600.0   # 6시간
FALL_ACCEL_G          = 3.0

def _verdict(omega: float) -> str:
    if omega >= 0.80: return "SAFE"
    if omega >= 0.50: return "CAUTION"
    if omega >= 0.25: return "WARNING"
    return "EMERGENCY"

class OmegaMonitor:
    """확장 Ω 케어 안전 지수 모니터 (6인수).

    기존 CareMonitor(4인수)를 대체/보완.
    배터리(Ω_b) + 인지(Ω_c) 인수 추가.
    """

    def tick(self, ctx: CareContext,
             battery_omega: float = 1.0,
             cognitive_omega: float = 1.0) -> OmegaReport:
        alerts: List[str] = []
        emergency = False
        fall_detected = False

        # ── Ω_vitals ───────────────────────────────────────────────
        if ctx.vitals:
            risk = ctx.vitals.risk_score()
            ω_v = (0.20 if risk > 0.80 else
                   0.55 if risk > 0.50 else
                   0.80 if risk > 0.25 else 1.0)
            if ctx.vitals.is_critical():
                emergency = True
                alerts.append(f"[긴급] 생체신호 위험: HR={ctx.vitals.heart_rate_bpm:.0f} "
                               f"SpO2={ctx.vitals.spo2_pct:.0f}%")
        else:
            ω_v = 0.90   # 데이터 없음 — 약간 불확실

        # ── Ω_fatigue ──────────────────────────────────────────────
        fat = ctx.memory.fatigue_score if ctx.memory else 0.0
        ω_f = (0.55 if fat > 0.85 else
               0.75 if fat > 0.60 else
               0.90 if fat > 0.40 else 1.0)
        if fat > 0.80:
            alerts.append(f"[주의] 피로도 높음: {fat:.0%} — 휴식 권장")

        # ── Ω_env ──────────────────────────────────────────────────
        ω_e = 1.0
        if ctx.environment.floor_hazard:
            ω_e *= 0.70
            alerts.append("[주의] 바닥 위험 감지 (젖음/경사)")
        if ctx.environment.obstacle_range_m < 0.5:
            ω_e *= 0.50
            alerts.append(f"[위험] 장애물 근접: {ctx.environment.obstacle_range_m:.1f}m")
        accel = float(ctx.extra.get("accel_g", 0.0))
        if accel > FALL_ACCEL_G:
            fall_detected = True
            emergency = True
            ω_e = 0.0
            alerts.append("[긴급] 낙상 감지!")

        # ── Ω_medication ───────────────────────────────────────────
        elapsed_med = ctx.t_s - (ctx.memory.last_medication_t_s if ctx.memory else 0.0)
        med_due = bool(ctx.profile.medical.medications and elapsed_med > MEDICATION_INTERVAL_S)
        ω_m = 0.80 if med_due else 1.0
        if med_due:
            alerts.append("[알림] 투약 시간 경과 — 복약 확인 필요")

        elapsed_meal = ctx.t_s - (ctx.memory.last_meal_t_s if ctx.memory else 0.0)
        if elapsed_meal > MEAL_INTERVAL_S:
            alerts.append("[알림] 식사 시간입니다")

        # ── Ω_battery (외부에서 주입) ──────────────────────────────
        ω_b = max(0.0, min(1.0, battery_omega))
        if ω_b < 0.20:
            alerts.append(f"[경고] 배터리 위험: {ω_b*100:.0f}%")

        # ── Ω_cognitive (외부에서 주입) ────────────────────────────
        ω_c = max(0.0, min(1.0, cognitive_omega))
        if ω_c < 0.30:
            alerts.append("[주의] 인지/감정 불안정 감지")

        # ── 종합 Ω ─────────────────────────────────────────────────
        omega = ω_v * ω_f * ω_e * ω_m * ω_b * ω_c
        verdict = _verdict(omega)
        if verdict == "EMERGENCY":
            emergency = True

        return OmegaReport(
            omega_vitals=ω_v, omega_fatigue=ω_f, omega_env=ω_e,
            omega_medication=ω_m, omega_battery=ω_b, omega_cognitive=ω_c,
            omega=omega, verdict=verdict, alerts=alerts,
            emergency=emergency, medication_due=med_due, fall_detected=fall_detected,
        )
