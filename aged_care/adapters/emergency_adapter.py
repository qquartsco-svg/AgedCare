"""EmergencyAdapter — 긴급 연락 및 통지 시스템.

역할:
  - 응급 상황 감지 시 보호자 연락
  - 119 신고 (시뮬레이션)
  - 이벤트 로그 기록
  - 쿨다운으로 알림 폭주 방지 (180초 기본)
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from ..contracts.schemas import CareContext, CareProfile, PlatformType

log = logging.getLogger(__name__)

@dataclass
class EmergencyEvent:
    t_s: float
    event_type: str              # "fall" | "vitals_critical" | "battery_critical" | "lost_contact"
    platform: PlatformType
    location: Optional[Tuple[float, float]]
    description: str
    contacts_notified: List[str] = field(default_factory=list)
    ems_notified: bool = False

class EmergencyAdapter:
    """긴급 연락 어댑터.

    실제 알림 채널 (확장 포인트):
      - SMS: Twilio / KakaoTalk API
      - 119: 공공 API (향후 연동)
      - 병원 시스템: HL7 FHIR (향후 연동)

    현재: 로컬 로그 + 이벤트 큐
    """

    COOLDOWN_S = 180.0    # 같은 유형 재알림 대기시간

    def __init__(self):
        self._events: List[EmergencyEvent] = []
        self._last_notified: dict = {}   # event_type → t_s

    def evaluate(self, ctx: CareContext, flags: dict) -> Optional[EmergencyEvent]:
        """응급 상황 평가 + 필요시 통지."""
        event_type = self._detect_event_type(ctx, flags)
        if event_type is None:
            return None

        # 쿨다운 확인
        last = self._last_notified.get(event_type, -self.COOLDOWN_S * 2)
        if ctx.t_s - last < self.COOLDOWN_S:
            return None

        event = EmergencyEvent(
            t_s=ctx.t_s,
            event_type=event_type,
            platform=ctx.platform,
            location=ctx.environment.location if ctx.environment else None,
            description=self._describe(event_type, ctx),
        )

        self._notify(event, ctx.profile)
        self._last_notified[event_type] = ctx.t_s
        self._events.append(event)
        return event

    def _detect_event_type(self, ctx: CareContext, flags: dict) -> Optional[str]:
        if flags.get("fall_detected"):
            return "fall"
        if ctx.vitals and ctx.vitals.is_critical():
            return "vitals_critical"
        if flags.get("battery_critical"):
            return "battery_critical"
        if flags.get("shock_detected"):
            return "vehicle_shock"
        return None

    def _describe(self, event_type: str, ctx: CareContext) -> str:
        name = ctx.profile.name
        descriptions = {
            "fall":             f"{name}님 낙상 감지 — 즉시 확인 필요",
            "vitals_critical":  f"{name}님 생체신호 위험 — HR/SpO2/체온 이상",
            "battery_critical": f"{name}님 기기 배터리 위험 (<15%) — 충전 필요",
            "vehicle_shock":    f"{name}님 차량 충격 감지 — 사고 가능성",
            "lost_contact":     f"{name}님 연락 두절 — 위치 확인 필요",
        }
        return descriptions.get(event_type, f"{name}님 알 수 없는 응급 상황")

    def _notify(self, event: EmergencyEvent, profile: CareProfile) -> None:
        """실제 통지 실행 (현재: 로컬 로그).

        확장 포인트:
            # SMS
            # import twilio; client.messages.create(...)

            # KakaoTalk API
            # kakao.send_message(contacts, event.description)
        """
        for contact in profile.emergency_contacts:
            log.warning(f"[EMERGENCY] {event.description} -> {contact}")
            event.contacts_notified.append(contact)

        if event.event_type in ("fall", "vitals_critical", "vehicle_shock"):
            log.warning(f"[EMS] 119 신고 — {event.description}")
            event.ems_notified = True

    def get_recent_events(self, n: int = 5) -> List[EmergencyEvent]:
        return self._events[-n:]

    def clear_history(self) -> None:
        self._events.clear()
        self._last_notified.clear()
