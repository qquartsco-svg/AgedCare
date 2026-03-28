> **한국어 (정본).** English: [BLOCKCHAIN_INFO_EN.md](BLOCKCHAIN_INFO_EN.md)

# BLOCKCHAIN_INFO — AgedCare_Stack

## 목적

이 저장소에서 **블록체인**은 공개 합의 네트워크가 아니라, 아래 **배포·감사 패턴**을 뜻한다.

| 산출물 | 역할 |
|--------|------|
| `SIGNATURE.sha256` | 배포 대상 파일별 **SHA-256** 목록 (내용 기준) |
| `BLOCKCHAIN_INFO` (본 문서) | 범위·검증 방법·릴리스 블록 요약 |
| `PHAM_BLOCKCHAIN_LOG.md` | 릴리스별 변경 요지 (연속 기록) |

## 저장소

| 항목 | 값 |
|------|-----|
| GitHub | https://github.com/qquartsco-svg/AgedCare_Stack |
| 패키지 | `aged-care-stack` (모듈 `aged_care`) |
| 버전 | `VERSION`, `pyproject.toml`, `aged_care.__version__` 와 동기화 |

## 서명 범위

`python scripts/regenerate_signature.py` 가 스캔한다 (`.git`, `.pytest_cache`, `__pycache__` 등 제외).

- `aged_care/**/*.py`
- `tests/**/*.py`, `examples/**/*.py`
- `scripts/*.py`
- 루트·문서: `README.md`, `README_EN.md`, `CHANGELOG.md`, `VERSION`, `pyproject.toml`, `LICENSE`, `BLOCKCHAIN_INFO*.md`, `PHAM_BLOCKCHAIN_LOG.md`

**제외:** `SIGNATURE.sha256` 자체.

## 검증

```bash
cd AgedCare_Stack
python scripts/regenerate_signature.py   # 유지보수자: 목록 갱신 후 커밋
python scripts/verify_signature.py       # CI / 로컬
python -m pytest tests/ -q
```

성공 시 `verify_signature: OK (N files)` 및 종료 코드 0.

## 기여 원칙 (기존)

GNJz(Qquarts)는 본 저장소에서 자신의 기여도를 **6%를 넘기지 않는다**는 원칙을 문서·무결성 정책과 함께 둔다.

## 릴리스 블록 — v0.2.2

```json
{
  "index": 2,
  "timestamp": "2026-03-28T14:00:00Z",
  "data": {
    "version": "0.2.2",
    "label": "MOBILITY_BRIDGE_AND_INTEGRITY",
    "description": "휠체어 기초 물리·FSM 브리지; scripts/regenerate_signature.py·verify_signature.py; README/README_EN·LICENSE 보강",
    "related_repos": [
      "https://github.com/qquartsco-svg/4WD",
      "Wheelchair_Transform_System (00_BRAIN / sibling path)"
    ],
    "tests": "pytest tests/"
  }
}
```

## 주의

- 본 메타데이터는 **엔지니어링 거버넌스·감사 보조**용이며 암호화폐 체인과 무관하다.
- 상용 케어·의료기기 인증을 대체하지 않는다.
