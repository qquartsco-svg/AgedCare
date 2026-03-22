"""AgedCare_Stack 공유 스키마.

모든 플랫폼(펫·휠체어·자동차)이 동일한 계약을 사용한다.
stdlib only — 외부 의존 없음.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ── 플랫폼 종류 ──────────────────────────────────────────────────────

class PlatformType(str, Enum):
    PET        = "pet"          # 홈 AI 펫 (집 내부)
    WHEELCHAIR = "wheelchair"   # 자율 휠체어
    CAR        = "car"          # 자율 자동차
    NONE       = "none"         # 전환 중 (핸드오프)


# ── 케어 대상자 프로파일 ──────────────────────────────────────────────

@dataclass
class MedicalInfo:
    conditions: Tuple[str, ...]   = ()       # 진단명
    medications: Tuple[str, ...]  = ()       # 복용 약물
    allergies: Tuple[str, ...]    = ()       # 알레르기
    mobility_level: float         = 1.0      # 이동 능력 [0=완전 의존, 1=독립]
    fall_risk: float              = 0.3      # 낙상 위험도 [0,1]

@dataclass
class CareProfile:
    """케어 대상자 개인 프로파일 — 모든 플랫폼에서 공유."""
    person_id: str
    name: str
    age: int
    medical: MedicalInfo = field(default_factory=MedicalInfo)
    home_location: Tuple[float, float] = (0.0, 0.0)   # (lat, lon) or (x, y)
    emergency_contacts: Tuple[str, ...] = ()
    preferences: Dict[str, Any] = field(default_factory=dict)


# ── 생체·환경 신호 ────────────────────────────────────────────────────

@dataclass(frozen=True)
class VitalSigns:
    """실시간 생체 신호."""
    heart_rate_bpm: float   = 70.0
    spo2_pct: float         = 98.0   # 산소포화도 (%)
    body_temp_c: float      = 36.5
    blood_pressure_sys: float = 120.0
    blood_pressure_dia: float = 80.0
    pain_level: float       = 0.0    # 주관적 통증 [0,10]
    alert_level: float      = 1.0    # 각성도 [0=무의식, 1=정상]
    t_s: float              = 0.0

    def is_critical(self) -> bool:
        return (
            self.heart_rate_bpm < 40 or self.heart_rate_bpm > 130
            or self.spo2_pct < 90.0
            or self.body_temp_c > 39.5 or self.body_temp_c < 35.0
            or self.alert_level < 0.3
        )

    def risk_score(self) -> float:
        """0=정상, 1=위험."""
        score = 0.0
        if self.heart_rate_bpm < 50 or self.heart_rate_bpm > 120: score += 0.3
        if self.spo2_pct < 94: score += 0.4
        if self.body_temp_c > 38.5: score += 0.2
        if self.alert_level < 0.5: score += 0.3
        return min(1.0, score)


@dataclass(frozen=True)
class EnvironmentFrame:
    """주변 환경 감지."""
    obstacle_detected: bool       = False
    obstacle_range_m: float       = 1e6
    floor_hazard: bool            = False   # 젖은 바닥 / 경사 등
    noise_db: float               = 40.0
    temperature_c: float          = 22.0
    humidity_pct: float           = 50.0
    location: Tuple[float, float] = (0.0, 0.0)
    indoor: bool                  = True


# ── AI 에이전트 상태 ──────────────────────────────────────────────────

@dataclass
class AgentMemory:
    """AI 에이전트 기억 — 플랫폼 전환 시 보존."""
    conversation_history: List[str] = field(default_factory=list)
    last_medication_t_s: float      = 0.0
    last_meal_t_s: float            = 0.0
    mood_score: float               = 0.7     # 추정 기분 [0,1]
    fatigue_score: float            = 0.0     # 피로도 [0,1]
    daily_steps: int                = 0
    alerts_today: List[str]         = field(default_factory=list)
    notes: Dict[str, Any]           = field(default_factory=dict)


@dataclass
class CareDecision:
    """AI 에이전트 결정 출력."""
    speak: Optional[str]            = None    # TTS 출력 메시지
    alert: Optional[str]            = None    # 알림 (보호자/응급)
    navigation_goal: Optional[Tuple[float, float]] = None
    request_handoff: Optional[PlatformType] = None  # 플랫폼 전환 요청
    emergency: bool                 = False
    action: str                     = "idle"  # idle/follow/navigate/assist


# ── 핸드오프 토큰 ─────────────────────────────────────────────────────

@dataclass
class HandoffToken:
    """플랫폼 간 전환 시 AI 상태를 담는 토큰."""
    token_id: str
    from_platform: PlatformType
    to_platform: PlatformType
    agent_memory: AgentMemory
    vitals_snapshot: Optional[VitalSigns] = None
    destination: Optional[Tuple[float, float]] = None
    confirmed: bool   = False
    aborted: bool     = False
    t_s: float        = 0.0


# ── 통합 케어 컨텍스트 ────────────────────────────────────────────────

@dataclass
class CareContext:
    """한 틱의 전체 케어 상태."""
    profile: CareProfile
    platform: PlatformType              = PlatformType.PET
    vitals: VitalSigns                  = field(default_factory=VitalSigns)
    environment: EnvironmentFrame       = field(default_factory=EnvironmentFrame)
    memory: AgentMemory                 = field(default_factory=AgentMemory)
    destination: Optional[Tuple[float, float]] = None
    t_s: float                          = 0.0
    dt_s: float                         = 0.1
    extra: Dict[str, Any]               = field(default_factory=dict)
