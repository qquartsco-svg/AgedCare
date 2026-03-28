> **한국어 (정본).** English: [README_EN.md](README_EN.md)

# AgedCare_Stack

> **하나의 개인 AI가 여러 몸체를 갈아타며 끊기지 않고 케어를 이어간다.**

v0.2.2 · Python 3.9+ · stdlib only (외부 엔진은 선택)

> **⚠️ 프로토타입 고지**
> 본 패키지는 개인 케어 운영 스택의 **소프트웨어 프로토타입**이다.
> 의료 진단·치료·응급 대응을 위한 인증 시스템이 아니며,
> 자율주행 완성 기기를 포함하지 않는다.
> 실제 케어 환경에서의 하드웨어 연동, 안전 인증, 임상 검증은 별도로 필요하다.

---

## 이 시스템이 무엇인가

### 핵심 개념

세 대의 로봇을 만드는 프로젝트가 아니다.

**하나의 개인 AI**가 있다.
그 AI는 사람 옆에 항상 붙어 있다.
하드웨어가 바뀌어도 AI는 끊기지 않는다.

```
AI = 영혼 (Soul)
펫 / 휠체어 / 자동차 = 바디 (Body)
```

집에서는 AI 펫의 몸에 들어가 주인 옆에서 케어한다.
외출할 때는 자율 휠체어의 몸으로 갈아타 이동을 돕는다.
장거리 이동 시에는 자율 자동차의 몸으로 갈아타 목적지까지 함께 간다.
어디서든 — **AI는 같은 AI다.** 기억도, 대화도, 건강 데이터도 그대로다.

---

## 여정 흐름 (전체 시나리오)

```
[집] 🐾 AI 펫
      │  개인 AI가 집 안에서 주인을 따라다니며 케어
      │  ↓ 외출 결정 → 휠체어 호출
      │
[이동] ♿ 자율 휠체어
      │  AI가 휠체어로 이동 — 현관까지 자율주행
      │  기억·건강 데이터 그대로 유지
      │  ↓ 자동차 도착 → 탑승
      │
[장거리] 🚗 자율 자동차
      │  AI가 자동차로 이동 — 목적지까지 자율주행
      │  이동 중에도 AI가 케어 (대화·생체 모니터링)
      │  ↓ 목적지 도착 → 하차
      │
[목적지] ♿ 자율 휠체어
      │  AI가 휠체어로 — 병원·시설 내 이동
      │  ↓ 용무 완료 → 귀가 결정
      │
[귀가] 🚗 자율 자동차
      │  AI가 자동차로 — 집까지 귀가 자율주행
      │  ↓ 집 근처 도착 → 하차
      │
[귀가] ♿ 자율 휠체어
      │  AI가 휠체어로 — 집 입구까지 이동
      │  ↓ 집 도착
      │
[집] 🐾 AI 펫
         AI가 다시 펫으로 — 귀가 후 케어 재개
         "잘 다녀오셨어요? 오늘 많이 피곤하셨겠어요."
```

**전 과정에서 AI는 하나다.**
플랫폼(하드웨어)이 바뀔 때마다 AI의 기억·감정·건강 상태·대화 맥락이
다음 몸체로 그대로 전달된다. 이것이 이 시스템의 핵심이다.

---

## 핵심 설계 원칙

| 원칙 | 설명 |
|------|------|
| **지속성 (Persistence)** | AI는 플랫폼이 바뀌어도 기억·대화·건강 추적을 이어간다 |
| **바디 핸드오프 (Body Handoff)** | SHA-256 토큰으로 AI 상태를 다음 플랫폼에 안전하게 전달 |
| **Ω 케어 안전 지수** | 생체·피로·환경·투약·배터리·감정 6인수 복합 안전 판정 |
| **페일세이프** | 핸드오프 실패 시 원래 플랫폼 자동 유지 |
| **Edge AI** | 코어는 외부 의존 없음 — 모든 외부 엔진은 선택적 |

---

## 바디별 역할

### 🐾 AI 펫 (집)
- 집 안에서 주인 옆을 따라다니며 케어
- 생체 신호 모니터링 (심박·체온·산소포화도)
- 낙상 감지 → 즉시 보호자 연락
- 투약·식사 알림
- 대화 (기분 확인, 일상 대화)
- 외출 감지 → 휠체어 호출 및 AI 상태 전달

