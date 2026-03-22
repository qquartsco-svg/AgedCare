# AgedCare_Stack

**하나의 AI 에이전트가 집에서 병원까지 — 플랫폼이 바뀌어도 케어는 끊기지 않는다.**

v0.2.0 | Python 3.9+ | stdlib only (external engines optional)

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
│  (Autonomy_Runtime_Stack, SYD_DRIFT)                            │
├─────────────────────────────────────────────────────────────────┤
│  Layer 3: Adapters (Edge AI — 모두 선택적)                       │
│  CognitiveAdapter  <- EmotionEngine + MemoryEngine + ActionEngine│
│  BatteryAdapter    <- Battery_Dynamics_Engine                   │
│  SNNAdapter        <- SNN_Backend_Engine                        │
│  EmergencyAdapter  <- 로컬 로그 / SMS / 119 확장 포인트          │
├─────────────────────────────────────────────────────────────────┤
│  Layer 4: Audit / Safety                                        │
│  CareChain — SHA-256 연결 감사 체인                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 수학적 기초

### 상태 벡터
```
s = [pos_x, pos_y, fatigue, pain, HR, SpO2, temp, valence, arousal, alert]
```

### 감정 공간 (Valence-Arousal)
```
E = sqrt(V^2 + A^2)      감정 강도 (magnitude)
theta = arctan(A / V)    감정 방향 (angle)
```

### 기억 감쇠
```
m(t) = m0 * exp(-(t - t0) / tau)
tau = 86400 s (기본 24시간)
```

### TD 강화학습 (BasalGanglia)
```
delta = r + gamma * V(s') - V(s)    TD 오차
pi(s,a) <- pi(s,a) + alpha * delta  Actor 업데이트
```

### Ω 케어 안전 지수 (6인수)
```
Omega_care = Omega_vitals * Omega_fatigue * Omega_env
           * Omega_medication * Omega_battery * Omega_cognitive

판정:
  SAFE      Omega >= 0.80
  CAUTION   Omega >= 0.50
  WARNING   Omega >= 0.25
  EMERGENCY Omega < 0.25
```

### 핸드오프 토큰 ID
```
tid = SHA-256(from_platform || to_platform || t_s)[:16]
```

### 감사 블록 해시
```
h_n = SHA-256(h_{n-1} || event_type || platform || t_s || data)
h_0 = "000...0" (제네시스)
```

### 미션 완료율
```
M = completed_stages / total_stages, M in [0, 1]
```

---

## 계층별 설명

### Layer 0 — Personal AI Core (`care_agent.py`)
- `CareAgent`: 에이전트 생명주기 관리 (세션 시작 → 틱 → 핸드오프)
- `PersonState`: 10차원 상태 벡터 (위치·생체·감정·인지)
- `MissionState`: 미션 단계 추적, 웨이포인트, 일정 관리
- `SafetyState`: 실시간 안전 판정 요약
- `_llm_decide()`: Claude API 연동 (폴백: 규칙 기반)

### Layer 1 — Care Orchestrator (`monitor/`, `handoff/`)
- `CareMonitor`: 4인수 Ω (하위 호환)
- `OmegaMonitor`: 6인수 Ω (배터리 + 인지 추가)
- `HandoffProtocol`: 플랫폼 전환 토큰 발행/확인/중단

### Layer 2 — Mobility Engines (`platforms/`)
- `PetPlatform`: 홈 AI 펫 (실내 케어, 낙상 감지)
- `WheelchairPlatform`: 자율 휠체어 (장애물 회피, Autonomy_Runtime_Stack)
- `CarPlatform`: 자율 자동차 (충격 감지, SYD_DRIFT)

### Layer 3 — Adapters (`adapters/`)
- `CognitiveAdapter`: EmotionEngine + MemoryEngine + ActionEngine 통합
- `BatteryAdapter`: SOC 모니터링, Ω_battery 계산
- `SNNAdapter`: 스파이킹 신경망 생체신호 패턴 분류
- `EmergencyAdapter`: 응급 감지, 보호자 통지, 쿨다운 관리

### Layer 4 — Audit (`audit/`)
- `CareChain`: SHA-256 연결 감사 블록체인
- 불변 이벤트 기록: 핸드오프, 긴급 상황, 투약, 대화

---

## 외부 엔진 연동 (모두 선택적)

| 엔진 | 경로 | 역할 | 폴백 |
|------|------|------|------|
| AmygdalaEngine | ENGINE_HUB/20_LIMBIC_LAYER/Amygdala_Engine | 감정 V-A 추론 | 규칙 기반 |
| HippocampusEngine | ENGINE_HUB/20_LIMBIC_LAYER/Hippocampus_Engine | 공간/에피소드 기억 | 목록 버퍼 |
| BasalGanglia_Engine | ENGINE_HUB/20_LIMBIC_LAYER/BasalGanglia_Engine | TD 강화학습 | 규칙 우선순위 |
| PrefrontalCortex_Engine | ENGINE_HUB/30_CORTEX_LAYER/PrefrontalCortex_Engine | 작업 기억, 억제 제어 | 생략 |
| Battery_Dynamics_Engine | _staging/Battery_Dynamics_Engine | SOC 모델링 | extra["battery_pct"] |
| SNN_Backend_Engine | _staging/SNN_Backend_Engine | LIF 뉴런 패턴 분류 | 임계값 규칙 |
| SYD_DRIFT | _staging/SYD_DRIFT | 자동차 궤적 | 단순 내비게이션 |
| Autonomy_Runtime_Stack | _staging/Autonomy_Runtime_Stack | 휠체어 자율주행 | 단순 경로 추적 |

---

## HandoffProtocol 허용 전환

```
PET        -> WHEELCHAIR  (외출)
WHEELCHAIR -> PET         (귀가)
WHEELCHAIR -> CAR         (장거리 이동)
CAR        -> WHEELCHAIR  (목적지 도착)
```

PET <-> CAR 직접 전환은 허용되지 않는다.

---

## 빠른 시작

```python
from aged_care import CareAgent, CareProfile, MedicalInfo

profile = CareProfile(
    person_id="001",
    name="홍길동",
    age=78,
    medical=MedicalInfo(medications=("아스피린",)),
    home_location=(37.5665, 126.9780),
    emergency_contacts=("010-0000-0000",),
)

agent = CareAgent(profile)
ctx = agent.start_session()

# 집에서 케어
for _ in range(10):
    ctx, decision = agent.tick(ctx)

# 외출 — 휠체어로 전환
ctx.destination = (37.5700, 126.9820)
ctx.extra["go_out"] = True
ctx, decision = agent.tick(ctx)
agent.execute_handoff(ctx)

print(agent.summary())
```

---

## 테스트 결과

```
pytest tests/test_aged_care.py -v
74 passed (§1-§7 original) + 25+ passed (§8 new layers)
```

- §1 데이터 스키마 & 파생 지표
- §2 CareMonitor — Ω 케어 안전 지수
- §3 HandoffProtocol — 토큰 발행/확인/중단
- §4 PetPlatform 틱 동작
- §5 WheelchairPlatform 틱 동작
- §6 CarPlatform 틱 동작
- §7 CareAgent 통합
- §8 새 레이어 (PersonState, CareChain, EmotionEngine, MemoryEngine, CognitiveAdapter, BatteryAdapter, SNNAdapter, EmergencyAdapter, OmegaMonitor)
