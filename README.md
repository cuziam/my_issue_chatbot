# InterMax Issue Analysis Bot

InterMax 패키지(Java JAR, .NET DLL)를 디컴파일하고, ClickUp 이슈를 Claude Code Agent Teams로 심층 분석하는 통합 도구입니다.

---

## 목차

1. [Quick Start](#quick-start)
2. [기능 소개](#기능-소개)
3. [아키텍처](#아키텍처)
4. [사전 준비](#사전-준비)
5. [환경 설정](#환경-설정)
6. [Web Dashboard](#web-dashboard)
7. [CLI 레퍼런스](#cli-레퍼런스)
8. [Docker 배포](#docker-배포)
9. [디렉토리 구조](#디렉토리-구조)
10. [트러블슈팅](#트러블슈팅)

---

## Quick Start

### 로컬 개발

```bash
# 1. 클론 + 환경 설정
git clone <repo-url> && cd jar-decompiler
cp .env.example .env          # API 키 입력

# 2. 의존성 설치 (Python + Node.js)
make install

# 3. 개발 서버 실행 (백엔드 :8000 + 프론트엔드 :5173)
make dev
```

### Docker 배포

```bash
cp .env.example .env          # API 키 입력
docker compose up --build -d  # http://localhost:8000
```

### 프로덕션 (빌드 후 단일 서버)

```bash
make build                    # 프론트엔드 빌드
make start                    # uvicorn :8000 (SPA 포함)
```

---

## 기능 소개

### 1. JAR/DLL 디컴파일러
- InterMax 패키지의 Java JAR (.java, CFR) / .NET DLL (.cs, ILSpy) 소스코드 디컴파일
- 압축 파일 자동 해제 (ZIP, TAR, TAR.GZ)
- 분석 시 `needs_decompile` 패키지 자동 감지 및 디컴파일

### 2. ClickUp Issue Analysis Bot (Agent Teams)
- ClickUp에서 이슈 자동 다운로드 (Custom Task ID 지원)
- **첨부파일 자동 처리**: 이미지 다운로드 + ZIP 아카이브 자동 해제
- **Claude Code Agent Teams를 활용한 심층 분석**
  - `issue-researcher`: 코드베이스 탐색 전문가
  - `issue-analyzer`: 근본 원인 분석 + 보고서 작성
  - `issue-followup`: 팔로업 질문 처리
  - `patch-reviewer`: 패치 diff 분석 + 리뷰 보고서 작성
- **4가지 태스크 유형**: 이슈 분석, 사양 문의, 개선 검증, 패치 리뷰

### 3. 패치 리뷰 파이프라인
- **ClickUp Doc 자동 연동**: 이슈에 링크된 Doc에서 패치 파일 자동 다운로드
- **diff 자동 생성**: 패치 파일과 기존 packages/ 소스를 비교하여 unified diff 생성
- **AI 패치 리뷰**: QA/현장 엔지니어를 위한 변경 요약, 검증 시나리오, 리스크 분석

### 4. 버전 Diff (Verification)
- 명시적 패치 파일 없이도 **패키지 버전 간 소스 비교** 자동 생성
- 기존 report.md의 분석 패키지 → 최신 패키지 간 diff

### 5. 자동화 스케줄러
- ClickUp 상태 변화 폴링 감지 (Web UI 또는 Cron)
- 상태 전환 시 자동 분석 트리거 (`claude -p`)
- 패치 파일 감지 시 자동 패치 리뷰 실행

### 6. Web Dashboard
- **FastAPI + React SPA**: 태스크 관리, 분석 실행, 스케줄러 제어
- **실시간 모니터링**: WebSocket 기반 Progress Timeline (도구 호출, 텍스트 출력, 비용 추적)
- **Chat Panel**: 태스크 컨텍스트 자동 주입 대화형 팔로업
- **4가지 분석 모드**: Initial Analysis, Verification, Activity Update, Patch Review

---

## 아키텍처

```
┌───────────────────────────────────────────────────────────────────────────┐
│                           전체 데이터 흐름                                 │
│                                                                           │
│  ClickUp                                                                  │
│  ┌────────────┐  ┌────────────┐                                          │
│  │ Task API   │  │ Doc API    │                                          │
│  │ (v2)       │  │ (v3)       │                                          │
│  └─────┬──────┘  └─────┬──────┘                                          │
│        │               │                                                  │
│        ▼               ▼                                                  │
│  ┌──────────┐   ┌────────────┐                                           │
│  │ fetch.py │   │fetch_doc.py│                                           │
│  │(태스크   │   │(패치 파일  │                                           │
│  │ 다운로드)│   │ 다운로드)  │                                           │
│  └─────┬────┘   └─────┬──────┘                                           │
│        │              │                                                   │
│        ▼              ▼                                                   │
│  ┌──────────────────────────┐     ┌──────────────────────────────────┐   │
│  │      tasks/{ID}/         │     │      packages/                   │   │
│  │  ├── task.json           │     │  ├── inventory.json              │   │
│  │  ├── images/             │     │  └── package_v5.4.*/             │   │
│  │  └── patches/            │     │      └── decompiled/             │   │
│  └──────────┬───────────────┘     └───────────────┬──────────────────┘   │
│             │                                     │                      │
│             ▼                                     │                      │
│  ┌───────────────┐                                │                      │
│  │ patch_diff.py │◀───────────────────────────────┘                      │
│  │ (diff 생성)   │                                                       │
│  └───────┬───────┘                                                       │
│          │                                                                │
│          ▼                                                                │
│  ┌────────────────────────────────────────────────────────────────┐      │
│  │                    Claude Code Agent Teams                     │      │
│  │  ┌────────────┐  ┌────────────┐  ┌───────────────────┐       │      │
│  │  │ researcher │─▶│  analyzer  │  │  patch-reviewer   │       │      │
│  │  │(코드 탐색) │  │(분석+보고) │  │(패치 diff 리뷰)   │       │      │
│  │  └────────────┘  └─────┬──────┘  └────────┬──────────┘       │      │
│  └────────────────────────┼──────────────────┼──────────────────┘      │
│                           ▼                  ▼                          │
│                      report.md         patch_review.md                  │
│                      context.md                                         │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────┐       │
│  │              Web Dashboard (localhost:8000)                    │       │
│  │  React SPA ◀──WebSocket──▶ FastAPI                            │       │
│  │  ├── Dashboard: 태스크 목록 + 상태                            │       │
│  │  ├── TaskDetail: Actions + Artifacts + Chat Panel             │       │
│  │  ├── Jobs: 실행 중/최근 분석 작업 모니터링                     │       │
│  │  ├── Scheduler: 상태 감지 + 자동 분석 실행                    │       │
│  │  └── Settings: config.json / .env 편집 + 패키지 관리          │       │
│  └───────────────────────────────────────────────────────────────┘       │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 사전 준비

### 필수 프로그램

| 항목 | 요구사항 | 확인 방법 |
|------|----------|-----------|
| **Python** | 3.8+ | `python --version` |
| **Claude Code** | Max Plan 필요 | `claude --version` |
| **Node.js** | 18+ (Web Dashboard) | `node --version` |
| **Java** | JDK 11+ (디컴파일용) | `java -version` |
| **.NET SDK** | 6.0+ (DLL 디컴파일용) | `dotnet --version` |

### API 키 발급

- **ClickUp API Key**: https://app.clickup.com/settings/apps

---

## 환경 설정

### 1. 의존성 설치

```bash
make install    # pip install -r requirements.txt + npm install

# 또는 수동:
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac (.venv\Scripts\activate on Windows)
pip install -r requirements.txt
cd web/frontend && npm install
```

### 2. .env 파일 생성

```bash
cp .env.example .env
```

`.env` 파일 내용:
```env
CLICKUP_API_KEY=pk_your_actual_clickup_api_key_here

# 자동 분석 scheduler에서 "나에게 배정된 이슈" 판별용
CLICKUP_USER_ID=12345678
```

### 3. config.json 설정

`config/config.json`:
```json
{
  "clickup": {
    "team_id": "25540965"
  },
  "scheduler": {
    "list_id": "YOUR_LIST_ID",
    "filter_status": "open",
    "watched_statuses": ["open", "qa assigned", "qa to do", "qa in review", "qa in progress"],
    "activity_watch_statuses": ["qa in review", "qa in progress"],
    "analysis_timeout_seconds": 600
  }
}
```

| 설정 | 설명 |
|------|------|
| `team_id` | ClickUp 팀 ID (= workspace_id). 태스크 URL에서 확인: `https://app.clickup.com/t/25540965/IMX-9326` |
| `list_id` | 감시할 ClickUp 리스트 ID |
| `watched_statuses` | 스케줄러가 감시할 상태 목록 |
| `analysis_timeout_seconds` | `claude -p` 타임아웃 (초) |

---

## Web Dashboard

브라우저에서 태스크 관리, 분석 실행, 실시간 모니터링을 수행하는 웹 애플리케이션입니다.

### 시작 방법

```bash
make dev       # 개발 모드: 백엔드 :8000 + 프론트엔드 :5173
make build && make start  # 프로덕션: 빌드 후 uvicorn :8000
docker compose up --build -d  # Docker: http://localhost:8000
```

### 주요 페이지

| 페이지 | 경로 | 기능 |
|--------|------|------|
| **Dashboard** | `/` | 태스크 목록, 상태별 필터, 검색 |
| **Task Detail** | `/tasks/:id` | 이슈 상세, Actions (Analyze/Fetch Doc/Generate Diff), Artifacts 뷰어, Chat Panel |
| **Jobs** | `/jobs` | 실행 중 / 최근 완료 분석 작업 모니터링, Progress Timeline |
| **Scheduler** | `/scheduler` | Poller 제어, 트리거 목록, 폴링 로그 |
| **Settings** | `/settings` | config.json 편집, .env 편집, 패키지 인벤토리/업로드 |

### 분석 모드

| 모드 | 설명 | 출력 |
|------|------|------|
| **Initial Analysis** | Researcher + Analyzer team으로 이슈 최초 분석 | report.md |
| **Verification** | 개발자 수정 후 QA 검증 (패치 리뷰 또는 버전 diff) | patch_review.md 또는 report.md 추가 |
| **Activity Update** | 새 댓글/본문 변경 감지 후 팔로업 | report.md 추가 분석 |
| **Patch Review** | 패치 파일을 기존 소스와 diff 비교 분석 | patch_review.md |

### Chat Panel

Task Detail 페이지에서 태스크에 대한 대화형 팔로업 질문이 가능합니다.

- **새 세션**: 태스크 컨텍스트(task.json, 버전, 설명, 댓글, artifacts)를 자동 주입
- **세션 resume**: 기존 분석 세션을 이어받아 전체 컨텍스트 유지
- **실시간 스트리밍**: WebSocket으로 AI 응답 실시간 표시
- **파일 첨부**: 이미지, 텍스트, ZIP 파일 업로드 지원

### Scheduler (Poller)

Web UI의 Scheduler 페이지에서 ClickUp 상태 변화 감지를 제어합니다.

**트리거 조건:**

| 상태 | 조건 | 분석 모드 |
|------|------|----------|
| `open` | 신규 태스크 | initial |
| `qa assigned` | 나에게 배정 + report 없음 | initial |
| `qa to do` | 상태 전환 | verification (패치 리뷰 또는 버전 diff) |
| `qa in review/progress` | activity 변경 | activity_update (팔로업) |

**서버 시작 시 자동 시작** (`config.json`):
```json
{
  "scheduler": {
    "poller": {
      "enabled_on_startup": true,
      "interval_minutes": 30,
      "auto_analyze": true
    }
  }
}
```

### REST API

| 엔드포인트 | 설명 |
|-----------|------|
| `/api/tasks` | 태스크 CRUD |
| `/api/analysis` | 분석 실행 + WebSocket 스트리밍 |
| `/api/chat` | 대화형 팔로업 |
| `/api/scheduler` | Poller 제어, 트리거 관리 |
| `/api/patches` | fetch_doc, patch_diff 실행 |
| `/api/settings` | config.json / .env 편집 |
| `/api/state` | 서버 상태 (health, version) |
| `/api/packages` | 패키지 인벤토리, 업로드 |

---

## CLI 레퍼런스

### fetch.py — 태스크 다운로드

```bash
python issuebot/fetch.py --task-id IMX-9326                           # 단일 태스크
python issuebot/fetch.py --list-id 901234567 --status open             # 리스트에서 open만
python issuebot/fetch.py --list-id 901234567 --status open --new-only  # 이미 있는 것 스킵
```

### fetch_doc.py — ClickUp Doc 패치 다운로드

```bash
python issuebot/fetch_doc.py --task-id IMX-9236 --dry-run   # 탐색만
python issuebot/fetch_doc.py --task-id IMX-9236              # 다운로드
```

### patch_diff.py — 패치 diff 생성

```bash
python issuebot/patch_diff.py --task-id IMX-9236 --dry-run       # 매칭 확인만
python issuebot/patch_diff.py --task-id IMX-9236 --output-json   # diff + JSON 생성
```

### version_diff.py — 버전 간 소스 diff

```bash
python issuebot/version_diff.py --task-id IMX-9227 --dry-run    # 미리보기
python issuebot/version_diff.py --task-id IMX-9227               # diff 생성
```

### scheduler.py — 스케줄러 CLI

```bash
python issuebot/scheduler.py --init-state     # state.json 최초 생성
python issuebot/scheduler.py --detect-only    # 트리거 감지만
python issuebot/scheduler.py --fetch-only     # 태스크 다운로드만
python issuebot/scheduler.py --auto           # 감지 + 다운로드 + 자동 분석
python issuebot/scheduler.py --auto --dry-run # 명령어만 출력
```

### inventory.py — 패키지 인벤토리

```bash
python issuebot/inventory.py             # 인벤토리 갱신
python issuebot/inventory.py --summary   # 요약 표시
```

### decompile_runner.py — 디컴파일

```bash
python issuebot/decompile_runner.py --check                        # 사전 조건 확인
python issuebot/decompile_runner.py --package package_v5.4.12.0    # 특정 패키지
python issuebot/decompile_runner.py --all                          # 전체 디컴파일
```

### 디컴파일 스크립트 (직접 실행)

```bash
# Windows
.\decompiler\decompile.ps1

# Linux/Mac
./decompiler/decompile.sh
```

### Cron 설정 (선택)

```bash
# 매일 오전 3시 자동 분석
0 3 * * * cd /path/to/jar-decompiler && .venv/bin/python issuebot/scheduler.py --auto >> logs/scheduler.log 2>&1
```

---

## Docker 배포

```bash
docker compose up --build -d    # 빌드 + 실행
docker compose logs -f          # 로그 확인
docker compose down             # 중지
```

### 환경변수 오버라이드

| 환경변수 | 기본값 | 설명 |
|----------|--------|------|
| `ISSUEBOT_ROOT` | 프로젝트 루트 자동 감지 | 프로젝트 루트 디렉토리 |
| `ISSUEBOT_TASKS_DIR` | `{ROOT}/tasks` | 분석 결과 저장 위치 |
| `ISSUEBOT_PACKAGES_DIR` | `{ROOT}/packages` | 디컴파일된 패키지 위치 |
| `ISSUEBOT_LOGS_DIR` | `{ROOT}/logs` | 로그 저장 위치 |
| `VITE_API_BASE_URL` | `/api` | 프론트엔드 API 엔드포인트 (빌드 시) |

Dockerfile은 Multi-stage 빌드를 사용합니다:
1. **Stage 1** (node:20-alpine): 프론트엔드 빌드
2. **Stage 2** (python:3.13-slim): Python 백엔드 + Java 런타임 + 빌드된 SPA

---

## 디렉토리 구조

```
jar-decompiler/
├── issuebot/                       # Python 모듈 — 분석 봇 핵심 로직
│   ├── config.py                     # 통합 config 로더
│   ├── shared.py                     # 패치 감지 상수/유틸
│   ├── fetch.py                      # ClickUp 태스크 다운로드
│   ├── fetch_doc.py                  # ClickUp Doc 패치 파일 다운로드
│   ├── patch_diff.py                 # 패치 감지 + diff 생성
│   ├── version_diff.py               # 패키지 버전 간 소스 diff 생성
│   ├── decompile_runner.py           # 자동 디컴파일 래퍼
│   ├── scheduler.py                  # 상태 감지 + 자동 분석
│   └── inventory.py                  # 패키지 인벤토리 생성
│
├── web/                            # Web Dashboard
│   ├── backend/                      # FastAPI 서버
│   │   ├── main.py                   # 앱 엔트리포인트
│   │   ├── config.py                 # 경로 설정 (환경변수 오버라이드)
│   │   ├── models/                   # 데이터 모델
│   │   ├── routers/                  # API 라우터 (8개)
│   │   ├── services/                 # 비즈니스 로직
│   │   │   ├── analysis/             #   분석 파이프라인
│   │   │   ├── chat/                 #   대화 세션 관리
│   │   │   ├── llm/                  #   LLM 백엔드 추상화
│   │   │   └── *.py                  #   task, patch, package, scheduler 서비스
│   │   ├── utils/platform.py         # 플랫폼 독립 유틸 (Windows/Linux)
│   │   └── ws/manager.py            # WebSocket 관리
│   │
│   └── frontend/                     # React + Vite + Tailwind CSS
│       └── src/
│           ├── pages/                # Dashboard, TaskDetail, Jobs
│           │   ├── scheduler/        #   Scheduler 서브 페이지
│           │   └── settings/         #   Settings 서브 페이지
│           ├── components/           # UI 컴포넌트
│           │   ├── chat/             #   ChatPanel 컴포넌트
│           │   ├── task-detail/      #   태스크 상세 탭
│           │   └── ui/              #   공통 UI (Button, Card 등)
│           ├── stores/               # Zustand 상태 관리
│           ├── contexts/             # WebSocket, ImageLightbox
│           └── api/client.ts         # REST API 클라이언트
│
├── .claude/agents/                 # Agent Teams 정의
│   ├── issue-researcher.md           # 코드베이스 탐색 agent
│   ├── issue-analyzer.md             # 분석 + 보고서 작성 agent
│   ├── issue-followup.md             # 팔로업 분석 agent
│   └── patch-reviewer.md            # 패치 리뷰 agent
│
├── decompiler/                     # 디컴파일 스크립트
│   ├── decompile.ps1                 # Windows
│   └── decompile.sh                  # Linux/Mac
├── config/                         # 설정 파일
│   ├── config.json                   # ClickUp + 스케줄러 설정
│   └── prompts.json                  # 분석 프롬프트 템플릿
├── tools/                          # 디컴파일러 도구 (CFR, ILSpy)
├── packages/                       # 디컴파일된 패키지 (gitignore)
├── tasks/                          # 분석 결과 (gitignore)
│   └── {TASK_ID}/
│       ├── task.json                 # 태스크 메타데이터
│       ├── images/                   # 첨부파일
│       ├── patches/                  # 패치 파일
│       ├── report.md                 # 분석 보고서
│       ├── context.md                # 분석 컨텍스트 (팔로업용)
│       ├── patch_diff.md/json        # 패치 diff
│       └── patch_review.md           # 패치 리뷰 보고서
├── logs/                           # 런타임 로그 (gitignore)
│
├── Dockerfile                      # Multi-stage 빌드
├── docker-compose.yml              # 컨테이너 오케스트레이션
├── Makefile                        # dev, install, build, start, docker
├── .env.example                    # 환경변수 템플릿
├── requirements.txt                # Python 의존성
└── CLAUDE.md                       # Claude Code Agent 지침
```

---

## 트러블슈팅

### "Analysis가 0초 만에 실패합니다"

`claude` CLI가 다른 Claude Code 세션 내에서 실행되면 중첩 세션 방지로 거부됩니다. Web Dashboard 서버를 **일반 터미널**에서 실행하세요.

진단: `GET /api/analysis/diagnostic`

### "패치 파일을 찾을 수 없어요"

1. `fetch_doc.py --dry-run`으로 Doc 탐색 결과 확인
2. 수동으로 `tasks/{ID}/patches/`에 파일 배치

### "patch_diff.py가 파일을 매칭하지 못해요"

1. `--dry-run`으로 매칭 결과 확인
2. 필요한 버전 패키지를 `packages/`에 추가 후 `python issuebot/inventory.py`

### "디컴파일이 안 돼요"

`python issuebot/decompile_runner.py --check`로 사전 조건 확인 (Java JDK 11+, CFR, ILSpy)

### "Progress가 표시되지 않습니다"

Vite dev server 사용 시 `vite.config.ts`의 `/api` 프록시에 `ws: true` 설정 확인

### "externally-managed-environment 오류 (pip)"

Python 3.12+에서는 가상환경 사용 필수:
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

---

## Makefile 명령어

| 명령어 | 설명 |
|--------|------|
| `make install` | Python + Node.js 의존성 설치 |
| `make dev` | 백엔드 (:8000) + 프론트엔드 (:5173) 개발 서버 |
| `make build` | 프론트엔드 프로덕션 빌드 |
| `make start` | 프로덕션 서버 (빌드된 SPA 포함) |
| `make docker-up` | Docker 빌드 + 실행 |
| `make docker-down` | Docker 중지 |

---

## 라이센스

이 프로젝트는 EXEM, Inc.의 InterMax 지원팀을 위한 내부 도구입니다.