### ♿ 자율 휠체어 (실내·근거리 이동)
- 집 → 자동차 승차 위치까지 자율주행
- 목적지 내부 (병원·시설) 자율 이동
- 장애물 즉시 정지 (0.8m 이내)
- 최대 속도 1.5 m/s (노인 안전 속도)
- 자동차 도착 감지 → 탑승 안내 및 AI 상태 전달

**기초 물리·휠체어 FSM (v0.2.1+):** AgedCare의 이동 바디가 휠체어일 때, 케어 맥락 아래에 **질량·축하중·접지/동력 예산**을 둔다. `WheelchairPlatform` 틱마다 `aged_care/bridges/wheelchair_physics.py` 가 (PYTHONPATH에 있을 때) `vehicle_platform_foundation` 의 `assess_platform` 과 `wheelchair_transform_system` 의 착석 FSM 프로브를 호출하고, 결과를 `CareContext.extra["wheelchair_mobility_layer"]` 에 넣으며 **제안 상한 속도**로 내비 속도를 깎는다. 스택이 없으면 플래그만 False 로 두고 기존 폴백 동작.

### 🚗 자율 자동차 (장거리 이동)
- 목적지까지 자율주행
- 노인 보호 속도 프리셋 (최대 50 km/h, 부드러운 제동)
- 충격 감지 (2.0 g 초과) → 비상 정차
- 이동 중 AI 케어 지속 (대화·생체 모니터링)
- 도착 감지 → 휠체어 호출 및 AI 상태 전달

---

## 시스템 아키텍처 (5계층)

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 0: Personal AI Core                                      │
│  CareAgent — 기억·감정·판단·Claude API                          │
│  PersonState s⃗ | MissionState M | SafetyState Ω               │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1: Care Orchestrator                                     │
│  HandoffProtocol — 플랫폼 전환 토큰                              │
│  OmegaMonitor — Ω_care = Ω_v × Ω_f × Ω_e × Ω_m × Ω_b × Ω_c  │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2: Mobility Engines                                      │
│  PetPlatform | WheelchairPlatform | CarPlatform                 │
│  + bridges/wheelchair_physics → VPF + Wheelchair_Transform       │
│  (Autonomy_Runtime_Stack, SYD_DRIFT — 선택)                      │
├─────────────────────────────────────────────────────────────────┤
│  Layer 3: Adapters (Edge AI — 모두 선택적)                       │
│  CognitiveAdapter  ← EmotionEngine + MemoryEngine + ActionEngine│
│  BatteryAdapter    ← Battery_Dynamics_Engine                   │
│  SNNAdapter        ← SNN_Backend_Engine                        │
│  EmergencyAdapter  ← 로컬 로그 / SMS / 119 확장 포인트          │
├─────────────────────────────────────────────────────────────────┤
│  Layer 4: Audit / Safety                                        │
│  CareChain — SHA-256 연결 감사 체인                              │
└─────────────────────────────────────────────────────────────────┘
```

**사용자 관점:**

```
사용자
  ↕ 대화·케어
개인 AI 코어 (CareAgent)
  ├─ 건강/안전 레이어 (CareMonitor, OmegaMonitor)
  ├─ 기억/감정 레이어 (Hippocampus, Amygdala, BasalGanglia)
  ├─ 일정/미션 레이어 (MissionState, ScheduleEvent)
  └─ 바디 핸드오프 레이어 (HandoffProtocol)
        ├─ 🐾 AI 펫 바디      (PetPlatform)
        ├─ ♿ 휠체어 바디     (WheelchairPlatform)
        └─ 🚗 자동차 바디     (CarPlatform)
```

---

## 수학적 기초

### 개인 AI 상태 벡터
```
s⃗ = [pos_x, pos_y, fatigue, pain, HR, SpO2, temp, valence, arousal, alert]
     (위치 2차원) (신체 2) (생체 3) (감정 2차원) (인지 1)
```

### 감정 공간 (Valence-Arousal)
```
E = sqrt(V² + A²)      감정 강도 (magnitude)
θ = arctan(A / V)      감정 방향 (angle)

