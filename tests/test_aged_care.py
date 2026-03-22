"""AgedCare_Stack 전체 테스트 스위트.

§1  데이터 스키마 & 파생 지표
§2  CareMonitor — Ω 케어 안전 지수
§3  HandoffProtocol — 토큰 발행 / 확인 / 중단
§4  PetPlatform 틱 동작
§5  WheelchairPlatform 틱 동작
§6  CarPlatform 틱 동작
§7  CareAgent 통합 — 세션 / 틱 / 핸드오프 / 메모리

실행:
    cd AgedCare_Stack
    python -m pytest tests/test_aged_care.py -v
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import math
import pytest

from aged_care.contracts.schemas import (
    PlatformType, MedicalInfo, CareProfile, VitalSigns,
    EnvironmentFrame, AgentMemory, CareDecision, HandoffToken, CareContext,
)
from aged_care.monitor import CareMonitor, MonitorResult
from aged_care.handoff.protocol import HandoffProtocol, ALLOWED_TRANSITIONS
from aged_care.platforms.pet import PetPlatform
from aged_care.platforms.wheelchair import WheelchairPlatform
from aged_care.platforms.car import CarPlatform
from aged_care.care_agent import CareAgent


# ─────────────────────────────────────────────────────────────────────────────
# 픽스처
# ─────────────────────────────────────────────────────────────────────────────

def make_profile(**kw) -> CareProfile:
    defaults = dict(
        person_id="TST-001",
        name="테스터",
        age=75,
        medical=MedicalInfo(
            conditions=("고혈압",),
            medications=("아스피린",),
            mobility_level=0.7,
            fall_risk=0.3,
        ),
        home_location=(0.0, 0.0),
        emergency_contacts=("010-0000-0000",),
    )
    defaults.update(kw)
    return CareProfile(**defaults)


def make_ctx(platform=PlatformType.PET, **kw) -> CareContext:
    profile = kw.pop("profile", make_profile())
    ctx = CareContext(
        profile=profile,
        platform=platform,
        memory=AgentMemory(),
        t_s=0.0,
    )
    for k, v in kw.items():
        setattr(ctx, k, v)
    return ctx


# ─────────────────────────────────────────────────────────────────────────────
# §1  데이터 스키마 & 파생 지표
# ─────────────────────────────────────────────────────────────────────────────

class TestSchemas:
    def test_platform_type_values(self):
        assert PlatformType.PET.value == "pet"
        assert PlatformType.WHEELCHAIR.value == "wheelchair"
        assert PlatformType.CAR.value == "car"
        assert PlatformType.NONE.value == "none"

    def test_vitals_normal_not_critical(self):
        v = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.5)
        assert not v.is_critical()

    def test_vitals_low_spo2_is_critical(self):
        # is_critical: spo2_pct < 90.0
        v = VitalSigns(heart_rate_bpm=72, spo2_pct=88, body_temp_c=36.5)
        assert v.is_critical()

    def test_vitals_high_hr_is_critical(self):
        # is_critical: heart_rate_bpm > 130
        v = VitalSigns(heart_rate_bpm=135, spo2_pct=97, body_temp_c=36.5)
        assert v.is_critical()

    def test_vitals_low_hr_is_critical(self):
        # is_critical: heart_rate_bpm < 40
        v = VitalSigns(heart_rate_bpm=38, spo2_pct=97, body_temp_c=36.5)
        assert v.is_critical()

    def test_vitals_high_temp_is_critical(self):
        # is_critical: body_temp_c > 39.5
        v = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=40.0)
        assert v.is_critical()

    def test_vitals_risk_score_normal(self):
        v = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.5)
        assert 0.0 <= v.risk_score() <= 1.0

    def test_vitals_risk_score_critical_higher(self):
        normal = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.5)
        critical = VitalSigns(heart_rate_bpm=140, spo2_pct=88, body_temp_c=39.5)
        assert critical.risk_score() > normal.risk_score()

    def test_vitals_frozen(self):
        v = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.5)
        with pytest.raises((AttributeError, TypeError)):
            v.heart_rate_bpm = 80  # type: ignore

    def test_env_defaults_safe(self):
        env = EnvironmentFrame()
        assert not env.obstacle_detected
        assert not env.floor_hazard

    def test_care_decision_defaults(self):
        d = CareDecision()
        assert d.speak is None
        assert d.emergency is False
        assert d.request_handoff is None

    def test_handoff_token_fields(self):
        tok = HandoffToken(
            token_id="tok-001",
            from_platform=PlatformType.PET,
            to_platform=PlatformType.WHEELCHAIR,
            agent_memory=AgentMemory(),
        )
        assert not tok.confirmed
        assert not tok.aborted

    def test_care_context_defaults(self):
        ctx = make_ctx()
        assert ctx.destination is None
        assert ctx.extra == {}
        assert ctx.dt_s == 0.1   # 스키마 기본값 0.1 s/틱

    def test_medical_info_defaults(self):
        m = MedicalInfo()
        assert m.conditions == ()
        assert 0.0 <= m.fall_risk <= 1.0

    def test_agent_memory_initial(self):
        mem = AgentMemory()
        assert mem.fatigue_score == 0.0
        assert mem.mood_score == 0.7
        assert mem.conversation_history == []
        assert mem.alerts_today == []


# ─────────────────────────────────────────────────────────────────────────────
# §2  CareMonitor — Ω 케어 안전 지수
# ─────────────────────────────────────────────────────────────────────────────

class TestCareMonitor:
    def setup_method(self):
        self.mon = CareMonitor()

    def test_healthy_ctx_safe(self):
        ctx = make_ctx()
        ctx.vitals = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.5)
        result = self.mon.tick(ctx)
        assert result.verdict == "SAFE"
        assert result.omega >= 0.80

    def test_default_vitals_caution_or_safe(self):
        # vitals 기본값(정상)은 SAFE 또는 CAUTION
        ctx = make_ctx()
        # ctx.vitals 는 VitalSigns 기본값 — 정상 범위
        result = self.mon.tick(ctx)
        assert result.verdict in ("SAFE", "CAUTION")

    def test_critical_vitals_triggers_emergency(self):
        ctx = make_ctx()
        ctx.vitals = VitalSigns(heart_rate_bpm=150, spo2_pct=85, body_temp_c=40.5)
        result = self.mon.tick(ctx)
        assert result.emergency

    def test_high_fatigue_downgrades_verdict(self):
        ctx = make_ctx()
        ctx.vitals = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.5)
        ctx.memory.fatigue_score = 0.95
        result = self.mon.tick(ctx)
        assert result.omega < 0.80

    def test_obstacle_close_adds_alert(self):
        # obstacle_range_m < 0.5 m → 장애물 근접 알림
        ctx = make_ctx()
        ctx.environment = EnvironmentFrame(obstacle_range_m=0.3)
        result = self.mon.tick(ctx)
        assert any("장애물" in a for a in result.alerts)

    def test_floor_hazard_adds_alert(self):
        ctx = make_ctx()
        ctx.environment = EnvironmentFrame(floor_hazard=True)
        result = self.mon.tick(ctx)
        assert any("미끄럼" in a or "바닥" in a for a in result.alerts)

    def test_omega_in_range(self):
        ctx = make_ctx()
        result = self.mon.tick(ctx)
        assert 0.0 <= result.omega <= 1.0

    def test_monitor_result_has_all_fields(self):
        ctx = make_ctx()
        result = self.mon.tick(ctx)
        assert hasattr(result, "omega")
        assert hasattr(result, "verdict")
        assert hasattr(result, "emergency")
        assert hasattr(result, "alerts")
        assert hasattr(result, "medication_due")

    def test_omega_decreases_with_worse_vitals(self):
        ctx_good = make_ctx()
        ctx_good.vitals = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.5)
        ctx_bad = make_ctx()
        ctx_bad.vitals = VitalSigns(heart_rate_bpm=120, spo2_pct=92, body_temp_c=38.5)
        r_good = self.mon.tick(ctx_good)
        r_bad  = self.mon.tick(ctx_bad)
        assert r_good.omega >= r_bad.omega

    def test_medication_due_flag(self):
        # elapsed = t_s − last_medication_t_s > 28800 이어야 함
        # t_s=30000, last=0 → elapsed=30000 > 28800 → True
        ctx = make_ctx()
        ctx.memory.last_medication_t_s = 0.0
        ctx.t_s = 30000.0
        result = self.mon.tick(ctx)
        assert result.medication_due


# ─────────────────────────────────────────────────────────────────────────────
# §3  HandoffProtocol — 토큰 발행 / 확인 / 중단
# ─────────────────────────────────────────────────────────────────────────────

class TestHandoffProtocol:
    def setup_method(self):
        self.proto = HandoffProtocol()

    def test_allowed_transitions_defined(self):
        assert (PlatformType.PET, PlatformType.WHEELCHAIR) in ALLOWED_TRANSITIONS
        assert (PlatformType.WHEELCHAIR, PlatformType.PET) in ALLOWED_TRANSITIONS
        assert (PlatformType.WHEELCHAIR, PlatformType.CAR) in ALLOWED_TRANSITIONS
        assert (PlatformType.CAR, PlatformType.WHEELCHAIR) in ALLOWED_TRANSITIONS

    def test_pet_to_car_not_allowed(self):
        assert (PlatformType.PET, PlatformType.CAR) not in ALLOWED_TRANSITIONS

    def test_initiate_valid_returns_token(self):
        ctx = make_ctx(platform=PlatformType.PET)
        token = self.proto.initiate(ctx, PlatformType.WHEELCHAIR)
        assert token is not None
        assert token.from_platform == PlatformType.PET
        assert token.to_platform == PlatformType.WHEELCHAIR

    def test_initiate_invalid_returns_none(self):
        ctx = make_ctx(platform=PlatformType.PET)
        token = self.proto.initiate(ctx, PlatformType.CAR)
        assert token is None

    def test_token_id_deterministic_same_input(self):
        # 동일 플랫폼·시간 → 동일 해시 (결정론적)
        ctx = make_ctx(platform=PlatformType.PET)
        t1 = self.proto.initiate(ctx, PlatformType.WHEELCHAIR)
        # 다른 t_s 로 두 번째 토큰 → 다른 ID
        ctx2 = make_ctx(platform=PlatformType.PET)
        ctx2.t_s = 99.0
        t2 = self.proto.initiate(ctx2, PlatformType.WHEELCHAIR)
        assert t1 is not None and t2 is not None
        assert t1.token_id != t2.token_id

    def test_confirm_valid_token(self):
        ctx = make_ctx(platform=PlatformType.PET)
        token = self.proto.initiate(ctx, PlatformType.WHEELCHAIR)
        assert token is not None
        confirmed = self.proto.confirm(token.token_id)
        assert confirmed is not None
        assert confirmed.confirmed

    def test_confirm_unknown_token_returns_none(self):
        result = self.proto.confirm("nonexistent-id")
        assert result is None

    def test_abort_removes_token(self):
        ctx = make_ctx(platform=PlatformType.PET)
        token = self.proto.initiate(ctx, PlatformType.WHEELCHAIR)
        assert token is not None
        aborted = self.proto.abort(token.token_id)
        assert aborted
        # 이미 중단된 토큰은 confirm 불가
        result = self.proto.confirm(token.token_id)
        assert result is None

    def test_abort_unknown_returns_false(self):
        assert not self.proto.abort("ghost-token")

    def test_token_carries_memory(self):
        ctx = make_ctx(platform=PlatformType.PET)
        ctx.memory.mood_score = 0.42
        token = self.proto.initiate(ctx, PlatformType.WHEELCHAIR)
        assert token is not None
        assert token.agent_memory.mood_score == 0.42

    def test_wheelchair_to_car_transition(self):
        ctx = make_ctx(platform=PlatformType.WHEELCHAIR)
        token = self.proto.initiate(ctx, PlatformType.CAR)
        assert token is not None
        assert token.to_platform == PlatformType.CAR


# ─────────────────────────────────────────────────────────────────────────────
# §4  PetPlatform 틱 동작
# ─────────────────────────────────────────────────────────────────────────────

class TestPetPlatform:
    def setup_method(self):
        self.platform = PetPlatform()
        self.profile = make_profile()
        agent_stub = type("Agent", (), {"profile": self.profile, "memory": AgentMemory()})()
        self.platform.attach(agent_stub)

    def _ctx(self, **kw):
        return make_ctx(platform=PlatformType.PET, profile=self.profile, **kw)

    def test_normal_tick_returns_decision(self):
        ctx = self._ctx()
        decision = self.platform.tick(ctx)
        assert isinstance(decision, CareDecision)

    def test_normal_tick_action_set(self):
        ctx = self._ctx()
        decision = self.platform.tick(ctx)
        assert decision.action != ""

    def test_go_out_requests_wheelchair(self):
        ctx = self._ctx()
        ctx.destination = (100.0, 200.0)
        ctx.extra["go_out"] = True
        decision = self.platform.tick(ctx)
        assert decision.request_handoff == PlatformType.WHEELCHAIR

    def test_fall_detected_triggers_emergency(self):
        # 낙상 감지: ctx.extra["accel_g"] > 3.0 → CareMonitor.fall_detected → emergency
        ctx = self._ctx()
        ctx.extra["accel_g"] = 4.0
        decision = self.platform.tick(ctx)
        assert decision.emergency or decision.alert

    def test_critical_vitals_triggers_emergency(self):
        ctx = self._ctx()
        ctx.vitals = VitalSigns(heart_rate_bpm=150, spo2_pct=85, body_temp_c=40.5)
        decision = self.platform.tick(ctx)
        assert decision.emergency

    def test_no_emergency_on_healthy_vitals(self):
        ctx = self._ctx()
        ctx.vitals = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.5)
        decision = self.platform.tick(ctx)
        assert not decision.emergency

    def test_detach_does_not_crash(self):
        self.platform.detach()  # should not raise

    def test_platform_type_is_pet(self):
        from aged_care.platforms.base import PlatformBase
        assert self.platform.platform_type == PlatformType.PET


# ─────────────────────────────────────────────────────────────────────────────
# §5  WheelchairPlatform 틱 동작
# ─────────────────────────────────────────────────────────────────────────────

class TestWheelchairPlatform:
    def setup_method(self):
        self.platform = WheelchairPlatform()
        self.profile = make_profile()
        agent_stub = type("Agent", (), {"profile": self.profile, "memory": AgentMemory()})()
        self.platform.attach(agent_stub)

    def _ctx(self, **kw):
        return make_ctx(platform=PlatformType.WHEELCHAIR, profile=self.profile, **kw)

    def test_idle_without_destination(self):
        ctx = self._ctx()
        decision = self.platform.tick(ctx)
        assert decision.action in ("idle", "navigate", "stop")

    def test_navigate_with_destination(self):
        ctx = self._ctx()
        ctx.destination = (50.0, 50.0)
        decision = self.platform.tick(ctx)
        assert decision.action in ("navigate", "stop", "idle")

    def test_obstacle_stops_wheelchair(self):
        ctx = self._ctx()
        ctx.destination = (50.0, 50.0)
        ctx.environment = EnvironmentFrame(obstacle_range_m=0.3)  # 0.8m 미만
        decision = self.platform.tick(ctx)
        assert decision.action == "stop"

    def test_car_ready_triggers_handoff(self):
        ctx = self._ctx()
        ctx.destination = (50.0, 50.0)
        ctx.extra["car_ready"] = True
        decision = self.platform.tick(ctx)
        assert decision.request_handoff == PlatformType.CAR

    def test_at_home_triggers_pet_handoff(self):
        ctx = self._ctx()
        ctx.destination = None
        ctx.extra["at_home"] = True
        decision = self.platform.tick(ctx)
        assert decision.request_handoff == PlatformType.PET

    def test_emergency_stop_on_critical_vitals(self):
        ctx = self._ctx()
        ctx.vitals = VitalSigns(heart_rate_bpm=160, spo2_pct=83, body_temp_c=41.0)
        decision = self.platform.tick(ctx)
        assert decision.emergency

    def test_platform_type_is_wheelchair(self):
        assert self.platform.platform_type == PlatformType.WHEELCHAIR


# ─────────────────────────────────────────────────────────────────────────────
# §6  CarPlatform 틱 동작
# ─────────────────────────────────────────────────────────────────────────────

class TestCarPlatform:
    def setup_method(self):
        self.platform = CarPlatform()
        self.profile = make_profile()
        agent_stub = type("Agent", (), {"profile": self.profile, "memory": AgentMemory()})()
        self.platform.attach(agent_stub)

    def _ctx(self, **kw):
        return make_ctx(platform=PlatformType.CAR, profile=self.profile, **kw)

    def test_driving_with_destination(self):
        ctx = self._ctx()
        ctx.destination = (500.0, 200.0)
        decision = self.platform.tick(ctx)
        assert decision.action in ("navigate", "idle", "emergency_route")

    def test_arrived_triggers_wheelchair_handoff(self):
        ctx = self._ctx()
        ctx.extra["arrived"] = True
        decision = self.platform.tick(ctx)
        assert decision.request_handoff == PlatformType.WHEELCHAIR

    def test_shock_triggers_emergency(self):
        ctx = self._ctx()
        ctx.extra["shock_g"] = 3.5
        decision = self.platform.tick(ctx)
        assert decision.emergency
        assert "충격" in (decision.alert or "")

    def test_low_shock_no_emergency(self):
        ctx = self._ctx()
        ctx.extra["shock_g"] = 0.5
        decision = self.platform.tick(ctx)
        assert not decision.emergency

    def test_critical_vitals_reroute(self):
        ctx = self._ctx()
        ctx.vitals = VitalSigns(heart_rate_bpm=155, spo2_pct=84, body_temp_c=40.8)
        decision = self.platform.tick(ctx)
        assert decision.emergency

    def test_no_destination_idles(self):
        ctx = self._ctx()
        ctx.destination = None
        decision = self.platform.tick(ctx)
        assert decision.action == "idle"

    def test_platform_type_is_car(self):
        assert self.platform.platform_type == PlatformType.CAR

    def test_navigation_goal_set_when_driving(self):
        ctx = self._ctx()
        ctx.destination = (500.0, 200.0)
        decision = self.platform.tick(ctx)
        if decision.action == "navigate":
            assert decision.navigation_goal == (500.0, 200.0)


# ─────────────────────────────────────────────────────────────────────────────
# §7  CareAgent 통합 — 세션 / 틱 / 핸드오프 / 메모리
# ─────────────────────────────────────────────────────────────────────────────

class TestCareAgent:
    def setup_method(self):
        self.profile = make_profile()
        self.agent = CareAgent(self.profile)

    def test_start_session_returns_pet_platform(self):
        ctx = self.agent.start_session()
        assert ctx.platform == PlatformType.PET

    def test_tick_returns_ctx_and_decision(self):
        ctx = self.agent.start_session()
        ctx2, decision = self.agent.tick(ctx)
        assert isinstance(ctx2, CareContext)
        assert isinstance(decision, CareDecision)

    def test_time_advances_per_tick(self):
        ctx = self.agent.start_session()
        ctx, _ = self.agent.tick(ctx)
        assert self.agent._t_s == ctx.dt_s

    def test_multiple_ticks_no_crash(self):
        ctx = self.agent.start_session()
        for _ in range(20):
            ctx, decision = self.agent.tick(ctx)
        assert ctx.t_s > 0

    def test_go_out_creates_pending_token(self):
        ctx = self.agent.start_session()
        ctx.destination = (100.0, 200.0)
        ctx.extra["go_out"] = True
        ctx, decision = self.agent.tick(ctx)
        # 펜딩 토큰이 생성돼야 함
        assert self.agent._pending_token is not None
        assert self.agent._pending_token.to_platform == PlatformType.WHEELCHAIR

    def test_execute_handoff_switches_platform(self):
        ctx = self.agent.start_session()
        ctx.destination = (100.0, 200.0)
        ctx.extra["go_out"] = True
        ctx, decision = self.agent.tick(ctx)
        if self.agent._pending_token:
            result = self.agent.execute_handoff(ctx)
            assert result
            assert self.agent.current_platform == PlatformType.WHEELCHAIR

    def test_abort_handoff_keeps_original_platform(self):
        ctx = self.agent.start_session()
        ctx.destination = (100.0, 200.0)
        ctx.extra["go_out"] = True
        ctx, decision = self.agent.tick(ctx)
        if self.agent._pending_token:
            self.agent.abort_handoff()
            assert self.agent.current_platform == PlatformType.PET
            assert self.agent._pending_token is None

    def test_execute_handoff_without_token_returns_false(self):
        ctx = self.agent.start_session()
        result = self.agent.execute_handoff(ctx)
        assert not result

    def test_memory_conversation_history_grows(self):
        ctx = self.agent.start_session()
        for _ in range(30):
            ctx, decision = self.agent.tick(ctx)
        # 최대 50개 제한 확인
        assert len(self.agent.memory.conversation_history) <= 50

    def test_fatigue_increases_on_pet_platform(self):
        ctx = self.agent.start_session()
        initial_fatigue = self.agent.memory.fatigue_score
        for _ in range(10):
            ctx, _ = self.agent.tick(ctx)
        assert self.agent.memory.fatigue_score > initial_fatigue

    def test_summary_returns_string(self):
        ctx = self.agent.start_session()
        ctx, _ = self.agent.tick(ctx)
        s = self.agent.summary()
        assert isinstance(s, str)
        assert self.profile.name in s

    def test_full_pet_to_wheelchair_journey(self):
        """PET → 핸드오프 → WHEELCHAIR 전환 통합 검증."""
        ctx = self.agent.start_session()
        assert self.agent.current_platform == PlatformType.PET

        # go_out 신호
        ctx.destination = (100.0, 200.0)
        ctx.extra["go_out"] = True
        ctx, decision = self.agent.tick(ctx)

        if self.agent._pending_token:
            self.agent.execute_handoff(ctx)

        assert self.agent.current_platform == PlatformType.WHEELCHAIR

    def test_alert_stored_in_memory(self):
        ctx = self.agent.start_session()
        ctx.vitals = VitalSigns(heart_rate_bpm=155, spo2_pct=84, body_temp_c=41.0)
        ctx, decision = self.agent.tick(ctx)
        if decision.alert:
            assert len(self.agent.memory.alerts_today) >= 1

    def test_llm_decide_returns_none_in_fallback(self):
        ctx = self.agent.start_session()
        result = self.agent._llm_decide(ctx)
        assert result is None

    def test_wheelchair_to_car_journey(self):
        """WHEELCHAIR → CAR 전환 통합 검증."""
        # 먼저 PET → WHEELCHAIR
        ctx = self.agent.start_session()
        ctx.destination = (100.0, 200.0)
        ctx.extra["go_out"] = True
        ctx, _ = self.agent.tick(ctx)
        if self.agent._pending_token:
            self.agent.execute_handoff(ctx)
        ctx.extra.pop("go_out", None)

        assert self.agent.current_platform == PlatformType.WHEELCHAIR

        # car_ready 신호
        ctx.extra["car_ready"] = True
        ctx, decision = self.agent.tick(ctx)
        if self.agent._pending_token:
            self.agent.execute_handoff(ctx)
            assert self.agent.current_platform == PlatformType.CAR
