"""AgedCare_Stack — 범용 AI 케어 시스템 v0.2.0.

AI 펫 → 자율 휠체어 → 자율 자동차 → 자율 휠체어 → AI 펫
하나의 AI 에이전트가 모든 플랫폼에서 연속으로 케어한다.
"""
from .care_agent import CareAgent
from .monitor    import CareMonitor, MonitorResult
from .handoff.protocol import HandoffProtocol
from .platforms.pet        import PetPlatform
from .platforms.wheelchair import WheelchairPlatform
from .platforms.car        import CarPlatform
from .contracts.schemas import (
    CareProfile, CareContext, CareDecision, HandoffToken,
    PlatformType, VitalSigns, EnvironmentFrame, AgentMemory,
    MedicalInfo, PersonState, MissionState, SafetyState,
    ScheduleEvent, CareGoal,
)

# ── 선택적 임포트 (Edge AI: 없어도 작동) ──────────────────────────────
try:
    from .adapters.cognitive_adapter import CognitiveAdapter
except Exception:
    pass

try:
    from .adapters.battery_adapter import BatteryAdapter
except Exception:
    pass

try:
    from .adapters.emergency_adapter import EmergencyAdapter
except Exception:
    pass

try:
    from .audit.care_chain import CareChain
except Exception:
    pass

try:
    from .monitor.omega import OmegaMonitor
except Exception:
    pass

# 깔끔한 공개 API
__all__ = [
    "CareAgent",
    "CareMonitor", "MonitorResult",
    "HandoffProtocol",
    "PetPlatform", "WheelchairPlatform", "CarPlatform",
    "CareProfile", "CareContext", "CareDecision", "HandoffToken",
    "PlatformType", "VitalSigns", "EnvironmentFrame",
    "AgentMemory", "MedicalInfo",
    "PersonState", "MissionState", "SafetyState",
    "ScheduleEvent", "CareGoal",
    "CognitiveAdapter",
    "BatteryAdapter",
    "EmergencyAdapter",
    "CareChain",
    "OmegaMonitor",
]