기쁨: V↑ A↑   슬픔: V↓ A↓
불안: V↓ A↑   평온: V↑ A↓
```

### 기억 감쇠 (Hippocampus)
```
m(t) = m₀ × exp(-(t - t₀) / τ)
τ = 86400 s  (기본 24시간)
```

### 행동 학습 (BasalGanglia — TD 강화학습)
```
δ = r + γ·V(s') - V(s)          TD 오차 (도파민 신호)
π(s,a) ← π(s,a) + α·δ           Actor 업데이트
```

### Ω 케어 안전 지수 (6인수)
```
Ω_care = Ω_vitals × Ω_fatigue × Ω_env
        × Ω_medication × Ω_battery × Ω_cognitive

판정:
  SAFE      Ω ≥ 0.80   정상 케어
  CAUTION   Ω ≥ 0.50   주의 (이벤트 발생)
  WARNING   Ω ≥ 0.25   경고 (보호자 알림)
  EMERGENCY Ω < 0.25   긴급 (119 + 보호자 즉시 연락)
```

### 바디 핸드오프 토큰
```
tid = SHA-256(from_platform ‖ to_platform ‖ t_s)[:16]
```

> **설계 범위:** 이 토큰은 플랫폼 전환의 **식별(identification)·추적(trace) 목적**의
> 감사 토큰이다. 서명·재생 공격 방지·세션 키를 포함한 전체 보안 핸드오프 구현은
> 실제 배포 단계에서 별도로 설계해야 한다.

### 감사 블록 체인
```
h_n = SHA-256(h_{n-1} ‖ event_type ‖ platform ‖ t_s ‖ data)
h_0 = "000...0"  (제네시스 블록)
```

### 미션 완료율
```
M = completed_stages / total_stages,  M ∈ [0, 1]
```

---

## 허용 바디 전환 경로

```
🐾 PET  ←→  ♿ WHEELCHAIR  ←→  🚗 CAR

PET  →  WHEELCHAIR   외출 시 휠체어 호출
WHEELCHAIR  →  PET   귀가 시 펫 복귀
WHEELCHAIR  →  CAR   장거리 이동 시 자동차 탑승
CAR  →  WHEELCHAIR   목적지 도착 시 하차
```

**PET → CAR 직접 전환 금지.**
반드시 WHEELCHAIR를 경유해야 한다. (안전 설계)

---

## 계층별 설명

### Layer 0 — Personal AI Core (`care_agent.py`)
- `CareAgent`: 에이전트 생명주기 전체 관리 (세션 시작 → 틱 → 핸드오프)
- `PersonState`: 10차원 실시간 상태 벡터
- `MissionState`: 미션 단계 추적, 웨이포인트, 일정 관리
- `SafetyState`: 실시간 안전 판정 요약
- `_llm_decide()`: Claude API 케어 판단 (폴백: 규칙 기반)

### Layer 1 — Care Orchestrator (`monitor/`, `handoff/`)
- `CareMonitor`: 4인수 Ω — 하위 호환
- `OmegaMonitor`: 6인수 Ω — 배터리·인지 인수 추가
- `HandoffProtocol`: SHA-256 토큰 기반 플랫폼 전환 발행/확인/중단

### Layer 2 — Mobility Engines (`platforms/`)
- `PetPlatform`: 홈 AI 펫 (실내 케어, 낙상 감지, 투약 알림)
- `WheelchairPlatform`: 자율 휠체어 (장애물 회피, Autonomy_Runtime_Stack 연동)
- `CarPlatform`: 자율 자동차 (충격 감지, SYD_DRIFT 연동)

### Layer 3 — Adapters (`adapters/`) — 모두 선택적
- `CognitiveAdapter`: EmotionEngine + MemoryEngine + ActionEngine 통합
- `BatteryAdapter`: SOC 모니터링, 5단계 Ω_battery 계산
- `SNNAdapter`: 스파이킹 신경망 생체신호 패턴 분류 (normal/stress/crisis/recovery)
- `EmergencyAdapter`: 낙상·생체위기·충격 감지, 보호자 통지, 쿨다운 관리
- `NexusAdapter`: 현장 케어 상태 → executive brief / Nexus signal / Pharaoh report

### Layer 4 — Audit (`audit/`)
- `CareChain`: SHA-256 연결 감사 블록체인
- 불변 이벤트 기록: 바디 전환, 긴급 상황, 투약, 대화

---

## 외부 엔진 연동 (모두 선택적)

모든 외부 엔진은 `try/except ImportError` 로 감싸져 있다.
미설치 시 내장 규칙 폴백이 자동 작동 — **코어는 항상 실행된다.**

| 엔진 | 역할 | 폴백 |
|------|------|------|
| AmygdalaEngine | 감정 Valence-Arousal 추론 | 생체신호 기반 규칙 |
| HippocampusEngine | 공간·에피소드 기억 | 목록 버퍼 + 지수 감쇠 |
| BasalGanglia_Engine | TD 강화학습 행동 선택 | 규칙 우선순위 |
| PrefrontalCortex_Engine | 작업 기억, 억제 제어 | 생략 |
| Battery_Dynamics_Engine | 배터리 팩 SOC 모델링 | `extra["battery_pct"]` |
| SNN_Backend_Engine | LIF 스파이킹 뉴런 패턴 분류 | 임계값 규칙 |
| SYD_DRIFT | 자동차 자율주행 궤적 | 단순 내비게이션 |
| Autonomy_Runtime_Stack | 휠체어 자율주행 | 단순 경로 추적 |
| Claude API (anthropic) | LLM 케어 판단 | 규칙 기반 |
| **vehicle_platform_foundation** (공개 미러 [**4WD**](https://github.com/qquartsco-svg/4WD)) | 휠체어 **기초 물리** (질량·축하중·접지·동력) | 브리지 미로드 시 스킵 |
| **wheelchair_transform_system** (00_BRAIN 동위 스테이징) | 휠체어 **FSM·HAL** (착석 프로브) | 브리지 미로드 시 스킵 |

---

## 무결성 · 블록체인 스타일 서명

배포·감사용으로 파일 내용 해시 목록을 유지한다 (암호화폐 체인 아님).

| 파일 | 설명 |
|------|------|
| `SIGNATURE.sha256` | 추적 대상 파일별 SHA-256 |
| `BLOCKCHAIN_INFO.md` / `BLOCKCHAIN_INFO_EN.md` | 정책·검증·릴리스 블록 |
| `PHAM_BLOCKCHAIN_LOG.md` | 릴리스 변경 요지 연속 기록 |
| `scripts/regenerate_signature.py` | 목록 재생성 |
| `scripts/verify_signature.py` | 현재 트리와 목록 비교 |

```bash
python scripts/regenerate_signature.py
python scripts/verify_signature.py
python -m pytest tests/ -q
```

성공 시 `verify_signature: OK (N files)` 가 출력된다.

---

## 휠체어 기초 물리 연동 (상세)

**AgedCare의 이동 바디가 휠체어일 때**, 케어 AI 아래에 **실제 지상 플랫폼 물리층**을 둔다.

1. **의미**  
   - 케어 = 의도·말·Ω·핸드오프 (상위).  
   - 휠체어 = 저속 자율·기립·전이가 일어나는 **몸**.  
   - **4WD/VPF** = 그 몸을 2축·4접촉으로 읽는 **질량·접지·동력 예산** (하위).

2. **코드 경로**  
   - `aged_care/bridges/wheelchair_physics.py` → `assess_platform` + `run_phase_tick(SEATED_IDLE, …)`.  
   - `WheelchairPlatform.tick` 이 매 틱 `ctx.extra["wheelchair_mobility_layer"]` 를 채우고 `suggested_max_speed_ms` 로 속도 상한을 제한한다.

3. **실행 환경**  
   - 단독 클론만 한 경우: 패키지가 없으면 `physics_available` / `fsm_available` 만 `False` — **코어 케어는 그대로 동작**.  
   - 00_BRAIN 모노레포: `tests/conftest.py` 가 `_staging/Vehicle_Platform_Foundation` · `_staging/Wheelchair_Transform_System` 을 `PYTHONPATH`에 넣어 연동 테스트(170+ tests)가 통과한다.

4. **확장용 `ctx.extra` 키 (선택)**  
   - `slope_grade_deg`, `wheel_velocity_m_s`, `brake_engaged`, `estop_active` 등 — 향후 센서·경사와 정합할 때 사용.

---

## 빠른 시작

```bash
git clone https://github.com/qquartsco-svg/AgedCare_Stack.git
cd AgedCare_Stack
pip install -e ".[dev]"
```

```python
from aged_care import CareAgent, CareProfile, MedicalInfo, VitalSigns

# 케어 대상자 설정
profile = CareProfile(
    person_id="001",
    name="홍길동",
    age=78,
    medical=MedicalInfo(
        conditions=("고혈압", "당뇨"),
        medications=("아스피린", "메트포르민"),
        fall_risk=0.4,
    ),
    home_location=(37.5665, 126.9780),
    emergency_contacts=("010-0000-0000",),
)

agent = CareAgent(profile)
ctx   = agent.start_session()
ctx.vitals = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.4)

