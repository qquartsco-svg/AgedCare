"""EmotionEngine — 감정 상태 추론.

Valence-Arousal 2D 감정 공간:
  E = √(V² + A²)   감정 강도 (magnitude)
  θ = arctan(A/V)  감정 방향 (angle)

외부 엔진 연동:
  AmygdalaEngine (ENGINE_HUB/20_LIMBIC_LAYER/Amygdala_Engine)
  → 미설치 시: 생체신호 기반 규칙 폴백
"""
from __future__ import annotations
import math, sys, os
from dataclasses import dataclass
from typing import Optional
from ..contracts.schemas import CareContext

ENGINE_HUB_PATH = os.path.join(
    os.path.dirname(__file__), "../../../../02_SYSTEMS/ENGINE_HUB/2_operational"
)

@dataclass
class EmotionState:
    valence: float = 0.5      # [-1, 1] → 정규화된 [0, 1], 0.5=중립
    arousal: float = 0.3      # [0, 1]
    magnitude: float = 0.0    # E = √(V²+A²)
    angle_deg: float = 0.0    # θ
    label: str = "neutral"    # calm/happy/anxious/distressed/fearful

class EmotionEngine:
    """감정 상태 추론 엔진.

    AmygdalaEngine 미설치 시 폴백:
      valence ← 1 - pain_norm - fatigue*0.5
      arousal ← HR_norm * 0.7 + pain_norm * 0.3
    """

    EMOTION_LABELS = {
        (True,  True):  "distressed",  # 부정적 + 고각성
        (True,  False): "sad",         # 부정적 + 저각성
        (False, True):  "anxious",     # 긍정적 + 고각성 (흥분/불안)
        (False, False): "calm",        # 긍정적 + 저각성
    }

    def __init__(self):
        self._amygdala = self._try_load_amygdala()

    def _try_load_amygdala(self):
        try:
            amygdala_dir = os.path.join(
                ENGINE_HUB_PATH,
                "20_LIMBIC_LAYER/Amygdala_Engine/package"
            )
            sys.path.insert(0, amygdala_dir)
            from amygdala.amygdala_engine import AmygdalaEngine
            return AmygdalaEngine()
        except Exception:
            return None

    def assess(self, ctx: CareContext) -> EmotionState:
        """현재 컨텍스트에서 감정 상태 추론."""
        if self._amygdala is not None:
            return self._assess_amygdala(ctx)
        return self._assess_fallback(ctx)

    def _assess_amygdala(self, ctx: CareContext) -> EmotionState:
        try:
            # AmygdalaEngine API: threat signal detection
            # 생체신호로 위협 텍스트 조합
            hr = ctx.vitals.heart_rate_bpm if ctx.vitals else 72.0
            pain = ctx.vitals.pain_level if ctx.vitals else 0.0
            signal_text = f"heart rate {hr:.0f} pain {pain:.1f}"
            result = self._amygdala.process(signal_text)
            # result has .valence_arousal or similar — adapt
            v = getattr(result, 'valence', 0.5)
            a = getattr(result, 'arousal', 0.3)
            return self._make_state(v, a)
        except Exception:
            return self._assess_fallback(ctx)

    def _assess_fallback(self, ctx: CareContext) -> EmotionState:
        """규칙 기반 폴백."""
        fatigue = ctx.memory.fatigue_score if ctx.memory else 0.0
        mood    = ctx.memory.mood_score if ctx.memory else 0.7
        pain    = 0.0
        hr      = 72.0
        if ctx.vitals:
            pain = ctx.vitals.pain_level / 10.0   # normalize to [0,1]
            # HR 정규화 (50=0, 100=0.5, 150=1)
            hr = max(0.0, min(1.0, (ctx.vitals.heart_rate_bpm - 50) / 100.0))

        # Valence: 기분 - 고통 - 피로 영향
        v = max(0.0, min(1.0, mood - pain * 0.5 - fatigue * 0.3))
        # Arousal: HR + 고통 + 외부 자극
        a = max(0.0, min(1.0, hr * 0.5 + pain * 0.3 + fatigue * 0.2))
        return self._make_state(v, a)

    @staticmethod
    def _make_state(v: float, a: float) -> EmotionState:
        v_c = v - 0.5  # 중립 보정
        mag = math.sqrt(v_c**2 + a**2)
        angle = math.degrees(math.atan2(a, v_c + 1e-9))
        negative = v < 0.4
        high_arousal = a > 0.5
        label = EmotionEngine.EMOTION_LABELS.get((negative, high_arousal), "neutral")
        return EmotionState(valence=v, arousal=a, magnitude=mag, angle_deg=angle, label=label)
