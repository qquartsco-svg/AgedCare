# Changelog

## 0.2.2

- GitHub 저장소 정식 경로: https://github.com/qquartsco-svg/AgedCare (`AgedCare_Stack` 이름은 리다이렉트될 수 있음).
- 무결성: `scripts/regenerate_signature.py`, `scripts/verify_signature.py`, `LICENSE`, `BLOCKCHAIN_INFO`/`BLOCKCHAIN_INFO_EN` 보강, `SIGNATURE.sha256` 재생성 워크플로 정리.
- README / README_EN: 무결성 절차, 휠체어·4WD 연동 상세, 외부 엔진 표에 VPF·휠체어 FSM 행 추가.
- `pyproject.toml` Repository URL 등 메타 보강.

## 0.2.1

- **휠체어 기초 물리 연동:** `aged_care/bridges/wheelchair_physics.py` — `vehicle_platform_foundation` (`assess_platform`) + `wheelchair_transform_system` (`run_phase_tick` 착석 프로브).
- `WheelchairPlatform.tick` 가 매 틱 `ctx.extra["wheelchair_mobility_layer"]` 를 채우고, `suggested_max_speed_ms` 로 내비 속도 상한을 깎는다.
- `WheelchairConfig` 에 전동 휠체어 질량·휠베이스·모터·타이어 등 **기초 물리 파라미터** 추가.
- `tests/conftest.py` 로 `_staging` 동위 패키지 경로 주입; `tests/test_wheelchair_mobility_bridge.py` 추가.

## 0.2.0

- `CareAgent` 중심의 지속형 케어 에이전트 구조 정리.
- `PersonState`, `MissionState`, `SafetyState` 등 확장 스키마 추가.
- `OmegaMonitor` 6인수 케어 안전 지수 추가.
- `CareChain` SHA-256 연결 감사 체인 추가.
- `CognitiveAdapter`, `BatteryAdapter`, `SNNAdapter`, `EmergencyAdapter` 추가.
- `PetPlatform`, `WheelchairPlatform`, `CarPlatform` 바디별 동작 보강.
- 전체 여정 예제 `examples/run_care_journey.py` 추가.
- 테스트 확장: `137 passed`.

## 0.1.0

- 초기 케어 에이전트, 모니터, 핸드오프, 플랫폼 코어 추가.