# 집에서 AI 펫 케어
for _ in range(50):
    ctx, decision = agent.tick(ctx)
    if decision.speak:
        print(f"🐾 {decision.speak}")

# 외출 — 자율 휠체어로 바디 전환
ctx.destination = (37.5700, 126.9820)   # 병원
ctx.extra["go_out"] = True
ctx, decision = agent.tick(ctx)
agent.execute_handoff(ctx)              # PET → WHEELCHAIR
# AI가 휠체어의 몸으로 이동을 이어간다

print(agent.summary())
```

### Executive Reporting (Nexus / Pharaoh)

고위 사용자나 의사결정권자 케이스에서는 현장 케어 상태를
상위 orchestration 계층에 업무 보고 형태로 올릴 수 있다.

```python
from aged_care import (
    build_executive_brief,
    executive_brief_to_nexus_signal,
    executive_brief_to_pharaoh_report,
)

brief = build_executive_brief(ctx=ctx, safety=ctx.safety_state, decision=decision)
nexus_signal = executive_brief_to_nexus_signal(brief)
pharaoh_report = executive_brief_to_pharaoh_report(brief)
```

이 흐름은 다음 의미를 가진다.

- `AgedCare`: 사람 곁 현장 케어
- `ExecutiveBrief`: 현장 상태의 요약 계약
- `Nexus`: 상위 orchestration / 보고 집계
- `Athena`: 공공 판단과 상황 해석
- `Pharaoh`: 최종 칙령 추천

현재 구현에서 실제로 추가된 핵심 함수는 다음과 같다.

- `build_executive_brief()`
- `executive_brief_to_nexus_signal()`
- `executive_brief_to_pharaoh_report()`
- `executive_brief_lines()`
- `merge_briefs()`

즉 이 스택은 이제 단순 현장 케어를 넘어서,
**고위 사용자/의사결정권자의 건강·피로·인지부하·긴급도를
상위 운영 계층에 업무 보고 형태로 올리는 구조**까지 갖는다.

관련 파일:

- `aged_care/adapters/nexus_adapter.py`
- `examples/run_executive_reporting.py`

예제 실행:

```bash
python examples/run_executive_reporting.py
```

### 전체 여정 시뮬레이션 (7단계)

```bash
python examples/run_care_journey.py
```

```
======================================================================
AgedCare_Stack — AI 케어 여정 시뮬레이션
======================================================================

