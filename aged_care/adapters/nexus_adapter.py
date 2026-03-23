"""AgedCare -> Nexus / Pharaoh bridge helpers.

현장 케어 상태를 상위 운영/거버넌스 계층이 읽을 수 있는
간결한 executive briefing 신호로 변환한다.

의도:
- AgedCare는 사람 곁의 embodied care runtime
- Nexus는 상위 orchestration conductor
- Kemet / Pharaoh는 보고와 칙령 계층

따라서 이 모듈은 AgedCare 내부 상태를
`업무 보고 가능한 형태`로 올리는 얇은 브리지 역할만 담당한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Tuple

from ..contracts.schemas import CareContext, CareDecision, PlatformType, SafetyState


@dataclass(frozen=True)
class AgedCareExecutiveBrief:
    """사용자/보호자/CEO 보고용 요약 신호."""

    person_id: str
    person_name: str
    current_platform: str
    omega_care: float
    verdict: str
    mission_completion: float
    emergency: bool
    vitals_risk: float
    fatigue_score: float
    cognitive_load: float
    alert_level: float
    pending_alerts: Tuple[str, ...] = ()
    recommended_actions: Tuple[str, ...] = ()
    destination: Optional[Tuple[float, float]] = None


@dataclass(frozen=True)
class AgedCareNexusSignal:
    """Nexus/Aton/Athena가 읽는 표준화 외부 신호."""

    care_omega: float
    care_emergency: bool
    care_verdict: str
    care_load: float
    mission_completion: float
    flags: Dict[str, bool] = field(default_factory=dict)
    notes: Tuple[str, ...] = ()


def _decision_actions(decision: Optional[CareDecision]) -> Tuple[str, ...]:
    if decision is None:
        return ()
    actions = []
    if decision.action and decision.action != "idle":
        actions.append(decision.action)
    if decision.request_handoff:
        actions.append(f"handoff:{decision.request_handoff.value}")
    if decision.alert:
        actions.append("alert")
    if decision.emergency:
        actions.append("emergency")
    return tuple(actions)


def build_executive_brief(
    *,
    ctx: CareContext,
    safety: Optional[SafetyState] = None,
    decision: Optional[CareDecision] = None,
) -> AgedCareExecutiveBrief:
    """CareContext를 경영/거버넌스 보고 형태로 축약."""
    safety = safety or SafetyState()
    destination = ctx.destination or (
        ctx.mission_state.current_destination if hasattr(ctx, "mission_state") and ctx.mission_state else None
    )
    pending_alerts = tuple(ctx.memory.alerts_today[-5:])
    mission_completion = 0.0
    if ctx.extra.get("mission_completion") is not None:
        mission_completion = float(ctx.extra["mission_completion"])
    elif ctx.extra.get("mission_state_ratio") is not None:
        mission_completion = float(ctx.extra["mission_state_ratio"])

    cognitive_load = ctx.person_state.cognitive_load if ctx.person_state else 0.0
    alert_level = ctx.person_state.alert_level if ctx.person_state else ctx.vitals.alert_level

    return AgedCareExecutiveBrief(
        person_id=ctx.profile.person_id,
        person_name=ctx.profile.name,
        current_platform=ctx.platform.value,
        omega_care=float(safety.omega),
        verdict=str(safety.verdict),
        mission_completion=max(0.0, min(1.0, mission_completion)),
        emergency=bool(decision.emergency) if decision else bool(safety.emergency_triggered),
        vitals_risk=float(ctx.vitals.risk_score()),
        fatigue_score=float(ctx.memory.fatigue_score),
        cognitive_load=float(cognitive_load),
        alert_level=float(alert_level),
        pending_alerts=pending_alerts,
        recommended_actions=_decision_actions(decision),
        destination=destination,
    )


def executive_brief_to_nexus_signal(
    brief: AgedCareExecutiveBrief,
) -> AgedCareNexusSignal:
    """Executive brief를 Nexus 외부 신호로 변환."""
    care_load = min(
        1.0,
        0.35 * brief.vitals_risk
        + 0.25 * brief.fatigue_score
        + 0.20 * brief.cognitive_load
        + 0.20 * (1.0 - brief.alert_level),
    )
    flags = {
        "care_emergency": brief.emergency,
        "care_warning": brief.omega_care < 0.50,
        "care_fragile": brief.omega_care < 0.25,
        "handoff_active": any(a.startswith("handoff:") for a in brief.recommended_actions),
        "vitals_critical": brief.vitals_risk >= 0.80,
    }
    notes = tuple(
        n for n in (
            f"platform={brief.current_platform}",
            f"verdict={brief.verdict}",
            f"mission={brief.mission_completion:.0%}",
        )
    )
    return AgedCareNexusSignal(
        care_omega=brief.omega_care,
        care_emergency=brief.emergency,
        care_verdict=brief.verdict,
        care_load=care_load,
        mission_completion=brief.mission_completion,
        flags=flags,
        notes=notes,
    )


def executive_brief_to_pharaoh_report(
    brief: AgedCareExecutiveBrief,
) -> Dict[str, object]:
    """Pharaoh/Kemet 쪽 보고 포맷으로 변환."""
    return {
        "subject_type": "aged_care_case",
        "person_id": brief.person_id,
        "person_name": brief.person_name,
        "omega_care": round(brief.omega_care, 4),
        "verdict": brief.verdict,
        "platform": brief.current_platform,
        "mission_completion": round(brief.mission_completion, 4),
        "emergency": brief.emergency,
        "vitals_risk": round(brief.vitals_risk, 4),
        "fatigue_score": round(brief.fatigue_score, 4),
        "cognitive_load": round(brief.cognitive_load, 4),
        "alert_level": round(brief.alert_level, 4),
        "pending_alerts": list(brief.pending_alerts),
        "recommended_actions": list(brief.recommended_actions),
        "destination": brief.destination,
        "pharaoh_attention_required": bool(brief.emergency or brief.omega_care < 0.50),
        "health_campaign_recommended": bool(brief.vitals_risk > 0.50 or brief.omega_care < 0.50),
    }


def executive_brief_lines(brief: AgedCareExecutiveBrief) -> Tuple[str, ...]:
    """사람이 읽는 짧은 보고문 생성."""
    lines = [
        f"{brief.person_name} | platform={brief.current_platform} | Ω={brief.omega_care:.3f} ({brief.verdict})",
        f"mission={brief.mission_completion:.0%} | vitals_risk={brief.vitals_risk:.2f} | fatigue={brief.fatigue_score:.2f}",
    ]
    if brief.emergency:
        lines.append("EMERGENCY: immediate executive attention required")
    if brief.pending_alerts:
        lines.append("alerts: " + " | ".join(brief.pending_alerts[:3]))
    if brief.recommended_actions:
        lines.append("actions: " + ", ".join(brief.recommended_actions))
    return tuple(lines)


def merge_briefs(briefs: Iterable[AgedCareExecutiveBrief]) -> AgedCareNexusSignal:
    """복수 케어 대상자의 보고를 하나의 상위 운영 신호로 집계."""
    items = tuple(briefs)
    if not items:
        return AgedCareNexusSignal(
            care_omega=1.0,
            care_emergency=False,
            care_verdict="HEALTHY",
            care_load=0.0,
            mission_completion=1.0,
            flags={},
            notes=(),
        )

    omega = min(b.omega_care for b in items)
    emergency = any(b.emergency for b in items)
    load = sum(executive_brief_to_nexus_signal(b).care_load for b in items) / len(items)
    mission = sum(b.mission_completion for b in items) / len(items)
    return AgedCareNexusSignal(
        care_omega=omega,
        care_emergency=emergency,
        care_verdict="CRITICAL" if omega < 0.25 else "WARNING" if omega < 0.50 else "STABLE",
        care_load=min(1.0, load),
        mission_completion=max(0.0, min(1.0, mission)),
        flags={
            "care_emergency": emergency,
            "multi_case": len(items) > 1,
            "care_warning": omega < 0.50,
        },
        notes=tuple(f"{b.person_name}:{b.verdict}" for b in items[:5]),
    )
