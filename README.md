# AgedCare_Stack

> 하나의 AI 에이전트가 AI 펫 · 자율 휠체어 · 자율 자동차를 넘나들며
> 노인을 집에서 병원까지, 병원에서 다시 집까지 끊김 없이 케어한다.

---

## 개요

```
[집] 🐾 AI 펫
  └─ 핸드오프 →
       ♿ 자율 휠체어 (집 → 자동차)
         └─ 핸드오프 →
              🚗 자율 자동차 (자율주행 → 목적지)
                └─ 핸드오프 →
                     ♿ 자율 휠체어 (목적지 내 이동)
                       └─ 핸드오프 →
                            🚗 자율 자동차 (귀가 자율주행)
                              └─ 핸드오프 →
                                   ♿ 자율 휠체어 (귀가 이동)
                                     └─ 핸드오프 →
                                          🐾 AI 펫 (귀가 케어)
```

**플랫폼은 바뀌어도 AI 에이전트는 하나다.**
`CareAgent` 는 모든 하드웨어 위에서 동일한 기억·대화·모니터링을 유지한다.

---

## 핵심 설계 원칙

| 원칙 | 내용 |
|------|------|
| **지속 에이전트** | `CareAgent` 는 플랫폼 전환 시에도 메모리 보존 |
| **토큰 기반 핸드오프** | SHA-256 토큰으로 플랫폼 전환을 안전하게 검증 |
| **Ω 케어 안전 지수** | 생체 × 피로 × 환경 × 투약 — 복합 안전 판정 |
| **페일세이프** | 핸드오프 중단 시 원래 플랫폼 자동 유지 |
| **선택적 외부 연동** | SYD_DRIFT·Autonomy_Runtime_Stack·Claude API — 미설치 시 내장 폴백 |
| **표준 라이브러리** | 코어는 stdlib 전용 — 엣지 AI 배포 가능 |

---

## 폴더 구조

```
AgedCare_Stack/
├── aged_care/
│   ├── __init__.py
│   ├── care_agent.py          — CareAgent (지속 AI 에이전트)
│   ├── monitor.py             — CareMonitor (Ω 케어 안전 지수)
│   ├── contracts/
│   │   ├── __init__.py
│   │   └── schemas.py         — 데이터 계약 (PlatformType, VitalSigns 등)
│   ├── handoff/
│   │   ├── __init__.py
│   │   └── protocol.py        — HandoffProtocol (토큰 기반 플랫폼 전환)
│   └── platforms/
│       ├── __init__.py
│       ├── base.py            — PlatformBase ABC
│       ├── pet.py             — PetPlatform (AI 펫)
│       ├── wheelchair.py      — WheelchairPlatform (자율 휠체어)
│       └── car.py             — CarPlatform (자율 자동차)
├── examples/
│   └── run_care_journey.py    — 7단계 전체 여정 시뮬레이션
├── tests/
│   └── test_aged_care.py      — §1~§7 단위·통합 테스트 (50+ 케이스)
├── pyproject.toml
└── README.md
```

---

## 상태 스키마

### VitalSigns (생체 신호)

| 필드 | 단위 | 임계치 |
|------|------|--------|
| `heart_rate_bpm` | bpm | < 50 또는 > 120 → 위험 |
| `spo2_pct` | % | < 92 → 위험 |
| `body_temp_c` | °C | > 38.5 → 위험 |
| `systolic_bp` | mmHg | > 180 → 위험 |

### Ω 케어 안전 지수

```
Ω = ω_vitals × ω_fatigue × ω_env × ω_medication

판정:
  SAFE       Ω ≥ 0.80   — 정상 케어
  CAUTION    Ω ≥ 0.50   — 주의 (이벤트 발생 가능)
  WARNING    Ω ≥ 0.25   — 경고 (보호자 알림)
  EMERGENCY  Ω < 0.25   — 긴급 (119·보호자 즉시 연락)
```

### 허용 핸드오프 전환

```
PET  ↔  WHEELCHAIR  ↔  CAR
         (단방향 허용 없음: PET → CAR 직접 불가)
```

---

## 플랫폼별 역할

### 🐾 PetPlatform
- 집 내부 동반 (음성 대화·생체 모니터링·낙상 감지)
- 투약 알림 (마지막 투약 후 8시간 경과 시)
- `go_out=True` 신호 수신 → 휠체어 핸드오프 요청

### ♿ WheelchairPlatform
- 자율 경로 추종 (Autonomy_Runtime_Stack 선택 연동)
- 장애물 즉시 제동 (0.8 m 이내)
- `car_ready=True` → 자동차 핸드오프
- `at_home=True` + `destination=None` → AI 펫 핸드오프
- 최대 속도 1.5 m/s (부드러운 이동)

