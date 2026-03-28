"""AgedCare ↔ 휠체어 기초 물리·FSM 연동.

AgedCare의 **이동 바디**가 휠체어일 때, 케어 맥락·설정으로부터:

1. `vehicle_platform_foundation` — 질량·축하중·접지/동력 예산 (`assess_platform`)
2. `wheelchair_transform_system` — 착석 기준 FSM 스냅샷 (`run_phase_tick`, 저속 자율주행·기립 게이트의 하위층)

을 **선택적으로** 호출한다. 패키지가 PYTHONPATH에 없으면 `physics_available` / `fsm_available` 만 False 로 두고
폴백한다 (AgedCare 단독 배포 유지).
"""
from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.schemas import CareContext
    from ..platforms.wheelchair import WheelchairConfig


def mobility_physics_available() -> bool:
    try:
        import vehicle_platform_foundation  # noqa: F401
        return True
    except ImportError:
        return False


def mobility_fsm_available() -> bool:
    try:
        import wheelchair_transform_system  # noqa: F401
        return True
    except ImportError:
        return False


def _hardware_snapshot_from_ctx(ctx: "CareContext", cfg: "WheelchairConfig") -> Any:
    from wheelchair_transform_system.contracts import HardwareSnapshot

    ts = int(ctx.t_s * 1000.0)
    v_wheel = float(ctx.extra.get("wheel_velocity_m_s", 0.0))
    brake = bool(ctx.extra.get("brake_engaged", True))
    return HardwareSnapshot(
        timestamp_ms=ts,
        wheel_velocity_m_s=v_wheel,
        brake_engaged=brake,
        seat_weight_ratio=float(ctx.extra.get("seat_weight_ratio", 1.0)),
        stand_frame_deployed_ratio=float(ctx.extra.get("stand_frame_deployed_ratio", 0.0)),
        estop_active=bool(ctx.extra.get("estop_active", False)),
        proximity_clear_mm=float(ctx.extra.get("proximity_clear_mm", 200.0)),
    )


def evaluate_wheelchair_mobility_foundation(
    ctx: "CareContext",
    cfg: "WheelchairConfig",
) -> Dict[str, Any]:
    """
    휠체어를 지상 2축·4접촉 플랫폼으로 읽어 기초 물리 스크리닝 + (가능 시) 착석 FSM 프로브.

    반환 dict는 `CareContext.extra["wheelchair_mobility_layer"]` 등에 넣기 좋게 평탄화한다.
    """
    out: Dict[str, Any] = {
        "physics_available": False,
        "fsm_available": False,
        "suggested_max_speed_ms": cfg.max_speed_ms,
        "slope_grade_deg": float(ctx.extra.get("slope_grade_deg", 0.0)),
    }

    gross_kg = cfg.rider_mass_kg + cfg.chair_frame_mass_kg

    # ── 1) Vehicle platform foundation (4WD 비유 물리 분모) ─────────────────
    if mobility_physics_available():
        from vehicle_platform_foundation import (
            ChassisSpec,
            IntegrationInputs,
            PowertrainSpec,
            TireSpec,
            TorqueSplit4WD,
            assess_platform,
        )

        tire = TireSpec(
            rolling_radius_m=cfg.tire_rolling_radius_m,
            mu_long_peak=cfg.tire_mu_long,
            rolling_resistance_coef=cfg.rolling_resistance_coef,
        )
        chassis = ChassisSpec(
            kind="powered_wheelchair_base",
            curb_mass_kg=gross_kg,
            payload_max_kg=0.0,
            wheelbase_m=cfg.wheelbase_m,
            track_front_m=cfg.track_width_m,
            track_rear_m=cfg.track_width_m,
            cg_height_m=cfg.cg_height_m,
            cg_longitudinal_from_rear_axle_m=cfg.cg_longitudinal_from_rear_m,
            tire=tire,
            aero_cd=cfg.aero_cd,
            frontal_area_m2=cfg.frontal_area_m2,
        )
        pt = PowertrainSpec(
            kind="bev",
            peak_torque_nm=cfg.motor_peak_torque_nm,
            peak_power_kw=cfg.motor_peak_power_kw,
            max_motor_shaft_rpm=cfg.motor_max_shaft_rpm,
            overall_drive_ratio=cfg.overall_drive_ratio,
            drivetrain_efficiency_0_1=float(cfg.drivetrain_efficiency),
        )
        inp = IntegrationInputs(
            gross_mass_kg=gross_kg,
            shaft_rpm=cfg.physics_assess_shaft_rpm,
            split=TorqueSplit4WD(front_axle_fraction=cfg.torque_front_fraction),
        )
        rep = assess_platform(chassis, pt, inp)
        out["physics_available"] = True
        out["governing_accel_ms2"] = rep.governing_accel_ms2
        out["traction_limited_accel_ms2"] = rep.traction_limited_accel_ms2
        out["power_limited_accel_ms2"] = rep.power_limited_accel_ms2
        out["static_front_axle_load_n"] = rep.static_front_axle_load_n
        out["static_rear_axle_load_n"] = rep.static_rear_axle_load_n
        out["wheel_torque_peak_nm"] = rep.wheel_torque_peak_nm
        out["physics_notes"] = rep.notes
        # 케어 보수: 접지·동력 상한이 낮으면 상한 속도를 깎는다.
        gov = rep.governing_accel_ms2
        cap = min(cfg.max_speed_ms, max(0.2, min(cfg.max_speed_ms, 0.35 + gov * 2.0)))
        out["suggested_max_speed_ms"] = float(cap)

    # ── 2) Wheelchair transform FSM (저속 HAL / 기립·전이 하위층) ─────────
    if mobility_fsm_available():
        from wheelchair_transform_system import AiIntent, TransformPhase, run_phase_tick

        snap = _hardware_snapshot_from_ctx(ctx, cfg)
        tick = run_phase_tick(TransformPhase.SEATED_IDLE, AiIntent(kind="none"), snap)
        out["fsm_available"] = True
        out["fsm_phase"] = tick.phase.value
        out["fsm_mode"] = tick.mode
        out["fsm_blocked_reason"] = tick.blocked_reason
        out["fsm_ato_label"] = tick.ato_phase_label

    return out
