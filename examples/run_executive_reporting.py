"""AgedCare executive reporting demo.

현장 케어 상태를 Nexus/Pharaoh가 읽을 수 있는
업무 보고 형태로 축약하는 예제.
"""

from __future__ import annotations

import os
import sys
from pprint import pprint


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from aged_care import (  # noqa: E402
    AgentMemory,
    CareContext,
    CareDecision,
    CareProfile,
    MedicalInfo,
    PersonState,
    PlatformType,
    SafetyState,
    VitalSigns,
    build_executive_brief,
    executive_brief_lines,
    executive_brief_to_nexus_signal,
    executive_brief_to_pharaoh_report,
    merge_briefs,
)


def make_case(
    *,
    person_id: str,
    name: str,
    omega: float,
    verdict: str,
    emergency: bool = False,
) -> tuple[CareContext, SafetyState, CareDecision]:
    ctx = CareContext(
        profile=CareProfile(
            person_id=person_id,
            name=name,
            age=78,
            medical=MedicalInfo(fall_risk=0.4),
        ),
        platform=PlatformType.WHEELCHAIR,
        memory=AgentMemory(
            fatigue_score=0.45 if emergency else 0.25,
            alerts_today=["낙상 위험 감지"] if emergency else ["투약 알림"],
        ),
        vitals=VitalSigns(
            heart_rate_bpm=104 if emergency else 82,
            spo2_pct=91 if emergency else 97,
            body_temp_c=37.4 if emergency else 36.5,
            alert_level=0.62 if emergency else 0.84,
        ),
    )
    ctx.person_state = PersonState(
        cognitive_load=0.52 if emergency else 0.28,
        alert_level=0.62 if emergency else 0.84,
    )
    ctx.extra["mission_completion"] = 0.4 if emergency else 0.9
    safety = SafetyState(
        omega=omega,
        verdict=verdict,
        emergency_triggered=emergency,
    )
    decision = CareDecision(
        action="assist" if not emergency else "stabilize",
        request_handoff=PlatformType.CAR if emergency else None,
        alert="응급 주의" if emergency else "",
        emergency=emergency,
    )
    return ctx, safety, decision


def main() -> None:
    primary_ctx, primary_safety, primary_decision = make_case(
        person_id="CEO-001",
        name="김대표",
        omega=0.43,
        verdict="WARNING",
        emergency=True,
    )
    support_ctx, support_safety, support_decision = make_case(
        person_id="OPS-002",
        name="이부장",
        omega=0.82,
        verdict="SAFE",
        emergency=False,
    )

    primary = build_executive_brief(
        ctx=primary_ctx,
        safety=primary_safety,
        decision=primary_decision,
    )
    support = build_executive_brief(
        ctx=support_ctx,
        safety=support_safety,
        decision=support_decision,
    )

    print("=" * 72)
    print("AGEDCARE EXECUTIVE REPORTING DEMO")
    print("=" * 72)
    print("\n[Primary Case]")
    for line in executive_brief_lines(primary):
        print(" ", line)

    print("\n[Nexus Signal]")
    pprint(executive_brief_to_nexus_signal(primary))

    print("\n[Pharaoh Report]")
    pprint(executive_brief_to_pharaoh_report(primary))

    print("\n[Merged Care Load]")
    pprint(merge_briefs((primary, support)))


if __name__ == "__main__":
    main()