🐾 1단계: 집 — AI 펫 케어
  [  0] 🐾 pet       | action=follow      💬 "안녕하세요! 오늘 기분은 어떠세요?"
  [ 40] 🐾 pet       | action=handoff_initiated  → wheelchair

♿ 2단계: 휠체어 — 집 → 자동차
  [ 60] ♿ wheelchair | action=navigate
  [110] ♿ wheelchair | action=handoff_initiated  → car

🚗 3단계: 자동차 — 자율주행 (병원까지)
  [140] 🚗 car       | action=navigate    💬 "불편한 건 없으세요?"
  [210] 🚗 car       | action=handoff_initiated  → wheelchair

... (4~7단계: 목적지 이동 → 귀가 → 펫 복귀)
```

---

## 테스트

```bash
python -m pytest tests/ -q
python scripts/verify_signature.py
```

> **테스트 범위:** 아래 **170개 전후**는 소프트웨어 **논리·통합 테스트**다.
> 데이터 계약 정합성, 상태 기계 전이, Ω 수식, 핸드오프 프로토콜을 검증한다.
> 실제 하드웨어 연동·임상 케어·실도로 자율주행의 현실 검증은 포함하지 않는다.

| 섹션 | 내용 | 결과 |
|------|------|------|
| §1 | 데이터 스키마 & 파생 지표 | ✅ |
| §2 | CareMonitor — Ω 케어 안전 지수 | ✅ |
| §3 | HandoffProtocol — 토큰 발행/확인/중단 | ✅ |
| §4 | PetPlatform 틱 동작 | ✅ |
| §5 | WheelchairPlatform 틱 동작 | ✅ |
| §6 | CarPlatform 틱 동작 | ✅ |
| §7 | CareAgent 통합 | ✅ |
| §8 | 새 레이어 (PersonState, CareChain, Cognitive, Battery, SNN, Emergency, OmegaMonitor) | ✅ |
| §9 | Executive reporting / Nexus adapter / governance signal | ✅ |
| §10 | 휠체어·VPF·FSM 브리지 (`test_wheelchair_mobility_bridge`) | ✅ |
| **합계** | | **170 passed (모노레포 동위 스택 경로 있을 때)** |

---

## 폴더 구조

```
AgedCare_Stack/
├── aged_care/
│   ├── care_agent.py          Layer 0 — 개인 AI 코어
│   ├── monitor.py             Layer 1 — 4인수 Ω (하위 호환)
│   ├── contracts/
│   │   └── schemas.py         데이터 계약 (PersonState, VitalSigns 등)
│   ├── handoff/
│   │   └── protocol.py        Layer 1 — SHA-256 핸드오프 토큰
│   ├── platforms/
│   │   ├── pet.py             Layer 2 — 🐾 AI 펫 바디
│   │   ├── wheelchair.py      Layer 2 — ♿ 자율 휠체어 바디
│   │   └── car.py             Layer 2 — 🚗 자율 자동차 바디
│   ├── monitor/
│   │   └── omega.py           Layer 1 — 6인수 Ω 확장 모니터
│   ├── cognitive/
│   │   ├── emotion_engine.py  Layer 3 — 감정 추론 (Amygdala 연동)
│   │   ├── memory_engine.py   Layer 3 — 기억 관리 (Hippocampus 연동)
│   │   └── action_engine.py   Layer 3 — 행동 선택 (BasalGanglia 연동)
│   ├── adapters/
│   │   ├── cognitive_adapter.py  Layer 3 — 인지 엔진 통합
│   │   ├── battery_adapter.py    Layer 3 — 배터리 모니터링
│   │   ├── snn_adapter.py        Layer 3 — 스파이킹 신경망
│   │   ├── emergency_adapter.py  Layer 3 — 긴급 연락
│   │   └── nexus_adapter.py      Layer 3 — executive reporting / Nexus bridge
│   ├── bridges/
│   │   └── wheelchair_physics.py  휠체어 ↔ VPF·휠체어 FSM 선택 연동
│   └── audit/
│       └── care_chain.py      Layer 4 — SHA-256 감사 체인
├── scripts/
│   ├── regenerate_signature.py  SIGNATURE.sha256 재생성
│   └── verify_signature.py      무결성 검증
├── LICENSE
├── SIGNATURE.sha256
├── BLOCKCHAIN_INFO.md / BLOCKCHAIN_INFO_EN.md
├── PHAM_BLOCKCHAIN_LOG.md
├── examples/
│   ├── run_care_journey.py        7단계 전체 여정 시뮬레이션
│   └── run_executive_reporting.py executive brief / Nexus / Pharaoh 예제
└── tests/
    ├── conftest.py            (선택) 동위 스택 PYTHONPATH
    ├── test_aged_care.py      §1~§9 단위·통합 테스트
    ├── test_nexus_adapter.py  executive reporting 회귀
    └── test_wheelchair_mobility_bridge.py  휠체어·물리·FSM 브리지
```

---

## 라이선스

[LICENSE](LICENSE) — MIT (quarts co. / GNJz)
