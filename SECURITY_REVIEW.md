# 시큐어 코딩 점검 리포트

- 대상: `studyforest_AI` (FastAPI + OpenAI 연동 AI 서버)
- 점검일: 2026-07-13
- 범위: `app/` 전체(564 LOC), `tests/`, `requirements.txt`
- 방식: 정적 분석(SAST) 자동 스캔 + 수동 코드 리뷰

## 1. 왜 SpotBugs가 아닌가

SpotBugs는 JVM 바이트코드(Java/Kotlin)를 대상으로 하는 도구라 이 저장소(Python)에는 적용할 수 없습니다. 대신 역할이 겹치는 Python 도구로 대체했습니다.

| SpotBugs 계열 도구 | 이 프로젝트에서 사용한 대체 도구 | 비고 |
|---|---|---|
| SpotBugs 코어 (버그 패턴) | **Ruff** (`E`, `F`, `I`, `B`, `UP`, `S` 규칙, `pyproject.toml`에 이미 설정됨) | `B`(bugbear)가 버그 패턴 탐지 역할 |
| FindSecBugs (보안 플러그인) | **Bandit** (`bandit -r app`) | 하드코딩 시크릿, `eval`/`exec`, 취약 crypto, SQL 조합 등 탐지 |
| OWASP Dependency-Check | **pip-audit** (`pip-audit -r requirements.txt`) | 의존성 CVE(OSV DB) 스캔 |

세 도구 모두 `requirements.txt`에 이미 개발 의존성으로 포함되어 있어 추가 설치 없이 바로 실행했습니다.

## 2. 실행 커맨드 및 원본 결과 요약

```bash
bandit -r app -f json
ruff check .                     # pyproject.toml 설정(S101 제외) 그대로 적용
pip-audit -r requirements.txt -f json
```

| 도구 | 탐지 건수 | 심각도 |
|---|---|---|
| Bandit | **0건** | - |
| Ruff `S` (flake8-bandit, 보안) | **0건** (S101은 프로젝트 설정에서 제외) | - |
| Ruff `B`/`E`/`I`/`UP` (버그·스타일) | 9건 | 전부 스타일/버그 카테고리, 보안 무관 |
| pip-audit | 1건 | `pytest` — Low (dev 의존성) |

자동 스캐너 기준으로는 "고전적인" 보안 안티패턴(`eval`/`exec`, 하드코딩 시크릿, SQL 문자열 조합, 약한 해시/암호, 안전하지 않은 역직렬화 등)은 발견되지 않았습니다. 이는 실제로 코드가 이미 상당히 방어적으로 작성돼 있기 때문입니다(로그 마스킹, 전역 예외 처리, 보안 헤더, Rate limit 등). 다만 이런 룰 기반 스캐너는 **비즈니스 로직/설계 수준의 결함**은 잡지 못하므로, 아래 3장은 수동 리뷰로 보강한 내용입니다.

## 3. 상세 findings — 어디를, 왜 바꿔야 하는가

### 3.1 실탐(True Positive) — 조치 권장

