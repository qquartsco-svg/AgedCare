"""Optional bridges to 00_BRAIN mobility stacks (stdlib-safe fallbacks)."""
from __future__ import annotations

from .wheelchair_physics import (
    evaluate_wheelchair_mobility_foundation,
    mobility_physics_available,
    mobility_fsm_available,
)

__all__ = [
    "evaluate_wheelchair_mobility_foundation",
    "mobility_physics_available",
    "mobility_fsm_available",
]
