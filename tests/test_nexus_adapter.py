from aged_care import (
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


def make_ctx() -> CareContext:
    profile = CareProfile(
        person_id="P-001",
        name="홍길동",
        age=78,
        medical=MedicalInfo(fall_risk=0.4),
    )
    ctx = CareContext(
        profile=profile,
        platform=PlatformType.WHEELCHAIR,
        memory=AgentMemory(fatigue_score=0.35, alerts_today=["낙상 위험 감지"]),
        vitals=VitalSigns(heart_rate_bpm=96, spo2_pct=93, body_temp_c=37.1, alert_level=0.8),
    )
    ctx.person_state = PersonState(cognitive_load=0.45, alert_level=0.8)
    ctx.destination = (37.57, 126.98)
    ctx.extra["mission_completion"] = 0.5
    return ctx


def test_build_executive_brief():
    ctx = make_ctx()
    safety = SafetyState(omega=0.62, verdict="CAUTION")
    decision = CareDecision(action="assist", request_handoff=PlatformType.CAR)
    brief = build_executive_brief(ctx=ctx, safety=safety, decision=decision)
    assert brief.person_id == "P-001"
    assert brief.current_platform == "wheelchair"
    assert brief.omega_care == 0.62
    assert "handoff:car" in brief.recommended_actions


def test_brief_to_nexus_signal():
    ctx = make_ctx()
    brief = build_executive_brief(ctx=ctx, safety=SafetyState(omega=0.4, verdict="WARNING"))
    signal = executive_brief_to_nexus_signal(brief)
    assert 0.0 <= signal.care_omega <= 1.0
    assert 0.0 <= signal.care_load <= 1.0
    assert signal.flags["care_warning"] is True


def test_brief_to_pharaoh_report():
    ctx = make_ctx()
    brief = build_executive_brief(
        ctx=ctx,
        safety=SafetyState(omega=0.2, verdict="EMERGENCY", emergency_triggered=True),
        decision=CareDecision(emergency=True, alert="응급"),
    )
    report = executive_brief_to_pharaoh_report(brief)
    assert report["subject_type"] == "aged_care_case"
    assert report["pharaoh_attention_required"] is True
    assert report["health_campaign_recommended"] is True


def test_executive_brief_lines():
    ctx = make_ctx()
    brief = build_executive_brief(ctx=ctx, safety=SafetyState(omega=0.7, verdict="SAFE"))
    lines = executive_brief_lines(brief)
    assert len(lines) >= 2
    assert "홍길동" in lines[0]


def test_merge_briefs():
    ctx = make_ctx()
    b1 = build_executive_brief(ctx=ctx, safety=SafetyState(omega=0.8, verdict="SAFE"))
    ctx2 = make_ctx()
    ctx2.profile = CareProfile(person_id="P-002", name="김영희", age=81)
    b2 = build_executive_brief(
        ctx=ctx2,
        safety=SafetyState(omega=0.3, verdict="WARNING"),
        decision=CareDecision(emergency=True),
    )
    merged = merge_briefs([b1, b2])
    assert merged.care_omega == 0.3
    assert merged.care_emergency is True
    assert merged.flags["multi_case"] is True