| # | 위치 | 심각도 | 내용 | 왜 실탐인가 | 권장 조치 |
|---|---|---|---|---|---|
| TP-1 | [app/services/openai_service.py:197-215](app/services/openai_service.py#L197-L215) `explain_question()` | **Medium** | `exam_chat`(L111)·`motivate`(L125)는 `contains_prompt_injection()` 검사를 거치는데, `explain_question`은 `questionContent`/`passage`/`options[].optionContent`를 검사 없이 그대로 프롬프트에 삽입 | 자동 스캐너는 "이 함수가 형제 함수와 다른 보안 검사를 누락했다"는 **일관성 결함**을 볼 수 없음. 사용자가 시스템 프롬프트 유출/지침 변경을 시도하는 문구를 문제 자료나 보기에 심으면 이 경로만 우회 가능 | `explain_question` 시작부에 `questionContent`, `passage`, `options[].optionContent`에 대해 동일하게 `contains_prompt_injection` 체크 추가 |
| TP-2 | [app/routers/chat.py](app/routers/chat.py), [app/routers/questions.py](app/routers/questions.py) 전체 | **Medium~High** (배포 구조에 따라 가변) | 모든 엔드포인트(`/api/v1/chat/*`, `/api/v1/questions/*`)에 서비스 간 인증(API 키/서명 헤더 등)이 없음. 커밋 로그(`spring api 연동 진행`)로 보아 Spring 백엔드가 유일한 호출자여야 하는 구조로 보이는데, 이를 강제하는 서버 측 검증이 없음 | CORS(`allow_origins`)와 `TrustedHostMiddleware`는 **브라우저/Host 헤더 기준**의 방어이지 서버 간 호출을 막는 인증이 아님. 이 서버의 URL을 알고 IP 기반 rate limit(60초 30회) 안에서 요청하면 누구나 유료 OpenAI 엔드포인트를 직접 호출 가능 | Spring↔AI서버 사이에 공유 시크릿 헤더(`X-Internal-Token` 등) 검증 미들웨어 추가, 또는 네트워크 레벨(VPC/사설망, mTLS)로 직접 접근 차단 |
| TP-3 | [requirements.txt:9](requirements.txt#L9) `pytest>=8.3.0,<9.0.0` | **Low** | pip-audit: `PYSEC-2026-1845` / `CVE-2025-71176` — pytest 9.0.2 이하는 UNIX에서 `/tmp/pytest-of-{user}` 패턴 디렉터리를 예측 가능하게 사용해 로컬 DoS·권한 상승 가능 | 실제 CVE이며 pip-audit이 정확히 탐지함. 다만 **개발/테스트 전용 의존성**(운영 배포물에 포함 안 됨)이고, 공유 다중 사용자 UNIX 호스트에서 CI를 돌리지 않는 한 악용 난이도가 낮아 실무 영향은 제한적 | `requirements.txt`에서 `pytest>=9.0.3,<10.0.0`으로 상향 |

### 3.2 오탐(False Positive) — 조치 불필요

| # | 위치 | 도구 | 내용 | 왜 오탐인가 |
|---|---|---|---|---|
| FP-1 | [app/routers/chat.py:10,17,25](app/routers/chat.py#L10), [app/routers/questions.py:15,22,30](app/routers/questions.py#L15) | Ruff `B008` (`function-call-in-default-argument`) 6건 | "기본 인자에서 함수 호출(`Depends(...)`) 금지" 규칙 위반으로 표시 | `Depends()`를 파라미터 기본값에 쓰는 것은 **FastAPI 의존성 주입의 정식 사용법** 그 자체임. bugbear 규칙은 일반 Python 함수의 mutable-default 버그 패턴(`def f(x=[])`)을 잡기 위한 것이라 FastAPI 컨텍스트를 모름. FastAPI 공식 문서도 이 패턴을 권장 |
| FP-2 | 프로젝트 전체 | Bandit / Ruff `S` | 탐지 0건 | 코드에 `eval`/`exec`/`pickle`/문자열 SQL 조합/하드코딩 시크릿이 없고, `SecretStr`로 API 키를 감싸 로그 노출을 막음. 스캐너가 "못 찾은" 것이 아니라 실제로 해당 안티패턴이 **존재하지 않아 참음성(true negative)** |

### 3.3 방어 설계가 이미 잘 되어 있는 부분 (변경 불필요, 참고용)

- [app/core/logging.py](app/core/logging.py): 정규식 기반 `RedactingFormatter`로 `sk-...`, `api_key=`, `Authorization: Bearer ...` 로그 마스킹
- [app/core/exceptions.py](app/core/exceptions.py): 전역 `Exception` 핸들러가 스택트레이스/내부 오류를 노출하지 않고 고정 메시지만 반환 (정보 노출 방지)
- [app/core/middleware.py](app/core/middleware.py): 보안 헤더(`X-Content-Type-Options`, `X-Frame-Options`, `Cache-Control: no-store`), 요청 바디 크기 제한, IP 기반 rate limit
- [app/main.py](app/main.py): `settings.is_production`일 때 `/docs` 비활성화, CORS `allow_credentials=False` + 메서드/헤더 화이트리스트, `TrustedHostMiddleware` 적용
- [app/models/schemas.py](app/models/schemas.py): 모든 요청 모델에 `extra='forbid'` + 길이 제한, LLM 응답도 Pydantic으로 스키마 검증 후 사용 (신뢰하지 않는 JSON 그대로 반환 안 함)
- [app/services/safety.py](app/services/safety.py): NFKC 정규화, 제어문자 제거, 길이 제한을 입력 정규화 단계에서 일괄 적용

### 3.4 참고 — 자동화 도구로는 판단 불가한 배포 토폴로지 이슈

[app/core/middleware.py:48](app/core/middleware.py#L48) `SimpleRateLimitMiddleware`는 `request.client.host`를 직접 사용합니다. 이 서버가 리버스 프록시/로드밸런서(예: Spring이 프록시 역할) 뒤에 있고 uvicorn에 `--proxy-headers`가 설정되지 않은 상태로 배포된다면, 모든 요청이 프록시의 IP 하나로 집계되어 실질적으로 전체 사용자가 하나의 rate limit 버킷을 공유하게 됩니다(한 명의 과다 요청이 전체를 차단). 실제 배포 구조(직접 노출 vs 프록시 경유)를 알아야 실탐 여부를 확정할 수 있어 별도로 표기했습니다.

## 4. 우선순위 요약

1. **TP-2 (서비스 간 인증 부재)** — 이 서버가 인터넷에 직접 노출된다면 가장 먼저 조치. 비용이 드는 OpenAI 호출을 외부인이 무단으로 소비할 수 있음
2. **TP-1 (explain_question 프롬프트 인젝션 검사 누락)** — 다른 엔드포인트와 동일한 로직 적용, 수정 범위 작음
3. **TP-3 (pytest 버전)** — `requirements.txt` 한 줄 수정
4. **FP-1 (B008)** — 조치 불필요, 필요하면 `# noqa: B008` 또는 라우터 파일에 한해 `B008` ignore 설정 추가해 리포트 노이즈만 제거

## 5. 결론

자동 스캐너(Bandit/Ruff-S/pip-audit) 기준 심각한 실탐은 없으며, 이는 코드베이스가 이미 방어적으로 설계되어 있음을 의미합니다(3.3절). 수동 리뷰에서 발견한 이슈는 패턴 매칭으로는 잡을 수 없는 **로직 일관성(TP-1)**과 **아키텍처 경계(TP-2)** 문제이며, 실제 조치가 필요한 항목입니다.
