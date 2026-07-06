# Korean History AI Server

Python, FastAPI, OpenAI API를 이용한 한국사능력검정시험 학습 보조 서버입니다.
프론트엔드는 나중에 붙일 수 있도록 REST API 형태로 구성했습니다.

## 주요 기능

- 한국사능력검정시험 문제 생성
- 시험 관련 질의응답
- 간단한 일상 대화 및 시험 동기부여
- 입력값 검증, 요청 크기 제한, 간단한 IP 기반 Rate Limit, 보안 헤더, 비밀값 로그 마스킹 적용

## 폴더 구조

```text
app/
  core/        설정, 예외 처리, 보안 미들웨어, 프롬프트
  models/      Pydantic 요청/응답 스키마
  routers/     FastAPI 라우터
  services/    OpenAI 연동 및 안전 처리
tests/         기본 검증 테스트
```

## VSCode 실행 방법

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

`.env` 파일에서 `OPENAI_API_KEY`를 본인 키로 바꿉니다.

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

브라우저에서 아래 주소를 엽니다.

```text
http://127.0.0.1:8000/docs
```

## API 예시

### 1. 문제 생성

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/questions/generate" ^
  -H "Content-Type: application/json" ^
  -d "{\"topic\":\"삼국시대\",\"difficulty\":\"intermediate\",\"question_type\":\"multiple_choice\",\"count\":3,\"include_explanation\":true}"
```

### 2. 시험 관련 질의응답

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/chat/exam" ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"흥선대원군의 정책을 시험에 나오는 포인트 중심으로 설명해줘\"}"
```

### 3. 동기부여 대화

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/chat/motivation" ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"공부가 너무 하기 싫어. 오늘 어떻게 시작하지?\"}"
```

## 보안 점검 명령어

```bash
ruff check app tests
bandit -r app
pip-audit
pytest
```

## 다음 확장 방향

- 사용자 계정/JWT 로그인
- 문제 저장 DB 연동
- 오답노트, 회차별 모의고사, 풀이 이력
- 관리자 페이지
- 공식 기출 데이터 기반 RAG 검색
