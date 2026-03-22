"""SNNAdapter — 스파이킹 신경망 기반 생체신호 패턴 분류.

SNN_Backend_Engine 연동 (선택):
  /Users/jazzin/Desktop/00_BRAIN/_staging/SNN_Backend_Engine
  - LIF / Izhikevich / HH 뉴런 모델
  - AER 이벤트 인코딩
  - STDP 소성

미설치 시: 임계값 기반 규칙 폴백
"""
from __future__ import annotations
import sys, os
from dataclasses import dataclass
from typing import List, Optional, Tuple
from ..contracts.schemas import CareContext, VitalSigns

SNN_PATH = os.path.join(
    os.path.dirname(__file__),
    "../../../../_staging/SNN_Backend_Engine"
)

@dataclass
class SpikePattern:
    firing_rate_hz: float = 0.0         # 스파이크 발화율
    burst_detected: bool = False        # 버스트 감지 (급격한 생체 변화)
    pattern_label: str = "normal"       # normal / stress / crisis / recovery
    confidence: float = 1.0

class SNNAdapter:
    """SNN 기반 생체신호 패턴 분류기.

    생체신호 → AER 이벤트 인코딩 → LIF 뉴런 → 패턴 분류

    발화율 패턴:
      정상:    2–8 Hz
      스트레스: 8–15 Hz
      위기:    > 15 Hz 또는 버스트
      회복:    1–3 Hz (감소 추세)
    """

    def __init__(self, n_neurons: int = 16):
        self._n = n_neurons
        self._network = self._try_load_snn()
        self._prev_pattern = "normal"

    def _try_load_snn(self):
        try:
            sys.path.insert(0, SNN_PATH)
            from snn_backends import SNNNetwork, LIFSomaBackend
            net = SNNNetwork(n_neurons=self._n, backend=LIFSomaBackend())
            return net
        except Exception:
            return None

    def encode_vitals(self, vitals: VitalSigns) -> List[float]:
        """생체신호 → 정규화 입력 벡터."""
        hr_norm   = max(0.0, min(1.0, (vitals.heart_rate_bpm - 40) / 120.0))
        spo2_norm = max(0.0, min(1.0, (vitals.spo2_pct - 85) / 15.0))
        temp_norm = max(0.0, min(1.0, (vitals.body_temp_c - 35.0) / 5.0))
        pain_norm = vitals.pain_level / 10.0
        alert_norm = vitals.alert_level
        return [hr_norm, spo2_norm, temp_norm, pain_norm, alert_norm,
                1.0 - alert_norm, hr_norm * spo2_norm, pain_norm * hr_norm]

    def classify(self, ctx: CareContext) -> SpikePattern:
        """생체신호 패턴 분류."""
        if ctx.vitals is None:
            return SpikePattern(pattern_label="unknown", confidence=0.5)

        input_vec = self.encode_vitals(ctx.vitals)

        if self._network is not None:
            try:
                result = self._network.step(input_vec)
                rate = float(getattr(result, 'mean_firing_rate', sum(input_vec) * 10))
                burst = getattr(result, 'burst_detected', False)
                return self._classify_from_rate(rate, burst)
            except Exception:
                pass

        # 폴백: 규칙 기반
        return self._fallback_classify(ctx.vitals)

    def _classify_from_rate(self, rate_hz: float, burst: bool) -> SpikePattern:
        if burst or rate_hz > 15.0:
            label, conf = "crisis", 0.85
        elif rate_hz > 8.0:
            label, conf = "stress", 0.75
        elif rate_hz < 3.0 and self._prev_pattern in ("stress", "crisis"):
            label, conf = "recovery", 0.70
        else:
            label, conf = "normal", 0.90
        self._prev_pattern = label
        return SpikePattern(firing_rate_hz=rate_hz, burst_detected=burst,
                            pattern_label=label, confidence=conf)

    def _fallback_classify(self, v: VitalSigns) -> SpikePattern:
        crisis = (v.heart_rate_bpm > 130 or v.heart_rate_bpm < 40
                  or v.spo2_pct < 90 or v.body_temp_c > 39.5)
        stress = (v.heart_rate_bpm > 100 or v.spo2_pct < 94
                  or v.pain_level > 5)
        if crisis:
            label, rate = "crisis", 18.0
        elif stress:
            label, rate = "stress", 10.0
        else:
            label, rate = "normal", 4.0
        return SpikePattern(firing_rate_hz=rate, pattern_label=label, confidence=0.80)
