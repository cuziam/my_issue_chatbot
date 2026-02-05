# InterMax JAR-Decompiler & ClickUp Issue Analysis Bot

InterMax 패키지(Java JAR, .NET DLL)를 디컴파일하고, ClickUp 이슈를 Claude AI로 자동 분석하는 통합 도구입니다.

---

## 목차

1. [기능 소개](#기능-소개)
2. [아키텍처](#아키텍처)
3. [사전 준비](#사전-준비)
4. [환경 설정](#환경-설정)
5. [디컴파일 사용법](#디컴파일-사용법)
6. [이슈 분석 사용법](#이슈-분석-사용법)
7. [자동화 (Scheduler)](#자동화-scheduler)
8. [고급 기능](#고급-기능)
9. [트러블슈팅](#트러블슈팅)

---

## 기능 소개

### 1. JAR/DLL 디컴파일러
- InterMax 패키지의 Java JAR 파일과 .NET DLL 파일을 소스코드로 디컴파일
- 압축 파일 자동 해제 (ZIP, TAR, TAR.GZ)
- InterMax 루트 디렉토리 자동 탐지
- 패키지 타입별 자동 처리

### 2. ClickUp Issue Analysis Bot
- ClickUp에서 이슈 자동 다운로드 (Custom Task ID 지원)
- 이미지 첨부파일 자동 다운로드
- **Claude Code CLI를 활용한 실시간 자동 분석**
- 버전 정보 기반 소스코드 자동 매칭
- **Cron 기반 자동화 스케줄러**

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                      scheduler.py (자동화)                       │
│  • Cron으로 주기 실행                                            │
│  • 새 task 자동 감지 및 분석                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│       fetch.py          │     │      analyze.py         │
│  ClickUp task 다운로드   │────▶│  Claude Code 분석 실행   │
└─────────────────────────┘     └─────────────────────────┘
              │                               │
              ▼                               ▼
        ┌──────────┐                   ┌──────────┐
        │  tasks/  │                   │ packages/│
        │ 태스크   │                   │ 디컴파일 │
        │ 데이터   │                   │ 소스코드 │
        └──────────┘                   └──────────┘
```

### 핵심 구성 요소

| 파일 | 역할 |
|------|------|
| `issuebot/fetch.py` | ClickUp API에서 태스크 및 이미지 다운로드 |
| `issuebot/analyze.py` | Claude Code CLI를 호출하여 이슈 분석 실행 |
| `issuebot/scheduler.py` | 자동화 스케줄러 (cron용) |
| `issuebot/batch.py` | 여러 태스크 일괄 처리 |
| `config/config.json` | Claude 및 ClickUp 설정 |
| `config/prompts.json` | 분석 템플릿 (한국어) |

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
```

### 3. config.json 설정

```json
{
  "clickup": {
    "team_id": "25540965"
  },
  "claude": {
    "allowed_tools": "Read,Glob,Grep,Bash,Write,Edit,WebFetch,WebSearch",
    "timeout_seconds": 1800
  },
  "scheduler": {
    "list_id": "YOUR_LIST_ID",
    "filter_status": "open",
    "auto_analyze": true,
    "template": "issue_analysis"
  }
}
```

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

## 이슈 분석 사용법

### 1. ClickUp 태스크 다운로드

```bash
# Custom Task ID 사용 (권장)
python issuebot/fetch.py --task-id IMX-9326

# 리스트에서 open 상태만 다운로드
python issuebot/fetch.py --list-id 901234567 --status open

# 새 태스크만 다운로드 (이미 있는 것 스킵)
python issuebot/fetch.py --list-id 901234567 --status open --new-only
```

**fetch.py 옵션:**
| 옵션 | 설명 |
|------|------|
| `--task-id` | 특정 태스크 ID (IMX-9326 또는 숫자 ID) |
| `--list-id` | 리스트 ID (여러 태스크 다운로드) |
| `--status` | 상태 필터 (open, in progress 등) |
| `--tags` | 태그 필터 (콤마 구분) |
| `--new-only` | 이미 다운로드된 태스크 스킵 |

### 2. Claude로 분석 실행

```bash
python issuebot/analyze.py --task-id IMX-9326 --template issue_analysis
```

**실시간 출력 예시:**
```
============================================================
Starting Claude Code analysis...
============================================================

This may take several minutes. Progress will appear below:

------------------------------------------------------------
[System] Initialized
[Claude] 태스크를 분석하겠습니다. 먼저 첨부된 이미지와 관련 코드베이스를 확인하겠습니다....
[Tool] Reading: /mnt/d/jar-decompiler/tasks/IMX-9326/images/image_0.png...
[Tool] Searching: packages/**/decompiled/**/*.java
[Tool] Grep: JeusContainer
[Claude] JEUS 9 관련 코드를 분석한 결과...
[Tool] Writing: /mnt/d/jar-decompiler/tasks/IMX-9326/report.md...

[Done] Completed in 265.6s (30 turns)
------------------------------------------------------------

Report saved to: tasks/IMX-9326/report.md

Analysis complete!
```

### 분석 템플릿

| 템플릿 | 설명 | 사용 시기 |
|--------|------|-----------|
| `issue_analysis` | 근본 원인 분석 + 재현 단계 | 버그/이슈 분석 |
| `spec_inquiry` | 기능 사양 확인 | 기능 질문 답변 |
| `improvement_request` | 개선 제안 분석 | 기능 개선 요청 |

### 3. 결과 확인

```bash
# 분석 보고서 확인
cat tasks/IMX-9326/report.md
```

---

## 자동화 (Scheduler)

### scheduler.py 사용법

새 태스크를 자동으로 가져와서 분석하는 스케줄러입니다.

```bash
# 기본 사용
python issuebot/scheduler.py --list-id 901234567

# 상태 필터 지정
python issuebot/scheduler.py --list-id 901234567 --status open

# fetch만 실행 (분석 없이)
python issuebot/scheduler.py --list-id 901234567 --fetch-only

# 미리보기 (실제 실행 없음)
python issuebot/scheduler.py --list-id 901234567 --dry-run
```

**scheduler.py 옵션:**
| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--list-id` | ClickUp 리스트 ID (필수) | config.json |
| `--status` | 필터링할 상태 | open |
| `--template` | 분석 템플릿 | issue_analysis |
| `--fetch-only` | 분석 없이 다운로드만 | false |
| `--dry-run` | 실제 실행 없이 미리보기 | false |

### Cron 설정

```bash
# crontab 편집
crontab -e

# 매 시간 정각에 실행
0 * * * * cd /mnt/d/jar-decompiler && /path/to/venv/bin/python issuebot/scheduler.py --list-id 901234567 >> logs/scheduler.log 2>&1

# 매일 오전 9시에 실행
0 9 * * * cd /mnt/d/jar-decompiler && /path/to/venv/bin/python issuebot/scheduler.py --list-id 901234567 >> logs/scheduler.log 2>&1
```

### config.json 스케줄러 설정

```json
{
  "scheduler": {
    "list_id": "901234567",
    "filter_status": "open",
    "auto_analyze": true,
    "template": "issue_analysis"
  }
}
```

설정해두면 `--list-id` 없이 실행 가능:
```bash
python issuebot/scheduler.py
```

---

## 고급 기능

### 여러 태스크 일괄 분석

```bash
# 순차 분석
python issuebot/batch.py --task-ids IMX-9326,IMX-9344

# 병렬 실행 (별도 터미널 창)
python issuebot/batch.py --task-ids IMX-9326,IMX-9344 --separate-terminals
```

### Claude 설정 커스터마이징

`config/config.json`에서 수정:

```json
{
  "claude": {
    "allowed_tools": "Read,Glob,Grep,Bash,Write,Edit,WebFetch,WebSearch",
    "timeout_seconds": 1800
  }
}
```

**사용 가능한 도구:**
- `Read` - 파일/이미지 읽기
- `Glob` - 파일 패턴 검색
- `Grep` - 내용 검색
- `Bash` - 명령 실행
- `Write` - 파일 쓰기 (report.md 생성에 필수)
- `Edit` - 파일 편집
- `WebFetch` - 웹 페이지 가져오기
- `WebSearch` - 웹 검색

---

## 트러블슈팅

### "Claude 출력이 보이지 않아요"

**원인**: 이전 버전에서는 subprocess 버퍼링 문제가 있었습니다.

**해결**: `--output-format stream-json --verbose` 옵션 사용 (현재 버전에 적용됨)

### "report.md가 생성되지 않아요"

**원인**: `allowed_tools`에 `Write`가 없으면 Claude가 파일을 쓸 수 없습니다.

**해결**: config.json에서 `Write` 도구 추가

### "max turns에 도달했어요"

**원인**: 이전 버전에서는 `max_turns: 10` 제한이 있었습니다.

**해결**: 현재 버전에서는 제한이 제거되어 Claude가 필요한 만큼 분석합니다.

### "이미지 분석이 안 돼요"

**해결**: 이미지 경로가 절대 경로로 프롬프트에 포함되어 있는지 확인. Claude의 Read 도구가 이미지를 읽을 수 있습니다.

### "externally-managed-environment 오류 (pip)"

**원인**: Python 3.12+에서 시스템 Python에 직접 설치가 제한됩니다.

**해결**: 가상환경 사용
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 디렉토리 구조

```
jar-decompiler/
├── issuebot/              # Issue Analysis Bot
│   ├── analyze.py         # Claude 이슈 분석
│   ├── fetch.py           # ClickUp 태스크 다운로드
│   ├── scheduler.py       # 자동화 스케줄러 (cron용)
│   └── batch.py           # 일괄 처리
├── decompiler/            # 디컴파일 스크립트
│   ├── decompile.ps1      # Windows
│   └── decompile.sh       # Linux/Mac
├── config/                # 설정 파일
│   ├── config.json        # 설정
│   └── prompts.json       # 분석 템플릿 (한국어)
├── tools/                 # 디컴파일러 도구 (CFR, ILSpy)
├── packages/              # 디컴파일된 패키지들 (gitignore)
│   └── {패키지}/
│       └── decompiled/    # 디컴파일된 소스
├── tasks/                 # 분석 결과 (gitignore)
│   └── {TASK_ID}/
│       ├── task.json      # 태스크 메타데이터
│       ├── images/        # 다운로드된 이미지
│       ├── prompt.txt     # 생성된 프롬프트
│       └── report.md      # 분석 보고서
├── logs/                  # 스케줄러 로그 (gitignore)
├── .env                   # API 키 (gitignore)
├── CLAUDE.md              # Claude Code 지침
├── README.md
└── requirements.txt
```

---

## 주요 특징

- **실시간 분석 로그**: `stream-json` 형식으로 Claude 진행 상황 실시간 표시
- **이미지 분석 지원**: 첨부된 스크린샷을 Claude가 직접 분석
- **버전 자동 매칭**: Custom Fields에서 버전 추출 후 패키지 매칭
- **한국어 분석 보고서**: 프롬프트 및 결과 모두 한국어
- **자동화 스케줄러**: Cron으로 새 이슈 자동 감지 및 분석
- **Claude Code Max Plan**: API 키 불필요 (Max Plan 로그인만 필요)

---

## 라이센스

이 프로젝트는 EXEM, Inc.의 InterMax 지원팀을 위한 내부 도구입니다.
