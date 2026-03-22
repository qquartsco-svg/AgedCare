"""BatteryMonitor — 다중 플랫폼 배터리 통합 감시."""
from __future__ import annotations
from dataclasses import dataclass
from ..contracts.schemas import CareContext

@dataclass
class MultiBatteryReport:
    wheelchair_pct: float = 100.0
    car_pct: float = 100.0
    pet_pct: float = 100.0
    combined_omega: float = 1.0
    critical: bool = False
    warning: bool = False

class BatteryMonitor:
    """전체 플랫폼 배터리 통합 감시."""

    def tick(self, ctx: CareContext) -> MultiBatteryReport:
        wc  = float(ctx.extra.get("wheelchair_battery_pct", 100.0))
        car = float(ctx.extra.get("car_battery_pct", 100.0))
        pet = float(ctx.extra.get("pet_battery_pct", 100.0))
        min_pct = min(wc, car, pet)
        omega = (1.00 if min_pct >= 80 else
                 0.85 if min_pct >= 50 else
                 0.65 if min_pct >= 30 else
                 0.40 if min_pct >= 15 else 0.10)
        return MultiBatteryReport(
            wheelchair_pct=wc, car_pct=car, pet_pct=pet,
            combined_omega=omega,
            critical=min_pct < 15,
            warning=min_pct < 30,
        )
