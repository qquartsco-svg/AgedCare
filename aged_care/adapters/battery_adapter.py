"""BatteryAdapter — 배터리 상태 모니터링.

Battery_Dynamics_Engine 연동 (선택):
  /Users/jazzin/Desktop/00_BRAIN/_staging/Battery_Dynamics_Engine

미설치 시: SOC 직접 읽기 폴백 (ctx.extra["battery_pct"])
"""
from __future__ import annotations
import sys, os
from dataclasses import dataclass
from typing import Optional
from ..contracts.schemas import CareContext, PlatformType

BATTERY_ENGINE_PATH = os.path.join(
    os.path.dirname(__file__),
    "../../../../_staging/Battery_Dynamics_Engine"
)

@dataclass
class BatteryReport:
    soc_pct: float = 100.0              # State of Charge [0, 100]
    is_critical: bool = False           # < 15%
    is_low: bool = False                # < 30%
    estimated_range_km: Optional[float] = None
    omega_battery: float = 1.0         # Ω_battery

    CRITICAL_PCT = 15.0
    LOW_PCT = 30.0

class BatteryAdapter:
    """배터리 어댑터.

    Ω_battery:
      SOC ≥ 80%  → 1.00
      SOC ≥ 50%  → 0.85
      SOC ≥ 30%  → 0.65
      SOC ≥ 15%  → 0.40
      SOC < 15%  → 0.10  (긴급 충전 필요)
    """

    def __init__(self, platform: PlatformType = PlatformType.WHEELCHAIR):
        self._platform = platform
        self._pack = self._try_load_battery_engine()
        self._soc_pct = 100.0

    def _try_load_battery_engine(self):
        try:
            sys.path.insert(0, BATTERY_ENGINE_PATH)
            from battery_pack import build_pack_state
            return build_pack_state()
        except Exception:
            return None

    def tick(self, ctx: CareContext) -> BatteryReport:
        """배터리 상태 틱."""
        # 플랫폼별 배터리 키
        key = {
            PlatformType.WHEELCHAIR: "wheelchair_battery_pct",
            PlatformType.CAR:        "car_battery_pct",
            PlatformType.PET:        "pet_battery_pct",
        }.get(self._platform, "battery_pct")

        if self._pack is not None:
            try:
                # Battery_Dynamics_Engine API
                self._soc_pct = getattr(self._pack, 'soc_pct', 100.0)
            except Exception:
                self._soc_pct = float(ctx.extra.get(key, 100.0))
        else:
            self._soc_pct = float(ctx.extra.get(key, 100.0))

        soc = self._soc_pct
        omega = (1.00 if soc >= 80 else
                 0.85 if soc >= 50 else
                 0.65 if soc >= 30 else
                 0.40 if soc >= 15 else 0.10)

        # 주행 가능 거리 추정 (휠체어: 30Wh @ 1.5m/s, 자동차: 60kWh @ 30km/h)
        range_km = None
        if self._platform == PlatformType.WHEELCHAIR:
            range_km = (soc / 100.0) * 20.0        # 최대 20km 가정
        elif self._platform == PlatformType.CAR:
            range_km = (soc / 100.0) * 300.0       # 최대 300km 가정

        return BatteryReport(
            soc_pct=soc,
            is_critical=soc < BatteryReport.CRITICAL_PCT,
            is_low=soc < BatteryReport.LOW_PCT,
            estimated_range_km=range_km,
            omega_battery=omega,
        )

    def simulate_discharge(self, dt_s: float, current_a: float = 5.0) -> None:
        """방전 시뮬레이션 (Battery 엔진 없을 때 간단 모델)."""
        # Q = I × t, 100Ah 배터리 가정
        self._soc_pct = max(0.0, self._soc_pct - (current_a * dt_s / 3600.0 / 100.0) * 100.0)