### 🚗 CarPlatform
- 자율주행 (SYD_DRIFT 선택 연동)
- 탑승자 안전 프리셋 (최대 50 km/h, 부드러운 제동 2.0 m/s²)
- 충격 감지 (> 2.0 g → 비상 정차)
- `arrived=True` → 휠체어 핸드오프

---

## 외부 연동 포인트

```python
# 1. Autonomy_Runtime_Stack (자율 휠체어 경로 추종)
from autonomy_runtime_stack import AutonomyOrchestrator
# WheelchairPlatform 에서 자동 감지·로드

# 2. SYD_DRIFT (자율 자동차 주행)
from syd_drift import SydDriftRunner
# CarPlatform 에서 자동 감지·로드

# 3. Claude API (LLM 케어 판단)
import anthropic
# CareAgent._llm_decide() 에서 확장 — 현재는 규칙 기반 폴백
```

---

## 빠른 시작

### 설치

```bash
git clone https://github.com/qquartsco-svg/AgedCare_Stack.git
cd AgedCare_Stack
pip install -e ".[dev]"
```

### 전체 여정 시뮬레이션 실행

```bash
python examples/run_care_journey.py
```

출력 예:
```
======================================================================
AgedCare_Stack — AI 케어 여정 시뮬레이션
======================================================================

────────────────────────────────────────────────────────────
🐾 1단계: 집 — AI 펫 케어
────────────────────────────────────────────────────────────
  [   0] 🐾 pet          | action=monitor              💬 "안녕하세요! 오늘 기분은 어떠세요?"
  [  10] 🐾 pet          | action=monitor
  [  40] 🐾 pet          | action=handoff_initiated    → wheelchair
...
```

### 테스트 실행

```bash
python -m pytest tests/test_aged_care.py -v
```

---

## 코드 사용 예

```python
from aged_care import (
    CareAgent, CareProfile, CareContext,
    VitalSigns, MedicalInfo, PlatformType,
)

# 케어 대상자 프로파일
profile = CareProfile(
    person_id="GNJz-001",
    name="홍길동",
    age=78,
    medical=MedicalInfo(
        conditions=("고혈압", "당뇨"),
        medications=("메트포르민", "아스피린"),
        mobility_level=0.6,
        fall_risk=0.4,
    ),
    home_location=(0.0, 0.0),
    emergency_contacts=("010-1234-5678",),
)

agent = CareAgent(profile)
ctx   = agent.start_session()
ctx.vitals = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.4)

# 케어 루프
for _ in range(100):
    ctx, decision = agent.tick(ctx)
    if decision.speak:
        print(f"AI 펫: {decision.speak}")
    if decision.alert:
        print(f"🚨 {decision.alert}")

# 외출 → 휠체어 전환
ctx.extra["go_out"] = True
ctx.destination = (500.0, 200.0)  # 병원
ctx, decision = agent.tick(ctx)
if agent._pending_token:
    agent.execute_handoff(ctx)

print(f"현재 플랫폼: {agent.current_platform.value}")  # wheelchair
```

---

## Claude API 확장 포인트

```python
# care_agent.py — _llm_decide() 메서드
import anthropic

def _llm_decide(self, ctx: CareContext) -> Optional[str]:
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=256,
        system=f"당신은 {ctx.profile.name}님의 AI 케어 보조입니다.",
        messages=[{"role": "user", "content": self._care_summary(ctx)}]
    )
    return message.content[0].text
```

현재는 규칙 기반 폴백으로 동작. `_llm_decide()` 구현 시 자동으로 LLM 판단이 적용된다.

---

## 연동 스택

| 스택 | 역할 | 연동 위치 |
|------|------|-----------|
| **SYD_DRIFT** | 자율주행 (도심 경로·CommandChain) | `CarPlatform` |
| **Autonomy_Runtime_Stack** | 자율 이동 (Stanley 컨트롤러·BehaviorFSM) | `WheelchairPlatform` |
| **Orca** | 해양 자율 시스템 (선박 케어 확장 가능) | 미래 `BoatPlatform` |
| **Claude API** | LLM 케어 판단 | `CareAgent._llm_decide()` |

---

## 버전

| 버전 | 내용 |
|------|------|
| **v0.1.0** | 최초 설계 — PetPlatform / WheelchairPlatform / CarPlatform / CareAgent / HandoffProtocol / CareMonitor |

---

## 라이선스

MIT
