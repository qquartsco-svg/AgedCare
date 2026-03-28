"""AgedCare 휠체어 ↔ vehicle_platform_foundation / wheelchair_transform_system 연동."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from aged_care.bridges.wheelchair_physics import (
    evaluate_wheelchair_mobility_foundation,
    mobility_fsm_available,
    mobility_physics_available,
)
from aged_care.contracts.schemas import CareContext, PlatformType
from aged_care.platforms.wheelchair import WheelchairConfig, WheelchairPlatform


def _ctx() -> CareContext:
    from aged_care.contracts.schemas import AgentMemory, CareProfile

    return CareContext(
        profile=CareProfile(person_id="p1", name="Test", age=80),
        platform=PlatformType.WHEELCHAIR,
        memory=AgentMemory(),
        t_s=0.0,
        extra={},
    )


def test_mobility_flags_match_imports():
    try:
        import vehicle_platform_foundation  # noqa: F401
        expect_p = True
    except ImportError:
        expect_p = False
    try:
        import wheelchair_transform_system  # noqa: F401
        expect_f = True
    except ImportError:
        expect_f = False
    assert mobility_physics_available() is expect_p
    assert mobility_fsm_available() is expect_f


def test_evaluate_returns_mobility_dict():
    ctx = _ctx()
    cfg = WheelchairConfig()
    out = evaluate_wheelchair_mobility_foundation(ctx, cfg)
    assert "suggested_max_speed_ms" in out
    assert out["suggested_max_speed_ms"] <= cfg.max_speed_ms + 1e-6
    if out.get("physics_available"):
        assert "governing_accel_ms2" in out
        assert out["governing_accel_ms2"] >= 0.0
    if out.get("fsm_available"):
        assert out.get("fsm_phase") == "seated_idle"


@pytest.mark.skipif(
    not mobility_physics_available() or not mobility_fsm_available(),
    reason="staging stacks not on PYTHONPATH",
)
def test_wheelchair_platform_tick_injects_layer():
    plat = WheelchairPlatform()
    ctx = _ctx()
    ctx.destination = (10.0, 0.0)
    d = plat.tick(ctx)
    assert "wheelchair_mobility_layer" in ctx.extra
    layer = ctx.extra["wheelchair_mobility_layer"]
    assert layer.get("physics_available") is True
    assert layer.get("fsm_available") is True
    assert d.action in ("navigate", "stop", "idle", "emergency_stop", "initiate_handoff")
