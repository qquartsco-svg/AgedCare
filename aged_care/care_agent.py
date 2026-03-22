"""CareAgent — 지속 AI 케어 에이전트 v0.2.0.

하드웨어(플랫폼)가 바뀌어도 AI 에이전트는 하나다.
PetPlatform → WheelchairPlatform → CarPlatform → ... 어디서든 같은 에이전트.

레이어 구조:
  Layer 0 (본 파일): 개인 AI 코어 — 기억·대화·감정·판단
  Layer 1 (care_agent): 케어 오케스트레이터 — 핸드오프·미션·안전
  Layer 2 (platforms/): 이동 엔진 — 펫·휠체어·자동차
  Layer 3 (adapters/): 외부 엔진 브리지
  Layer 4 (audit/): 감사 체인

Claude API 연동 확장:
  _llm_decide() → anthropic.messages.create()
  폴백: 규칙 기반 CognitiveAdapter 사용
"""
from __future__ import annotations

import logging
import os
from typing import Optional

log = logging.getLogger(__name__)

from .contracts.schemas import (
    AgentMemory, CareContext, CareDecision, CareProfile,
    HandoffToken, PlatformType, VitalSigns, PersonState,
    MissionState, SafetyState,
)
from .handoff.protocol import HandoffProtocol
from .platforms.base import PlatformBase
from .platforms.pet import PetPlatform
from .platforms.wheelchair import WheelchairPlatform
from .platforms.car import CarPlatform
from .monitor import CareMonitor

# ── 선택적 임포트 (Edge AI: 없어도 작동) ──────────────────────────────
try:
    from .adapters.cognitive_adapter import CognitiveAdapter, CognitiveReport
    _COGNITIVE_OK = True
except Exception:
    _COGNITIVE_OK = False

try:
    from .adapters.emergency_adapter import EmergencyAdapter
    _EMERGENCY_OK = True
except Exception:
    _EMERGENCY_OK = False

try:
    from .audit.care_chain import CareChain
    _AUDIT_OK = True
except Exception:
    _AUDIT_OK = False

try:
    from .monitor.omega import OmegaMonitor, OmegaReport
    _OMEGA_OK = True
except Exception:
    _OMEGA_OK = False


