> **English.** Korean (정본): [README.md](README.md)

# AgedCare_Stack

**One personal AI rides multiple bodies—pet, wheelchair, car—without losing continuity of care.**

v0.2.2 · Python 3.9+ · stdlib core (external engines optional)

> **Prototype notice**  
> This is a **software prototype** for continuous personal-care orchestration.  
> It is **not** a certified medical device or production autonomy product. Real deployments need hardware integration, safety certification, and clinical validation.

---

## What this is

Not three separate robot products. **One AI** stays with the person; **bodies** swap (pet at home, wheelchair for local mobility, car for long trips). Memory, dialogue, and health context stay aligned across handoffs.

---

## Wheelchair mobility foundation (v0.2.1+)

When the active body is the wheelchair, `WheelchairPlatform` calls `aged_care/bridges/wheelchair_physics.py` each tick:

1. **`vehicle_platform_foundation`** (GitHub mirror [**4WD**](https://github.com/qquartsco-svg/4WD)) — mass, axle loads, traction/power screening via `assess_platform`.
2. **`wheelchair_transform_system`** — seated FSM probe via `run_phase_tick(SEATED_IDLE, …)` (HAL / stand-transfer stack under the same 00_BRAIN lineage).

Results are stored in `CareContext.extra["wheelchair_mobility_layer"]`.  
`suggested_max_speed_ms` caps navigation speed. If sibling packages are not on `PYTHONPATH`, flags stay `False` and built-in fallbacks run—**the care core always works**.

**Monorepo checkout:** `tests/conftest.py` prepends sibling `_staging/Vehicle_Platform_Foundation` and `_staging/Wheelchair_Transform_System` so `pytest` sees them.

---

## Integrity (blockchain-style manifest)

| File | Purpose |
|------|---------|
| `SIGNATURE.sha256` | SHA-256 per tracked file |
| `BLOCKCHAIN_INFO.md` / `BLOCKCHAIN_INFO_EN.md` | Policy + release blocks |
| `PHAM_BLOCKCHAIN_LOG.md` | Release notes trail |

```bash
python scripts/regenerate_signature.py
python scripts/verify_signature.py
python -m pytest tests/ -q
```

---

## Quick start

```bash
git clone https://github.com/qquartsco-svg/AgedCare.git
cd AgedCare_Stack
pip install -e ".[dev]"
```

```python
from aged_care import CareAgent, CareProfile, MedicalInfo, VitalSigns

profile = CareProfile(
    person_id="001",
    name="Example",
    age=78,
    medical=MedicalInfo(fall_risk=0.4),
    home_location=(37.5665, 126.9780),
    emergency_contacts=("000-0000-0000",),
)
agent = CareAgent(profile)
ctx = agent.start_session()
ctx.vitals = VitalSigns(heart_rate_bpm=72, spo2_pct=97)
for _ in range(10):
    ctx, decision = agent.tick(ctx)
```

---

## Optional engines

All wrapped in `try/except ImportError`. See the Korean README table for Amygdala, Autonomy_Runtime_Stack, Claude, etc.

---

## License

[LICENSE](LICENSE) — MIT (quarts co. / GNJz)

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
