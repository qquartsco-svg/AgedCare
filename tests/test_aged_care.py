"""AgedCare_Stack 전체 테스트 스위트.

§1  데이터 스키마 & 파생 지표
§2  CareMonitor — Ω 케어 안전 지수
§3  HandoffProtocol — 토큰 발행 / 확인 / 중단
§4  PetPlatform 틱 동작
§5  WheelchairPlatform 틱 동작
§6  CarPlatform 틱 동작
§7  CareAgent 통합 — 세션 / 틱 / 핸드오프 / 메모리
§8  새 레이어 테스트 — v0.2.0

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


# ─────────────────────────────────────────────────────────────────────────────
# §8  새 레이어 테스트 — v0.2.0
# ─────────────────────────────────────────────────────────────────────────────

from aged_care.contracts.schemas import (
    PersonState, MissionState, SafetyState, ScheduleEvent, CareGoal,
)
from aged_care.audit.care_chain import CareChain, CareBlock
from aged_care.cognitive.emotion_engine import EmotionEngine, EmotionState
from aged_care.cognitive.memory_engine import MemoryEngine, MemoryTrace
from aged_care.cognitive.action_engine import ActionEngine, ActionScore
from aged_care.adapters.cognitive_adapter import CognitiveAdapter, CognitiveReport
from aged_care.adapters.battery_adapter import BatteryAdapter, BatteryReport
from aged_care.adapters.snn_adapter import SNNAdapter, SpikePattern
from aged_care.adapters.emergency_adapter import EmergencyAdapter, EmergencyEvent
from aged_care.monitor.omega import OmegaMonitor, OmegaReport


class TestPersonState:
    def test_emotion_magnitude_neutral(self):
        ps = PersonState()
        # valence=0.5, arousal=0.3 → v_c=0.0, E=0.3
        mag = ps.emotion_magnitude()
        assert abs(mag - 0.3) < 1e-6

    def test_emotion_magnitude_distressed(self):
        ps = PersonState(valence=0.1, arousal=0.9)
        mag = ps.emotion_magnitude()
        assert mag > 0.3

    def test_emotion_angle_deg_positive_arousal(self):
        ps = PersonState(valence=0.5, arousal=0.5)
        angle = ps.emotion_angle_deg()
        # arctan(0.5 / ~0) ≈ 90 degrees (high arousal)
        assert angle > 0

    def test_as_vector_length(self):
        ps = PersonState()
        vec = ps.as_vector()
        assert len(vec) == 10

    def test_as_vector_values(self):
        ps = PersonState(pos_x=1.0, pos_y=2.0, heart_rate=80.0)
        vec = ps.as_vector()
        assert vec[0] == 1.0
        assert vec[1] == 2.0
        assert vec[4] == 80.0


class TestMissionState:
    def test_completion_ratio_zero(self):
        ms = MissionState(total_stages=4, completed_stages=0)
        assert ms.completion_ratio() == 0.0

    def test_completion_ratio_half(self):
        ms = MissionState(total_stages=4, completed_stages=2)
        assert ms.completion_ratio() == 0.5

    def test_completion_ratio_full(self):
        ms = MissionState(total_stages=4, completed_stages=4)
        assert ms.completion_ratio() == 1.0

    def test_completion_ratio_zero_stages(self):
        ms = MissionState(total_stages=0, completed_stages=0)
        assert ms.completion_ratio() == 1.0

    def test_next_waypoint_returns_first(self):
        ms = MissionState(waypoints=[(1.0, 2.0), (3.0, 4.0)])
        assert ms.next_waypoint() == (1.0, 2.0)

    def test_next_waypoint_falls_back_to_destination(self):
        ms = MissionState(current_destination=(5.0, 6.0))
        assert ms.next_waypoint() == (5.0, 6.0)

    def test_next_waypoint_none_when_empty(self):
        ms = MissionState()
        assert ms.next_waypoint() is None


class TestCareChain:
    def test_empty_chain_verifies(self):
        chain = CareChain()
        assert chain.verify()

    def test_record_adds_block(self):
        chain = CareChain()
        chain.record("session_start", PlatformType.PET, 0.0)
        assert chain.length == 1

    def test_multiple_records(self):
        chain = CareChain()
        chain.record("handoff", PlatformType.PET, 0.0, {"to": "wheelchair"})
        chain.record("vitals_alert", PlatformType.WHEELCHAIR, 5.0, {"hr": 130})
        assert chain.length == 2

    def test_verify_after_records(self):
        chain = CareChain()
        chain.record("event1", PlatformType.PET, 1.0)
        chain.record("event2", PlatformType.WHEELCHAIR, 2.0)
        assert chain.verify()

    def test_tamper_breaks_verify(self):
        chain = CareChain()
        chain.record("event1", PlatformType.PET, 1.0, {"x": 1})
        # Tamper with block data
        chain._blocks[0].data["x"] = 999
        assert not chain.verify()

    def test_head_hash_changes_after_record(self):
        chain = CareChain()
        h0 = chain.head_hash
        chain.record("event1", PlatformType.PET, 0.0)
        assert chain.head_hash != h0

    def test_block_has_correct_fields(self):
        chain = CareChain()
        block = chain.record("handoff", PlatformType.WHEELCHAIR, 10.0, {"key": "val"})
        assert block.index == 0
        assert block.event_type == "handoff"
        assert block.platform == "wheelchair"
        assert block.t_s == 10.0

    def test_summary_string(self):
        chain = CareChain()
        chain.record("handoff", PlatformType.PET, 0.0)
        chain.record("handoff", PlatformType.PET, 1.0)
        s = chain.summary()
        assert "CareChain" in s
        assert "handoff" in s


class TestEmotionEngine:
    def test_assess_returns_emotion_state(self):
        engine = EmotionEngine()
        ctx = make_ctx()
        result = engine.assess(ctx)
        assert isinstance(result, EmotionState)

    def test_valence_in_range(self):
        engine = EmotionEngine()
        ctx = make_ctx()
        result = engine.assess(ctx)
        assert 0.0 <= result.valence <= 1.0

    def test_arousal_in_range(self):
        engine = EmotionEngine()
        ctx = make_ctx()
        result = engine.assess(ctx)
        assert 0.0 <= result.arousal <= 1.0

    def test_high_pain_lowers_valence(self):
        engine = EmotionEngine()
        ctx_pain = make_ctx()
        ctx_pain.vitals = VitalSigns(pain_level=9.0)
        ctx_normal = make_ctx()
        ctx_normal.vitals = VitalSigns(pain_level=0.0)
        r_pain = engine.assess(ctx_pain)
        r_normal = engine.assess(ctx_normal)
        assert r_pain.valence <= r_normal.valence

    def test_label_is_string(self):
        engine = EmotionEngine()
        ctx = make_ctx()
        result = engine.assess(ctx)
        assert isinstance(result.label, str)
        assert result.label in ("calm", "anxious", "distressed", "sad", "neutral")


class TestMemoryEngine:
    def test_encode_returns_trace(self):
        engine = MemoryEngine()
        trace = engine.encode("test content", (1.0, 2.0), 0.0, tags=["test"])
        assert isinstance(trace, MemoryTrace)

    def test_recall_by_tag_finds_trace(self):
        engine = MemoryEngine()
        engine.encode("약 복용", (0.0, 0.0), 0.0, tags=["medication"])
        results = engine.recall_by_tag("medication", 1.0)
        assert len(results) >= 1

    def test_recall_by_tag_misses_different_tag(self):
        engine = MemoryEngine()
        engine.encode("외출", (0.0, 0.0), 0.0, tags=["mobility"])
        results = engine.recall_by_tag("medication", 1.0)
        assert len(results) == 0

    def test_memory_trace_strength_decays(self):
        engine = MemoryEngine()
        trace = engine.encode("event", (0.0, 0.0), 0.0)
        s0 = trace.current_strength(0.0)
        s1 = trace.current_strength(86400.0)  # 1 day later
        assert s1 < s0

    def test_strongest_recent_returns_n(self):
        engine = MemoryEngine()
        for i in range(5):
            engine.encode(f"event {i}", (float(i), 0.0), float(i))
        top = engine.strongest_recent(3, 5.0)
        assert len(top) == 3


class TestCognitiveAdapter:
    def test_tick_returns_report(self):
        adapter = CognitiveAdapter()
        ctx = make_ctx()
        report = adapter.tick(ctx)
        assert isinstance(report, CognitiveReport)

    def test_cognitive_omega_in_range(self):
        adapter = CognitiveAdapter()
        ctx = make_ctx()
        report = adapter.tick(ctx)
        assert 0.0 <= report.cognitive_omega <= 1.0

    def test_recommended_action_is_string(self):
        adapter = CognitiveAdapter()
        ctx = make_ctx()
        report = adapter.tick(ctx)
        assert isinstance(report.recommended_action, str)

    def test_emergency_flag_triggers_emergency_action(self):
        adapter = CognitiveAdapter()
        ctx = make_ctx()
        ctx.extra["emergency"] = True
        report = adapter.tick(ctx)
        assert "emergency" in report.recommended_action


class TestBatteryAdapter:
    def test_tick_returns_report(self):
        adapter = BatteryAdapter(PlatformType.WHEELCHAIR)
        ctx = make_ctx()
        report = adapter.tick(ctx)
        assert isinstance(report, BatteryReport)

    def test_full_battery_omega_is_one(self):
        adapter = BatteryAdapter(PlatformType.WHEELCHAIR)
        ctx = make_ctx()
        ctx.extra["wheelchair_battery_pct"] = 100.0
        report = adapter.tick(ctx)
        assert report.omega_battery == 1.0

    def test_critical_battery_omega_is_low(self):
        adapter = BatteryAdapter(PlatformType.WHEELCHAIR)
        ctx = make_ctx()
        ctx.extra["wheelchair_battery_pct"] = 10.0
        report = adapter.tick(ctx)
        assert report.omega_battery <= 0.10
        assert report.is_critical

    def test_low_battery_flag(self):
        adapter = BatteryAdapter(PlatformType.WHEELCHAIR)
        ctx = make_ctx()
        ctx.extra["wheelchair_battery_pct"] = 25.0
        report = adapter.tick(ctx)
        assert report.is_low

    def test_range_km_estimate(self):
        adapter = BatteryAdapter(PlatformType.WHEELCHAIR)
        ctx = make_ctx()
        ctx.extra["wheelchair_battery_pct"] = 50.0
        report = adapter.tick(ctx)
        assert report.estimated_range_km == 10.0  # 50% of 20km


class TestSNNAdapter:
    def test_classify_returns_pattern(self):
        adapter = SNNAdapter()
        ctx = make_ctx()
        ctx.vitals = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.5)
        result = adapter.classify(ctx)
        assert isinstance(result, SpikePattern)

    def test_normal_vitals_classify_normal(self):
        adapter = SNNAdapter()
        ctx = make_ctx()
        ctx.vitals = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.5)
        result = adapter.classify(ctx)
        assert result.pattern_label == "normal"

    def test_critical_vitals_classify_crisis(self):
        adapter = SNNAdapter()
        ctx = make_ctx()
        ctx.vitals = VitalSigns(heart_rate_bpm=145, spo2_pct=85, body_temp_c=40.0)
        result = adapter.classify(ctx)
        assert result.pattern_label == "crisis"

    def test_no_vitals_returns_unknown(self):
        adapter = SNNAdapter()
        ctx = make_ctx()
        ctx.vitals = None
        result = adapter.classify(ctx)
        assert result.pattern_label == "unknown"

    def test_encode_vitals_length(self):
        adapter = SNNAdapter()
        vitals = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.5)
        vec = adapter.encode_vitals(vitals)
        assert len(vec) == 8


class TestEmergencyAdapter:
    def setup_method(self):
        self.adapter = EmergencyAdapter()
        self.profile = make_profile()

    def test_no_emergency_returns_none(self):
        ctx = make_ctx(profile=self.profile)
        ctx.vitals = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.5)
        result = self.adapter.evaluate(ctx, {})
        assert result is None

    def test_fall_detected_creates_event(self):
        ctx = make_ctx(profile=self.profile)
        ctx.vitals = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.5)
        result = self.adapter.evaluate(ctx, {"fall_detected": True})
        assert result is not None
        assert result.event_type == "fall"

    def test_critical_vitals_creates_event(self):
        ctx = make_ctx(profile=self.profile)
        ctx.vitals = VitalSigns(heart_rate_bpm=145, spo2_pct=85, body_temp_c=40.5)
        result = self.adapter.evaluate(ctx, {})
        assert result is not None
        assert result.event_type == "vitals_critical"

    def test_cooldown_prevents_duplicate(self):
        ctx = make_ctx(profile=self.profile)
        ctx.vitals = VitalSigns(heart_rate_bpm=145, spo2_pct=85, body_temp_c=40.5)
        r1 = self.adapter.evaluate(ctx, {})
        r2 = self.adapter.evaluate(ctx, {})   # same t_s → cooldown
        assert r1 is not None
        assert r2 is None

    def test_get_recent_events(self):
        ctx = make_ctx(profile=self.profile)
        ctx.vitals = VitalSigns(heart_rate_bpm=145, spo2_pct=85, body_temp_c=40.5)
        self.adapter.evaluate(ctx, {})
        events = self.adapter.get_recent_events(5)
        assert len(events) >= 1


class TestOmegaMonitor:
    def test_tick_returns_report(self):
        mon = OmegaMonitor()
        ctx = make_ctx()
        ctx.vitals = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.5)
        report = mon.tick(ctx)
        assert isinstance(report, OmegaReport)

    def test_six_omega_factors_present(self):
        mon = OmegaMonitor()
        ctx = make_ctx()
        report = mon.tick(ctx)
        assert hasattr(report, "omega_vitals")
        assert hasattr(report, "omega_fatigue")
        assert hasattr(report, "omega_env")
        assert hasattr(report, "omega_medication")
        assert hasattr(report, "omega_battery")
        assert hasattr(report, "omega_cognitive")

    def test_healthy_is_safe(self):
        mon = OmegaMonitor()
        ctx = make_ctx()
        ctx.vitals = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.5)
        report = mon.tick(ctx, battery_omega=1.0, cognitive_omega=1.0)
        assert report.verdict == "SAFE"

    def test_low_battery_reduces_omega(self):
        mon = OmegaMonitor()
        ctx = make_ctx()
        ctx.vitals = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.5)
        r_full = mon.tick(ctx, battery_omega=1.0, cognitive_omega=1.0)
        r_low  = mon.tick(ctx, battery_omega=0.10, cognitive_omega=1.0)
        assert r_low.omega < r_full.omega

    def test_as_dict_has_all_keys(self):
        mon = OmegaMonitor()
        ctx = make_ctx()
        report = mon.tick(ctx)
        d = report.as_dict()
        assert "Ω_vitals" in d
        assert "Ω_care" in d
        assert "verdict" in d

    def test_fall_triggers_emergency(self):
        mon = OmegaMonitor()
        ctx = make_ctx()
        ctx.extra["accel_g"] = 5.0
        report = mon.tick(ctx)
        assert report.emergency
        assert report.fall_detected


class TestCareAgentV2:
    def setup_method(self):
        self.profile = make_profile()
        self.agent = CareAgent(self.profile)

    def test_session_start_records_chain_block(self):
        # CareChain should have at least the session_start block
        if self.agent._chain:
            assert self.agent._chain.length >= 1
            assert self.agent._chain._blocks[0].event_type == "session_start"

    def test_chain_verifies_after_ticks(self):
        ctx = self.agent.start_session()
        for _ in range(5):
            ctx, _ = self.agent.tick(ctx)
        if self.agent._chain:
            assert self.agent._chain.verify()

    def test_person_state_updated_after_tick(self):
        ctx = self.agent.start_session()
        ctx.vitals = VitalSigns(heart_rate_bpm=85, spo2_pct=96, body_temp_c=37.0)
        ctx, _ = self.agent.tick(ctx)
        assert self.agent.person_state.heart_rate == 85.0

    def test_mission_state_default(self):
        assert self.agent.mission_state.mission_id == "default"
        assert self.agent.mission_state.completion_ratio() == 0.0

    def test_safety_state_has_verdict(self):
        assert isinstance(self.agent.safety_state.verdict, str)

    def test_get_omega_report_returns_report(self):
        ctx = self.agent.start_session()
        report = self.agent.get_omega_report(ctx)
        if report is not None:
            assert hasattr(report, "omega")
            assert 0.0 <= report.omega <= 1.0

    def test_summary_v2_contains_omega(self):
        ctx = self.agent.start_session()
        ctx, _ = self.agent.tick(ctx)
        s = self.agent.summary()
        assert "Ω_care" in s

    def test_handoff_recorded_in_chain(self):
        ctx = self.agent.start_session()
        ctx.destination = (100.0, 200.0)
        ctx.extra["go_out"] = True
        ctx, _ = self.agent.tick(ctx)
        if self.agent._chain and self.agent._pending_token:
            events = [b.event_type for b in self.agent._chain._blocks]
            assert "handoff_initiated" in events