class CareAgent:
    """지속 AI 케어 에이전트 v0.2.0.

    레이어 아키텍처::

        ┌─────────────────────────────────────┐
        │  Layer 0: Personal AI Core          │  ← CareAgent
        │  - 기억(Hippocampus), 감정(Amygdala) │
        │  - 행동선택(BasalGanglia), 계획(PFC) │
        │  - Claude API / 규칙 기반 폴백       │
        ├─────────────────────────────────────┤
        │  Layer 1: Care Orchestrator         │  ← HandoffProtocol
        │  - 미션 관리, 핸드오프 조율           │
        │  - Ω_care 통합 안전 판정             │
        ├─────────────────────────────────────┤
        │  Layer 2: Mobility Engines          │  ← PetPlatform etc.
        │  - 펫 / 휠체어 / 자동차             │
        │  - Autonomy_Runtime_Stack           │
        │  - SYD_DRIFT                        │
        ├─────────────────────────────────────┤
        │  Layer 3: Adapters                  │  ← adapters/
        │  - CognitiveAdapter                 │
        │  - BatteryAdapter                   │
        │  - SNNAdapter, EmergencyAdapter     │
        ├─────────────────────────────────────┤
        │  Layer 4: Audit / Safety            │  ← audit/
        │  - CareChain (SHA-256)              │
        └─────────────────────────────────────┘

    Ω_care = Ω_v × Ω_f × Ω_e × Ω_m × Ω_b × Ω_c

    사용법::
        profile = CareProfile(person_id="001", name="홍길동", age=78)
        agent = CareAgent(profile)
        ctx = agent.start_session()
        for _ in range(100):
            ctx, decision = agent.tick(ctx)
    """

    def __init__(self, profile: CareProfile, enable_llm: bool = True):
        self.profile   = profile
        self.memory    = AgentMemory()
        self._proto    = HandoffProtocol()
        self._monitor  = CareMonitor()

        # 선택적 레이어
        self._cognitive  = CognitiveAdapter() if _COGNITIVE_OK else None
        self._emergency  = EmergencyAdapter() if _EMERGENCY_OK else None
        self._chain      = CareChain() if _AUDIT_OK else None
        self._omega_mon  = OmegaMonitor() if _OMEGA_OK else None

        # 상태 벡터
        self.person_state  = PersonState()
        self.mission_state = MissionState(
            mission_id="default",
            description="일상 케어",
            origin=profile.home_location,
        )
        self.safety_state  = SafetyState()

        # 플랫폼
        self._platforms = {
            PlatformType.PET:        PetPlatform(),
            PlatformType.WHEELCHAIR: WheelchairPlatform(),
            PlatformType.CAR:        CarPlatform(),
        }
        self._current_platform: PlatformType = PlatformType.PET
        self._platforms[PlatformType.PET].attach(self)

        self._t_s = 0.0
        self._pending_token: Optional[HandoffToken] = None
        self._enable_llm = enable_llm
        self._last_omega: float = 1.0

        # 초기 감사 기록
        if self._chain:
            self._chain.record("session_start", PlatformType.PET, 0.0,
                               {"person_id": profile.person_id, "name": profile.name})

    @property
    def current_platform(self) -> PlatformType:
        return self._current_platform

    # ── 세션 시작 ─────────────────────────────────────────────────────

    def start_session(self) -> CareContext:
        return CareContext(
            profile=self.profile,
            platform=self._current_platform,
            memory=self.memory,
            t_s=self._t_s,
        )

    # ── 메인 틱 ──────────────────────────────────────────────────────

    def tick(self, ctx: CareContext) -> tuple[CareContext, CareDecision]:
        """에이전트 한 틱.

        파이프라인:
          1. 시간 동기화
          2. 인지 레이어 (감정·기억·행동) — Layer 3
          3. 현재 플랫폼 tick() — Layer 2
          4. LLM / 규칙 기반 케어 판단 — Layer 0
          5. 핸드오프 처리 — Layer 1
          6. 기억 + 안전 상태 업데이트
          7. 감사 기록 — Layer 4
        """
        self._t_s += ctx.dt_s
        ctx.t_s    = self._t_s
        ctx.platform = self._current_platform
        ctx.memory   = self.memory

        # ── 1. 인지 레이어 ───────────────────────────────────────────
        cog_omega = 1.0
        if self._cognitive:
            cog_report = self._cognitive.tick(ctx)
            cog_omega = cog_report.cognitive_omega
            # 감정 상태 → PersonState 반영
            self.person_state.valence = cog_report.emotion.valence
            self.person_state.arousal = cog_report.emotion.arousal

        # ── 2. 플랫폼 틱 ────────────────────────────────────────────
        platform = self._platforms[self._current_platform]
        decision = platform.tick(ctx)

        # ── 3. LLM 케어 판단 (보강) ──────────────────────────────────
        if decision.speak is None and not decision.emergency:
            llm_speak = self._llm_decide(ctx)
            if llm_speak:
                decision.speak = llm_speak

        # ── 4. Ω 통합 안전 판정 ─────────────────────────────────────
        bat_omega = float(ctx.extra.get("battery_omega", 1.0))
        if self._omega_mon:
            omega_report = self._omega_mon.tick(ctx, bat_omega, cog_omega)
            self._last_omega = omega_report.omega
            self.safety_state.omega   = omega_report.omega
            self.safety_state.verdict = omega_report.verdict
            if omega_report.emergency and not decision.emergency:
                decision.emergency = True
                decision.alert = " | ".join(omega_report.alerts[:3])

        # ── 5. 긴급 어댑터 ──────────────────────────────────────────
        if self._emergency and decision.emergency:
            flags = {
                "fall_detected":  ctx.extra.get("accel_g", 0.0) > 3.0,
                "shock_detected": ctx.extra.get("shock_g", 0.0) > 2.0,
            }
            emg_event = self._emergency.evaluate(ctx, flags)
            if emg_event:
                self.safety_state.emergency_triggered = True
                self.safety_state.emergency_contacts_notified = emg_event.contacts_notified != []

        # ── 6. 핸드오프 처리 ────────────────────────────────────────
        if decision.request_handoff and not self._pending_token:
            token = self._proto.initiate(ctx, decision.request_handoff)
            if token:
                self._pending_token = token
                decision.action = "handoff_initiated"
                if self._chain:
                    self._chain.record("handoff_initiated", ctx.platform, self._t_s, {
                        "to": decision.request_handoff.value,
                        "token_id": token.token_id[:8],
                    })

        # ── 7. 기억 업데이트 ─────────────────────────────────────────
        self._update_memory(ctx, decision)

        # ── 8. 감사 기록 (중요 이벤트만) ────────────────────────────
        if self._chain and decision.emergency:
            self._chain.record("emergency", ctx.platform, self._t_s, {
                "alert": decision.alert or "", "action": decision.action
            })
        if self._chain and decision.speak and ctx.t_s % 100 < ctx.dt_s:
            # 100초마다 한 번씩 대화 기록
            self._chain.record("care_conversation", ctx.platform, self._t_s, {
                "speak": decision.speak[:80]
            })

        return ctx, decision

    # ── 핸드오프 실행 ─────────────────────────────────────────────────

    def execute_handoff(self, ctx: CareContext) -> bool:
        if not self._pending_token:
            return False
        confirmed = self._proto.confirm(self._pending_token.token_id)
        if not confirmed:
            self._pending_token = None
            return False

        old_platform = self._platforms[self._current_platform]
        old_platform.detach()

        new_type     = confirmed.to_platform
        new_platform = self._platforms[new_type]
        new_platform.attach(self)
        new_platform.resume_from_token(confirmed, ctx)

        if self._chain:
            self._chain.record("handoff_completed", new_type, self._t_s, {
                "from": self._current_platform.value,
                "to":   new_type.value,
                "token": self._pending_token.token_id[:8],
            })

        self._current_platform = new_type
        self._pending_token    = None

        # 미션 상태 업데이트
        self.mission_state.completed_stages += 1

        log.info(f"[CareAgent] 핸드오프 완료: → {new_type.value}")
        return True

    def abort_handoff(self) -> bool:
        if not self._pending_token:
            return False
        self._proto.abort(self._pending_token.token_id)
        self._pending_token = None
        return True

    # ── 기억 업데이트 ─────────────────────────────────────────────────

    def _update_memory(self, ctx: CareContext, decision: CareDecision) -> None:
        # 피로도 누적
        if ctx.platform == PlatformType.PET:
            self.memory.fatigue_score = min(1.0, self.memory.fatigue_score + 0.00001)
        else:
            self.memory.fatigue_score = min(1.0, self.memory.fatigue_score + 0.00003)

        # PersonState 업데이트
        if ctx.vitals:
            self.person_state.heart_rate  = ctx.vitals.heart_rate_bpm
            self.person_state.spo2        = ctx.vitals.spo2_pct
            self.person_state.temperature = ctx.vitals.body_temp_c
            self.person_state.alert_level = ctx.vitals.alert_level
            self.person_state.pain_level  = ctx.vitals.pain_level
        self.person_state.fatigue = self.memory.fatigue_score

        # 투약 기록
        if "약 복용" in (decision.speak or ""):
            self.memory.last_medication_t_s = self._t_s

        # 대화 이력
        if decision.speak:
            self.memory.conversation_history.append(
                f"[{self._t_s:.1f}s][{ctx.platform.value}] {decision.speak}"
            )
            if len(self.memory.conversation_history) > 50:
                self.memory.conversation_history = self.memory.conversation_history[-50:]

        # 알림 누적
        if decision.alert:
            self.memory.alerts_today.append(decision.alert)

    # ── Claude API 연동 ───────────────────────────────────────────────

    def _llm_decide(self, ctx: CareContext) -> Optional[str]:
        """Claude API 케어 판단.

        설치 조건: pip install anthropic
        환경변수: ANTHROPIC_API_KEY

        미설치/미인증 시: 규칙 기반 폴백 (None 반환)
        """
        if not self._enable_llm:
            return None
        try:
            import anthropic
            client = anthropic.Anthropic()
            prompt = self._build_care_prompt(ctx)
            message = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=100,
                system=(
                    f"당신은 {ctx.profile.name}님(만 {ctx.profile.age}세)의 전담 AI 케어 보조입니다. "
                    f"따뜻하고 간결한 한국어로 케어 메시지를 생성하세요. "
                    f"한 문장, 30자 이내로 답하세요."
                ),
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text.strip()
        except Exception:
            return None

    def _build_care_prompt(self, ctx: CareContext) -> str:
        """케어 상황 요약 → Claude 프롬프트 생성."""
        platform_names = {
            PlatformType.PET:        "집 (AI 펫)",
            PlatformType.WHEELCHAIR: "이동 중 (휠체어)",
            PlatformType.CAR:        "이동 중 (자동차)",
        }
        lines = [
            f"현재 위치: {platform_names.get(ctx.platform, ctx.platform.value)}",
            f"피로도: {self.memory.fatigue_score:.0%}",
            f"기분 점수: {self.memory.mood_score:.0%}",
        ]
        if ctx.vitals:
            lines.append(f"HR={ctx.vitals.heart_rate_bpm:.0f} SpO2={ctx.vitals.spo2_pct:.0f}%")
        if ctx.destination:
            lines.append(f"목적지: {ctx.destination}")
        lines.append(f"케어 상황에 맞는 한 마디를 해주세요.")
        return "\n".join(lines)

    # ── 상태 조회 ─────────────────────────────────────────────────────

    def get_omega_report(self, ctx: CareContext) -> Optional["OmegaReport"]:
        if self._omega_mon:
            return self._omega_mon.tick(ctx)
        return None

    def summary(self) -> str:
        lines = [
            f"[CareAgent v0.2.0] {self.profile.name} (만 {self.profile.age}세)",
            f"  현재 플랫폼: {self._current_platform.value}",
            f"  피로도:     {self.memory.fatigue_score:.1%}",
            f"  Ω_care:    {self._last_omega:.3f} ({self.safety_state.verdict})",
            f"  오늘 알림:  {len(self.memory.alerts_today)}건",
            f"  대화 이력:  {len(self.memory.conversation_history)}개",
            f"  운영 시간:  {self._t_s:.0f}초",
            f"  미션 진행:  {self.mission_state.completion_ratio():.0%}",
        ]
        if self._chain:
            lines.append(f"  감사 체인:  {self._chain.length}개 블록")
        return "\n".join(lines)
