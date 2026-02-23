# InterMax JAR-Decompiler & ClickUp Issue Analysis Bot

InterMax 패키지(Java JAR, .NET DLL)를 디컴파일하고, ClickUp 이슈를 Claude Code Agent Teams로 심층 분석하는 통합 도구입니다.

---

## 목차

1. [기능 소개](#기능-소개)
2. [아키텍처](#아키텍처)
3. [사전 준비](#사전-준비)
4. [환경 설정](#환경-설정)
5. [디컴파일 사용법](#디컴파일-사용법)
6. [이슈 분석 워크플로우](#이슈-분석-워크플로우)
7. [패치 리뷰 워크플로우](#패치-리뷰-워크플로우)
8. [자동화 (Scheduler)](#자동화-scheduler)
9. [CLI 레퍼런스](#cli-레퍼런스)
10. [디렉토리 구조](#디렉토리-구조)
11. [트러블슈팅](#트러블슈팅)

---

## 기능 소개

### 1. JAR/DLL 디컴파일러
- InterMax 패키지의 Java JAR 파일과 .NET DLL 파일을 소스코드로 디컴파일
- 압축 파일 자동 해제 (ZIP, TAR, TAR.GZ)
- InterMax 루트 디렉토리 자동 탐지
- 패키지 타입별 자동 처리

### 2. ClickUp Issue Analysis Bot (Agent Teams)
- ClickUp에서 이슈 자동 다운로드 (Custom Task ID 지원)
- **첨부파일 자동 처리**: 이미지 다운로드 + ZIP 아카이브 자동 해제
- **Claude Code Agent Teams를 활용한 심층 분석**
  - `issue-researcher`: 코드베이스 탐색 전문가 (읽기 전용)
  - `issue-analyzer`: 근본 원인 분석 + 보고서 작성 전문가
  - `issue-followup`: 팔로업 질문 처리 전문가
  - `patch-reviewer`: 패치 diff 분석 + 리뷰 보고서 작성 전문가
- **4가지 태스크 유형 지원**: 이슈 분석, 사양 문의, 개선 검증, 패치 리뷰
- 버전 정보 기반 소스코드 자동 매칭
- **팔로업 분석**: context.md 기반 후속 질문 처리 (크로스 세션 지원)

### 3. 패치 리뷰 파이프라인
- **ClickUp Doc 자동 연동**: 이슈에 링크된 ClickUp Doc에서 패치 파일 자동 다운로드
- **diff 자동 생성**: 패치 파일과 기존 packages/ 소스를 비교하여 unified diff 생성
- **AI 패치 리뷰**: QA/현장 엔지니어를 위한 변경 요약, 검증 시나리오, 리스크 분석 포함 보고서

### 4. 자동화 스케줄러
- Cron 기반 ClickUp 상태 변화 감지
- 상태 전환 시 자동 분석 트리거 (`claude -p`)
- 패치 파일 감지 시 자동 패치 리뷰 실행

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
│  ┌──────────────┐                                                        │
│  │ scheduler.py │  ← cron (매일 03:00) 또는 수동                         │
│  │ (상태 감지 + │     fetch → fetch_doc → patch_diff → claude -p        │
│  │  자동 분석)  │                                                        │
│  └──────────────┘                                                        │
└───────────────────────────────────────────────────────────────────────────┘
```

### 파이프라인별 역할

| 파이프라인 | 실행 방식 | 설명 |
|-----------|----------|------|
| **태스크 다운로드** | `fetch.py --task-id IMX-XXXX` | 이슈 메타데이터 + 첨부파일 다운로드 |
| **패치 다운로드** | `fetch_doc.py --task-id IMX-XXXX` | ClickUp Doc에서 패치 파일 다운로드 |
| **diff 생성** | `patch_diff.py --task-id IMX-XXXX` | 패치 vs 기존 소스 diff 생성 |
| **수동 분석** | Claude Code 대화형 세션 | "IMX-XXXX 분석해줘" → Agent Teams |
| **패치 리뷰** | Claude Code 대화형 세션 | "IMX-XXXX 패치 리뷰해줘" → patch-reviewer |
| **자동 분석** | `scheduler.py --auto` (cron) | 상태 변화 감지 → 자동 `claude -p` |

### 핵심 구성 요소

| 파일 | 역할 |
|------|------|
| `issuebot/fetch.py` | ClickUp API v2에서 태스크 다운로드 + ZIP 자동 해제 |
| `issuebot/fetch_doc.py` | ClickUp API v3 Docs에서 패치 파일 다운로드 |
| `issuebot/patch_diff.py` | 패치 파일 감지 + packages/ 소스와 diff 생성 |
| `issuebot/scheduler.py` | 상태 감지 + 자동 분석 스케줄러 (cron용) |
| `issuebot/inventory.py` | 패키지 인벤토리 생성 (버전 매칭용) |
| `.claude/agents/issue-researcher.md` | 코드베이스 탐색 agent 정의 |
| `.claude/agents/issue-analyzer.md` | 분석 + report.md/context.md 작성 agent 정의 |
| `.claude/agents/issue-followup.md` | 팔로업 질문 처리 agent 정의 |
| `.claude/agents/patch-reviewer.md` | 패치 diff 분석 + patch_review.md 작성 agent 정의 |
| `config/config.json` | ClickUp 및 스케줄러 설정 |

---

## 사전 준비

### 필수 프로그램

| 항목 | 요구사항 | 확인 방법 | 설치 링크 |
|------|----------|-----------|-----------|
| **Python** | 3.8+ | `python --version` | [Python](https://www.python.org/) |
| **Claude Code** | Max Plan 필요 | `claude --version` | [Claude Code](https://claude.ai/download) |
| **Java** | JDK 11+ (디컴파일용) | `java -version` | [Adoptium](https://adoptium.net/) |
| **.NET SDK** | 6.0+ (디컴파일용) | `dotnet --version` | [.NET](https://dotnet.microsoft.com/download) |

### API 키 발급

- **ClickUp API Key**: https://app.clickup.com/settings/apps

---

## 환경 설정

### 1. Python 가상환경 및 의존성 설치

```bash
# 가상환경 생성 (권장)
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 2. .env 파일 생성

```bash
cp .env.example .env
```

`.env` 파일 내용:
```env
CLICKUP_API_KEY=pk_your_actual_clickup_api_key_here

# 자동 분석 scheduler에서 "나에게 배정된 이슈" 판별용
# 확인 방법: ClickUp Settings > Apps 페이지
CLICKUP_USER_ID=12345678
```

### 3. config.json 설정

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
| `team_id` | ClickUp 팀 ID (= workspace_id) |
| `list_id` | ClickUp 리스트 ID |
| `filter_status` | `--fetch-only` 모드 기본 status |
| `watched_statuses` | `--auto` 모드에서 감시할 status 목록 |
| `activity_watch_statuses` | activity 변경 감지 대상 status (댓글/본문 업데이트) |
| `analysis_timeout_seconds` | `claude -p` 타임아웃 (초) |

**Team ID 찾는 법**: ClickUp 태스크 URL에서 확인
`https://app.clickup.com/t/25540965/IMX-9326` → `25540965`

---

## 디컴파일 사용법

### Windows (PowerShell)

```powershell
# 대화형 모드 (패키지 목록에서 선택)
.\decompiler\decompile.ps1

# 특정 패키지 지정
.\decompiler\decompile.ps1 -PackageName "package_v5.4.12.0.tar.gz"
```

### Linux / Mac (Bash)

```bash
chmod +x decompiler/decompile.sh
./decompiler/decompile.sh
```

### 출력 위치

```
packages/{패키지명}/{InterMax_루트}/decompiled/
├── datagather/         # .java 파일들
├── PlatformJS/         # .java 파일들
└── jspd/               # .java 파일들
```

---

## 이슈 분석 워크플로우

이슈 분석은 ClickUp 태스크를 다운로드한 뒤 Claude Code Agent Teams로 심층 분석하는 과정입니다.

### 전체 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│  이슈 분석 워크플로우                                            │
│                                                                  │
│  Step 1: 태스크 다운로드                                         │
│  $ python issuebot/fetch.py --task-id IMX-9326                  │
│       └─▶ tasks/IMX-9326/task.json, images/                     │
│                                                                  │
│  Step 2: Claude Code에서 분석 요청                               │
│  > "IMX-9326을 agent team으로 분석해줘"                          │
│                                                                  │
│  Step 3: Agent Teams 내부 동작                                   │
│  ┌──────────┐    task.json 읽기                                  │
│  │Team Lead │──▶ 태스크 유형 판별                                │
│  │(조율만)  │──▶ inventory.json 읽기                             │
│  └────┬─────┘                                                    │
│       │                                                          │
│       ├─▶ researcher (Explore agent)                             │
│       │     코드베이스 탐색                                       │
│       │     관련 파일 위치 식별                                    │
│       │         │                                                │
│       │         └─── 직접 SendMessage ────┐                      │
│       │                                   ▼                      │
│       └─▶ analyzer (general-purpose agent)                       │
│             researcher 결과 수신                                  │
│             심층 분석                                             │
│             report.md + context.md 직접 Write                    │
│                                                                  │
│  Step 4: 결과 확인                                               │
│  $ cat tasks/IMX-9326/report.md                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Step 1. ClickUp 태스크 다운로드

```bash
# Custom Task ID 사용 (권장)
python issuebot/fetch.py --task-id IMX-9326

# 리스트에서 open 상태만 다운로드
python issuebot/fetch.py --list-id 901234567 --status open

# 새 태스크만 다운로드 (이미 있는 것 스킵)
python issuebot/fetch.py --list-id 901234567 --status open --new-only
```

**fetch.py 주요 기능:**
- 이미지 첨부파일 자동 다운로드
- **ZIP 아카이브 자동 해제**: 로그 파일, 설정 파일 등을 자동 추출
- **markdown_description 저장**: ClickUp Doc 링크 추출 가능
- **linked_docs 메타데이터**: 연결된 Doc ID/Page ID 자동 추출

### Step 2. Agent Teams로 심층 분석

Claude Code를 실행하고 다음과 같이 요청합니다:

```
# 단일 이슈 분석
"IMX-9326을 agent team으로 분석해줘"

# 태스크 유형 지정
"IMX-9355 사양 확인해줘"
"IMX-9321 개선 검증해줘"

# 미분석 이슈 일괄 확인
"분석 안 된 이슈 목록 보여줘"
```

### 태스크 유형

| 유형 | 키워드 | 핵심 질문 | 출력 |
|------|--------|----------|------|
| 이슈 분석 | "안 됨", "오류", "에러" | 뭐가 안 되나? 왜? | report.md |
| 사양 문의 | "가능한지", "사양", "확인" | 이 기능이 있나? 어떻게 쓰나? | report.md |
| 개선 검증 | "개선", "추가", "변경" | 개선이 제대로 됐나? | report.md |
| 패치 리뷰 | "패치", "리뷰" | 패치가 제대로 됐나? | patch_review.md |

### Step 3. 팔로업 분석

기존 분석 결과에 대해 추가 질문이 가능합니다:

```
# 팔로업 질문
"IMX-8984 팔로업: visitor_criteria 변경 시 영향 범위는?"
"IMX-9321 추가 질문: v5.3에서도 동일 버그가 있나?"
```

- **context.md** 기반으로 이전 분석 맥락을 자동 로드
- 이미 탐색한 파일 재탐색 방지, 비효율 검색어 회피
- report.md에 "추가 분석 #N" 섹션이 누적
- 다른 세션에서도 팔로업 가능 (크로스 세션)

### Step 4. 결과 확인

```bash
# 분석 보고서 확인
cat tasks/IMX-9326/report.md

# 분석 컨텍스트 확인 (팔로업용)
cat tasks/IMX-9326/context.md
```

### 보고서 형식

보고서 대상은 **QA 엔지니어, 현장 설치 엔지니어**입니다 (개발자가 아님).

모든 보고서에 공통 포함되는 섹션:
- **버전 정보**: 관련 컴포넌트 버전 나열
- **분석 코드베이스**: 어떤 패키지 버전을 분석했는지, 요청 버전과 일치하는지 명시
- **QA 검증 방법**: UI 조작 기준 구체적 검증 시나리오
- **참고: 코드 레벨 분석 (개발자용)**: 파일 경로, 라인 번호, 원인 등

---

## 패치 리뷰 워크플로우

패치 리뷰는 개발자가 수정한 패치 파일을 기존 소스와 비교 분석하여, QA가 검증에 활용할 리뷰 보고서를 생성하는 과정입니다.

### 전체 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│  패치 리뷰 워크플로우                                            │
│                                                                  │
│  Step 1: 패치 파일 다운로드 (ClickUp Doc에서)                    │
│  $ python issuebot/fetch_doc.py --task-id IMX-9236              │
│       └─▶ tasks/IMX-9236/patches/                               │
│           ├── doc_content.md          (Doc 페이지 원문)          │
│           ├── {패치}.zip              (원본 아카이브)            │
│           └── {패치}/                 (자동 해제된 파일)         │
│               ├── DatePicker.js                                  │
│               ├── AlertHistory.js                                │
│               └── ...                                            │
│                                                                  │
│  Step 2: diff 생성 (패치 vs 기존 소스)                           │
│  $ python issuebot/patch_diff.py --task-id IMX-9236 --output-json│
│       └─▶ tasks/IMX-9236/                                       │
│           ├── patch_diff.md           (사람 읽기용 diff)         │
│           └── patch_diff.json         (agent 입력용 diff)        │
│                                                                  │
│  Step 3: Claude Code에서 패치 리뷰 요청                          │
│  > "IMX-9236 패치 리뷰해줘"                                     │
│                                                                  │
│  Step 4: patch-reviewer agent 동작                               │
│  ┌────────────────────────────────┐                              │
│  │ patch-reviewer (자립형)        │                              │
│  │  1. task.json 읽기             │                              │
│  │  2. patch_diff.json 읽기       │                              │
│  │  3. report.md 읽기 (있으면)    │  ← 기존 분석과 대조          │
│  │  4. doc_content.md 읽기        │  ← 패치노트 확인             │
│  │  5. diff 분석                  │                              │
│  │  6. patch_review.md 작성       │                              │
│  └────────────────────────────────┘                              │
│                                                                  │
│  Step 5: 결과 확인                                               │
│  $ cat tasks/IMX-9236/patch_review.md                            │
└─────────────────────────────────────────────────────────────────┘
```

### Step 1. 패치 파일 다운로드

패치 파일은 ClickUp Doc에 업로드되어 있습니다. `fetch_doc.py`가 이슈에 연결된 Doc을 자동으로 찾아 패치 파일을 다운로드합니다.

```bash
# Doc 탐색만 (다운로드 안 함)
python issuebot/fetch_doc.py --task-id IMX-9236 --dry-run

# 패치 파일 다운로드
python issuebot/fetch_doc.py --task-id IMX-9236

# 특정 Doc 직접 지정
python issuebot/fetch_doc.py --doc-id rbeb5-185442 --page-id rbeb5-3475418
```

**fetch_doc.py 동작 방식:**
1. `task.json`의 `markdown_description`에서 ClickUp Doc URL 추출
2. ClickUp v3 Docs API로 Doc 페이지 목록 조회
3. 태스크 ID가 포함된 페이지 탐색 (예: "IMX-9236 | 패치 파일")
4. 페이지 콘텐츠에서 첨부파일 URL 추출
5. `tasks/{ID}/patches/`에 다운로드 + ZIP/TAR 자동 해제
6. `doc_content.md`에 Doc 페이지 원문 저장

**패치 파일 소스 2가지:**

| 방식 | 설명 | 저장 위치 |
|------|------|-----------|
| **자동 (ClickUp Doc)** | `fetch_doc.py`로 자동 다운로드 | `tasks/{ID}/patches/` |
| **수동** | QA가 직접 파일 배치 | `tasks/{ID}/` 루트 또는 서브폴더 |

### Step 2. diff 생성

패치 파일과 `packages/` 내 기존 소스를 비교하여 unified diff를 생성합니다.

```bash
# 매칭 확인만 (diff 생성 안 함)
python issuebot/patch_diff.py --task-id IMX-9236 --dry-run

# diff + JSON 생성
python issuebot/patch_diff.py --task-id IMX-9236 --output-json

# diff만 생성 (JSON 없이)
python issuebot/patch_diff.py --task-id IMX-9236
```

**patch_diff.py 동작 방식:**
1. `tasks/{ID}/patches/`와 태스크 루트에서 패치 파일 자동 감지
2. `task.json`의 버전 정보로 `packages/` 내 최적 패키지 매칭
3. 경로 prefix 기반 컴포넌트 매핑:

   | 패치 경로 prefix | 컴포넌트 | packages/ 내 위치 |
   |-----------------|---------|------------------|
   | `intermax/` | PlatformJS 프론트 | `{pkg}/InterMax*/PlatformJS/intermax/` |
   | `jdg/` | DataGather | `{pkg}/InterMax*/decompiled/datagather/jdg/` |
   | `com/exem/platform/` | PlatformJS 백엔드 | `{pkg}/InterMax*/decompiled/PlatformJS/` |
   | `com/exem/jspd/` | JSPD | `{pkg}/InterMax*/decompiled/jspd/` |

4. 매칭된 파일 간 unified diff 생성
5. `patch_diff.md` (사람 읽기용) + `patch_diff.json` (agent 입력용) 출력

### Step 3. 패치 리뷰 요청

Claude Code에서 다음과 같이 요청합니다:

```
"IMX-9236 패치 리뷰해줘"
"IMX-9380 패치 분석해줘"
```

Team Lead는 내부적으로 다음을 실행합니다:
1. `fetch_doc.py`로 패치 파일 다운로드 (없으면)
2. `patch_diff.py`로 diff 생성 (없으면)
3. `patch-reviewer` agent 스폰

### Step 4. patch-reviewer agent

patch-reviewer는 **자립형 agent**로, task ID와 경로만 전달받으면 필요한 파일을 직접 읽고 분석합니다.

**입력 파일 (자동 로딩):**
| 파일 | 용도 | 필수 |
|------|------|------|
| `task.json` | 이슈 메타데이터, 버전 정보, URL | 필수 |
| `patch_diff.json` | diff 데이터 (없으면 자체 생성) | 필수 |
| `report.md` | 기존 이슈 분석과 대조 | 선택 |
| `patches/doc_content.md` | 패치노트/수정내용 확인 | 선택 |

### Step 5. 패치 리뷰 보고서

`patch_review.md`에 다음 섹션이 포함됩니다:

| 섹션 | 설명 | 대상 |
|------|------|------|
| **패치 요약** | 이 패치로 무엇이 바뀌는지 2-3문장 | QA/엔지니어 |
| **변경 파일 목록** | 파일별 변경 규모 + 1줄 요약 | QA/엔지니어 |
| **기존 이슈와의 대응** | report.md 지적 사항 vs 패치 반영 여부 | QA/엔지니어 |
| **QA 검증 시나리오** | UI 조작 기준 단계별 검증 방법 | QA |
| **리스크 및 주의사항** | 사이드 이펙트, 회귀 테스트, 누락 수정 | QA/개발 |
| **코드 변경 상세** | 파일별 변경 위치, 내용, 이유 | 개발자 |

---

## 자동화 (Scheduler)

scheduler.py는 ClickUp 이슈의 **상태 변화를 감지**하고 `claude -p`로 **자동 분석을 실행**합니다.

### 전체 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│  Scheduler 자동 분석 흐름                                        │
│                                                                  │
│  cron (매일 03:00)                                               │
│       │                                                          │
│       ▼                                                          │
│  scheduler.py --auto                                             │
│       │                                                          │
│       ├─▶ ClickUp API 폴링 (watched_statuses)                   │
│       │                                                          │
│       ├─▶ state.json과 비교 → 상태 전환 감지                     │
│       │                                                          │
│       ├─▶ 트리거 조건 판별                                       │
│       │   ├── 신규 open → 초동 분석                              │
│       │   ├── qa assigned (나) → 초동 분석                       │
│       │   └── qa to do (나) → 검증 분석                          │
│       │       ├── 패치 파일 있음?                                │
│       │       │   ├── Yes → fetch_doc → patch_diff               │
│       │       │   │         → claude -p "패치 리뷰해줘"          │
│       │       │   └── No  → claude -p "팔로업 검증"              │
│       │       └── report 없음? → 초동 분석                       │
│       │                                                          │
│       └─▶ claude -p 실행 → report.md 또는 patch_review.md 생성  │
└─────────────────────────────────────────────────────────────────┘
```

### 실행 모드

| 모드 | 명령어 | 용도 |
|------|--------|------|
| **초기화** | `--init-state` | tasks/에서 state.json 최초 생성 |
| **fetch만** | `--fetch-only` | 새 태스크 다운로드만 (기존 동작) |
| **감지만** | `--detect-only` | API 폴링 + 트리거 감지 (분석 안 함) |
| **자동 분석** | `--auto` | 감지 + 다운로드 + `claude -p` 분석 |
| **드라이런** | `--auto --dry-run` | 분석 명령어만 출력 (실행 안 함) |

### 초기 설정 (최초 1회)

```bash
# 1. .env에 CLICKUP_USER_ID 추가 (assignee 기반 트리거에 필요)
echo "CLICKUP_USER_ID=12345678" >> .env

# 2. 기존 tasks/에서 state.json 초기 생성
python issuebot/scheduler.py --init-state
```

### 사용법

```bash
# 트리거 감지만 확인 (분석 실행 안 함)
python issuebot/scheduler.py --detect-only

# 드라이런: 어떤 분석이 실행될지 미리 확인
python issuebot/scheduler.py --auto --dry-run

# 실제 자동 분석 실행
python issuebot/scheduler.py --auto

# fetch만 (기존 동작, 분석 안 함)
python issuebot/scheduler.py --fetch-only
```

### 트리거 규칙

| 상태 | 조건 | 분석 모드 | 동작 |
|------|------|----------|------|
| `open` | 신규 (state에 없음) | initial | 초동 분석 |
| `qa assigned` | 나에게 배정 + report 없음 | initial | 초동 분석 |
| `qa to do` | 나에게 배정 + 상태 전환 | verification | 패치 리뷰 또는 팔로업 |
| `qa to do` | 나에게 배정 + report 없음 | initial | report 없으면 초동부터 |
| `qa in review` | 나에게 배정 + activity 변경 | activity_update | 팔로업 분석 |
| `qa in progress` | 나에게 배정 + activity 변경 | activity_update | 팔로업 분석 |

**verification 모드 상세:**
1. `tasks/{ID}/patches/` 확인 → 패치 파일 존재 여부 판별
2. 없으면 `fetch_doc.py` 실행 → ClickUp Doc에서 패치 자동 다운로드
3. 패치 파일 있으면 → `patch_diff.py` 실행 → diff 생성 → 패치 리뷰 프롬프트
4. 패치 파일 없으면 → 기존 팔로업 검증 프롬프트

**activity_update 모드 상세:**
1. ClickUp API의 `date_updated` 타임스탬프로 변경 감지
2. report.md가 이미 있는 태스크만 대상 (없으면 initial이 먼저)
3. Self-trigger 필터링: 내가 쓴 댓글만 있으면 트리거 제외
4. 타인의 새 댓글 또는 본문 업데이트 시 팔로업 분석 실행

**멱등성**: state.json 업데이트 후 동일 트리거가 재발동하지 않습니다.
**실패 재시도**: 최대 3회 연속 실패 시 해당 task 스킵 (다음 상태 변화 시 리셋).

### Cron 설정

```bash
crontab -e

# 매일 오전 3시 실행
0 3 * * * cd /mnt/d/jar-decompiler && .venv/bin/python issuebot/scheduler.py --auto >> logs/scheduler.log 2>&1
```

> **주의**: PATH에 `claude` CLI 위치가 포함되어야 합니다.

---

## CLI 레퍼런스

### fetch.py

```bash
python issuebot/fetch.py [옵션]
```

| 옵션 | 설명 | 예시 |
|------|------|------|
| `--task-id` | 특정 태스크 ID | `--task-id IMX-9326` |
| `--team-id` | Team ID (custom ID 시 필요) | `--team-id 25540965` |
| `--list-id` | 리스트 ID (여러 태스크) | `--list-id 901234567` |
| `--status` | 단일 상태 필터 | `--status open` |
| `--statuses` | 복수 상태 필터 (콤마 구분) | `--statuses "open,qa assigned"` |
| `--tags` | 태그 필터 (콤마 구분) | `--tags "bug,critical"` |
| `--new-only` | 이미 다운로드된 태스크 스킵 | `--new-only` |

### fetch_doc.py

```bash
python issuebot/fetch_doc.py [옵션]
```

| 옵션 | 설명 | 예시 |
|------|------|------|
| `--task-id` | 태스크 ID (Doc 자동 탐색) | `--task-id IMX-9236` |
| `--doc-id` | 특정 Doc ID 직접 지정 | `--doc-id rbeb5-185442` |
| `--page-id` | 특정 페이지 ID 직접 지정 | `--page-id rbeb5-3475418` |
| `--dry-run` | 탐색만 (다운로드 안 함) | `--dry-run` |

### patch_diff.py

```bash
python issuebot/patch_diff.py [옵션]
```

| 옵션 | 설명 | 예시 |
|------|------|------|
| `--task-id` | 태스크 ID (필수) | `--task-id IMX-9236` |
| `--output-json` | JSON 형식도 함께 출력 | `--output-json` |
| `--dry-run` | 매칭 확인만 (diff 생성 안 함) | `--dry-run` |

### scheduler.py

```bash
python issuebot/scheduler.py [옵션]
```

| 옵션 | 설명 | 예시 |
|------|------|------|
| `--init-state` | state.json 최초 생성 | `--init-state` |
| `--fetch-only` | 새 태스크 다운로드만 | `--fetch-only` |
| `--detect-only` | 트리거 감지만 (분석 안 함) | `--detect-only` |
| `--auto` | 감지 + 다운로드 + 자동 분석 | `--auto` |
| `--dry-run` | `--auto`와 함께, 명령어만 출력 | `--auto --dry-run` |

### inventory.py

```bash
# 패키지 인벤토리 갱신 (새 패키지 추가 시)
python issuebot/inventory.py
```

---

## 디렉토리 구조

```
jar-decompiler/
├── .claude/agents/                # Agent Teams 정의
│   ├── issue-researcher.md          # 코드베이스 탐색 agent
│   ├── issue-analyzer.md            # 분석 + 보고서 작성 agent
│   ├── issue-followup.md            # 팔로업 분석 agent
│   └── patch-reviewer.md           # 패치 리뷰 agent
├── issuebot/                      # Issue Analysis Bot
│   ├── fetch.py                     # ClickUp 태스크 다운로드 + ZIP 해제
│   ├── fetch_doc.py                 # ClickUp Doc 패치 파일 다운로드
│   ├── patch_diff.py                # 패치 감지 + diff 생성 CLI
│   ├── scheduler.py                 # 상태 감지 + 자동 분석 스케줄러
│   └── inventory.py                 # 패키지 인벤토리 생성
├── decompiler/                    # 디컴파일 스크립트
│   ├── decompile.ps1                # Windows
│   └── decompile.sh                 # Linux/Mac
├── config/                        # 설정 파일
│   ├── config.json                  # ClickUp + 스케줄러 설정
│   └── prompts.json                 # 분석 템플릿 (참조용)
├── tools/                         # 디컴파일러 도구 (CFR, ILSpy)
├── packages/                      # 디컴파일된 패키지들 (gitignore)
│   ├── inventory.json               # 패키지 인벤토리 (자동 생성)
│   └── package_v5.4.*/              # 버전별 패키지
│       └── InterMax5.4/
│           └── decompiled/          # 디컴파일된 소스
│               ├── datagather/
│               ├── jspd/
│               └── PlatformJS/
├── tasks/                         # 분석 결과 (gitignore)
│   ├── state.json                   # 스케줄러 상태 추적 (자동 관리)
│   └── {TASK_ID}/
│       ├── task.json                # 태스크 메타데이터
│       ├── images/                  # 첨부파일 (이미지 + 아카이브 해제)
│       ├── patches/                 # 패치 파일 (fetch_doc.py가 다운로드)
│       │   ├── doc_content.md       #   Doc 페이지 원문
│       │   └── {패치파일}.zip/      #   자동 해제된 패치 파일
│       ├── report.md                # 분석 보고서 (추가 분석 누적)
│       ├── context.md               # 분석 컨텍스트 (팔로업용)
│       ├── patch_diff.md            # 패치 diff (사람 읽기용)
│       ├── patch_diff.json          # 패치 diff (agent 입력용)
│       └── patch_review.md          # 패치 리뷰 보고서
├── logs/                          # 스케줄러 로그 (gitignore)
├── .env                           # API 키 (gitignore)
├── CLAUDE.md                      # Claude Code Agent 지침
├── README.md
└── requirements.txt
```

---

## 트러블슈팅

### "report.md가 생성되지 않아요"

**원인**: Agent Teams 분석이 실행되지 않았습니다.

**해결**: Claude Code를 실행하고 `"IMX-XXXX를 agent team으로 분석해줘"` 라고 요청하세요.

### "패치 파일을 찾을 수 없어요"

**원인**: ClickUp Doc에 패치가 업로드되어 있지 않거나, Doc 링크가 태스크 description에 없습니다.

**해결**:
1. `fetch_doc.py --dry-run`으로 Doc 탐색 결과 확인
2. 수동으로 패치 파일을 `tasks/{ID}/patches/`에 배치

### "patch_diff.py가 파일을 매칭하지 못해요"

**원인**: 해당 버전의 패키지가 `packages/`에 없거나, 경로 prefix가 인식되지 않습니다.

**해결**:
1. `--dry-run`으로 매칭 결과 확인
2. 필요한 패키지 버전을 디컴파일하여 `packages/`에 추가
3. `python issuebot/inventory.py`로 인벤토리 갱신

### "이미지 분석이 안 돼요"

**해결**: 이미지 경로가 절대 경로로 task.json에 포함되어 있는지 확인. Claude의 Read 도구가 이미지를 읽을 수 있습니다.

### "externally-managed-environment 오류 (pip)"

**원인**: Python 3.12+에서 시스템 Python에 직접 설치가 제한됩니다.

**해결**: 가상환경 사용
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 주요 특징

- **Agent Teams 심층 분석**: researcher + analyzer 2인 협업, direct communication으로 병목 제거
- **4가지 태스크 유형**: 이슈 분석, 사양 문의, 개선 검증, 패치 리뷰 각각 맞춤 보고서
- **패치 리뷰 파이프라인**: ClickUp Doc → 패치 다운로드 → diff 생성 → AI 리뷰 보고서
- **ZIP 첨부파일 자동 해제**: 로그, 설정 파일 등 아카이브를 자동 추출하여 분석에 활용
- **팔로업 분석**: context.md 기반으로 후속 질문 처리 (크로스 세션 지원)
- **이미지 분석 지원**: 첨부된 스크린샷을 Claude가 직접 분석
- **버전 자동 매칭**: Custom Fields에서 버전 추출 → 인접 버전 자동 매칭 → 보고서에 분석 코드베이스 명시
- **한국어 분석 보고서**: 보고서 대상 = QA/현장 엔지니어 (코드 분석은 참고 섹션으로 분리)
- **자동 분석 스케줄러**: Cron으로 상태 변화 감지 → 패치 자동 다운로드 → diff 생성 → `claude -p` 분석
- **Claude Code Max Plan**: API 키 불필요 (Max Plan 로그인만 필요)

---

## 라이센스

이 프로젝트는 EXEM, Inc.의 InterMax 지원팀을 위한 내부 도구입니다.
