"""ActionEngine — 행동 선택 + 실행 제어.

기저핵 (BasalGanglia) — 강화학습 행동 선택:
  TD 오차: δ = r + γV(s') - V(s)
  Actor 업데이트: π(s,a) ← π(s,a) + α·δ

전전두피질 (PrefrontalCortex) — 작업 기억 + 억제 제어:
  작업 기억 용량: 7 ± 2 슬롯
  의사결정 충돌 해소

외부 엔진:
  BasalGanglia_Engine (ENGINE_HUB/20_LIMBIC_LAYER/BasalGanglia_Engine)
  PrefrontalCortex_Engine (ENGINE_HUB/30_CORTEX_LAYER/PrefrontalCortex_Engine)
"""
from __future__ import annotations
import sys, os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

ENGINE_HUB_PATH = os.path.join(
    os.path.dirname(__file__), "../../../../02_SYSTEMS/ENGINE_HUB/2_operational"
)

@dataclass
class ActionScore:
    action: str
    q_value: float = 0.0            # Q(s, a) 추정값
    priority: int = 5               # 1=최고 우선순위
    rationale: str = ""             # 선택 이유

class ActionEngine:
    """행동 선택 엔진.

    우선순위:
      1. 긴급 (emergency) > 2. 핸드오프 > 3. 케어 루틴 > 4. 대화

    폴백: 규칙 기반 우선순위 정렬
    """
    CARE_ACTIONS = [
        "emergency_stop", "emergency_route", "initiate_handoff",
        "navigate", "remind_medication", "remind_meal",
        "follow", "converse", "idle"
    ]

    def __init__(self):
        self._bg   = self._try_load_basal_ganglia()
        self._pfc  = self._try_load_pfc()
        self._q: Dict[str, float] = {a: 0.0 for a in self.CARE_ACTIONS}

    def _try_load_basal_ganglia(self):
        try:
            bg_dir = os.path.join(ENGINE_HUB_PATH, "20_LIMBIC_LAYER/BasalGanglia_Engine")
            sys.path.insert(0, bg_dir)
            from rl import ActorCritic
            return ActorCritic(n_states=10, n_actions=len(self.CARE_ACTIONS))
        except Exception:
            return None

    def _try_load_pfc(self):
        try:
            pfc_dir = os.path.join(ENGINE_HUB_PATH, "30_CORTEX_LAYER/PrefrontalCortex_Engine")
            sys.path.insert(0, pfc_dir)
            from core import PrefrontalCortexEngine
            return PrefrontalCortexEngine()
        except Exception:
            return None

    def select_action(self, context_flags: Dict[str, bool],
                      available_actions: Optional[List[str]] = None) -> ActionScore:
        """컨텍스트 플래그 기반 최적 행동 선택.

        context_flags:
          emergency, handoff_ready, medication_due, destination_set,
          at_home, car_ready, arrived, fall_detected
        """
        available = available_actions or self.CARE_ACTIONS

        # 규칙 기반 우선순위 (항상 적용)
        rule_scores = self._rule_priority(context_flags, available)

        # BasalGanglia Q-value (있으면 반영)
        if self._bg is not None:
            try:
                state_vec = self._flags_to_state(context_flags)
                for i, act in enumerate(available):
                    if i < len(self.CARE_ACTIONS):
                        q = self._bg.get_q(state_vec, i) if hasattr(self._bg, 'get_q') else 0.0
                        if act in rule_scores:
                            rule_scores[act] = rule_scores[act] * 0.7 + q * 0.3
            except Exception:
                pass

        best = max(rule_scores, key=lambda a: rule_scores[a])
        return ActionScore(action=best, q_value=rule_scores[best],
                           priority=1 if "emergency" in best else 5)

    def _rule_priority(self, flags: Dict[str, bool],
                       available: List[str]) -> Dict[str, float]:
        scores: Dict[str, float] = {a: 0.0 for a in available}
        if flags.get("emergency"):
            if "emergency_stop" in scores:   scores["emergency_stop"] = 1.0
            if "emergency_route" in scores:  scores["emergency_route"] = 0.95
        if flags.get("handoff_ready"):
            if "initiate_handoff" in scores: scores["initiate_handoff"] = 0.9
        if flags.get("destination_set"):
            if "navigate" in scores:         scores["navigate"] = 0.7
        if flags.get("medication_due"):
            if "remind_medication" in scores: scores["remind_medication"] = 0.6
        if flags.get("meal_due"):
            if "remind_meal" in scores:      scores["remind_meal"] = 0.55
        if "follow" in scores and not any(scores.values()):
            scores["follow"] = 0.3
        if "idle" in scores and not any(scores.values()):
            scores["idle"] = 0.1
        return scores

    def update_reward(self, action: str, reward: float, t_s: float) -> None:
        """강화 신호 업데이트 (TD learning)."""
        if action in self._q:
            # 단순 지수 평활 업데이트 (TD 근사)
            alpha = 0.1
            self._q[action] = self._q[action] + alpha * (reward - self._q[action])

    @staticmethod
    def _flags_to_state(flags: Dict[str, bool]) -> List[float]:
        keys = ["emergency", "handoff_ready", "medication_due", "destination_set",
                "at_home", "car_ready", "arrived", "fall_detected", "obstacle", "fatigue_high"]
        return [1.0 if flags.get(k) else 0.0 for k in keys]
