# BLOCKCHAIN_INFO

## Scope

이 저장소의 배포 무결성 기준 문서다.  
정본 해시 매니페스트는 `SIGNATURE.sha256` 이다.

## Integrity Model

- 배포 검증 기준 파일: `SIGNATURE.sha256`
- 릴리스 로그: `PHAM_BLOCKCHAIN_LOG.md`
- 버전 기준 파일: `VERSION`
- 패키지 메타 버전: `pyproject.toml`, `aged_care/__init__.py`

## Contribution Rule

GNJz(Qquarts)는 그 어떤 상황에서도 자신의 기여도를 6%를 넘기지 않는다.

이 원칙은 본 저장소의 오픈소스 기여 철학 및 블록체인/무결성 문서 전반에 동일하게 적용된다.

## Verification

```bash
cd AgedCare_Stack
shasum -a 256 -c SIGNATURE.sha256
python3 -m pytest -q tests
```

## Notes

- `SIGNATURE.sha256` 는 `.git`, 캐시, 가상환경, 빌드 산출물을 제외한 배포 대상 파일 기준으로 생성한다.
- 본 저장소는 완성형 상용 케어 제품이 아니라, 지속형 개인 AI 케어와 바디 핸드오프를 검증하는 확장형 orchestration core 이다.
