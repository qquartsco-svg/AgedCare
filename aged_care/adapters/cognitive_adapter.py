"""CognitiveAdapter — 인지 엔진들을 CareContext로 브리지.

EmotionEngine + MemoryEngine + ActionEngine → CareContext 갱신
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from ..contracts.schemas import CareContext, PersonState
from ..cognitive.emotion_engine import EmotionEngine, EmotionState
from ..cognitive.memory_engine import MemoryEngine
from ..cognitive.action_engine import ActionEngine

@dataclass
class CognitiveReport:
    emotion: EmotionState
    recommended_action: str = "idle"
    cognitive_omega: float = 1.0      # Ω_cognitive ∈ [0, 1]
    alert: Optional[str] = None

class CognitiveAdapter:
    """인지 레이어 어댑터 — 모든 인지 엔진을 하나의 인터페이스로."""

    def __init__(self):
        self.emotion  = EmotionEngine()
        self.memory   = MemoryEngine()
        self.action   = ActionEngine()

    def tick(self, ctx: CareContext) -> CognitiveReport:
        """인지 레이어 틱.

        1. 감정 상태 추론 (Amygdala)
        2. Ω_cognitive 계산
        3. 행동 추천 (BasalGanglia + PFC)
        4. 중요 이벤트 기억 인코딩 (Hippocampus)
        """
        emotion = self.emotion.assess(ctx)

        # Ω_cognitive: 감정 안정 + 인지 각성도
        # 부정 감정(valence<0.3) + 고각성(arousal>0.7) → 위험
        v_score = emotion.valence                     # 높을수록 좋음
        a_penalty = max(0.0, emotion.arousal - 0.6)  # 0.6 초과 시 패널티
        alert_level = ctx.vitals.alert_level if ctx.vitals else 1.0
        omega_cog = min(1.0, max(0.0,
            v_score * 0.5 + alert_level * 0.3 + (1 - a_penalty) * 0.2
        ))

        # 중요 이벤트 기억 (핸드오프, 응급, 투약)
        important_events = []
        if ctx.extra.get("go_out"):
            important_events.append(("외출 시작", ctx.profile.home_location, ["mobility", "handoff"]))
        if ctx.extra.get("arrived"):
            if ctx.destination:
                important_events.append(("목적지 도착", ctx.destination, ["arrival"]))
        for content, loc, tags in important_events:
            self.memory.encode(content, loc, ctx.t_s, tags=tags, importance=0.8)

        # 행동 추천
        context_flags = {
            "emergency":      ctx.extra.get("emergency", False),
            "handoff_ready":  any(ctx.extra.get(k) for k in ["go_out", "car_ready", "arrived", "at_home"]),
            "medication_due": ctx.extra.get("medication_due", False),
            "destination_set": ctx.destination is not None,
            "at_home":        ctx.extra.get("at_home", False),
            "car_ready":      ctx.extra.get("car_ready", False),
            "arrived":        ctx.extra.get("arrived", False),
            "fall_detected":  ctx.extra.get("accel_g", 0.0) > 3.0,
            "fatigue_high":   ctx.memory.fatigue_score > 0.75 if ctx.memory else False,
        }
        action_score = self.action.select_action(context_flags)

        # 감정 위기 알림
        alert = None
        if emotion.label in ("distressed", "fearful") and omega_cog < 0.4:
            alert = f"[주의] 감정 불안정 감지 (V={emotion.valence:.2f}, A={emotion.arousal:.2f})"

        return CognitiveReport(
            emotion=emotion,
            recommended_action=action_score.action,
            cognitive_omega=omega_cog,
            alert=alert,
        )

    def update_reward(self, action: str, reward: float, t_s: float) -> None:
        """행동 결과 피드백 → 강화학습 업데이트."""
        self.action.update_reward(action, reward, t_s)
