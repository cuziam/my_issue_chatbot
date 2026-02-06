# InterMax JAR-Decompiler & ClickUp Issue Analysis Bot

InterMax 패키지(Java JAR, .NET DLL)를 디컴파일하고, ClickUp 이슈를 Claude Code Agent Teams로 심층 분석하는 통합 도구입니다.

---

## 목차

1. [기능 소개](#기능-소개)
2. [아키텍처](#아키텍처)
3. [사전 준비](#사전-준비)
4. [환경 설정](#환경-설정)
5. [디컴파일 사용법](#디컴파일-사용법)
6. [이슈 분석 사용법](#이슈-분석-사용법)
7. [자동화 (Scheduler)](#자동화-scheduler)
8. [트러블슈팅](#트러블슈팅)

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
- **3가지 태스크 유형 지원**: 이슈 분석, 사양 문의, 개선 검증
- 버전 정보 기반 소스코드 자동 매칭
- **팔로업 분석**: context.md 기반 후속 질문 처리 (크로스 세션 지원)
- **Cron 기반 자동 fetch 스케줄러**

---

## 아키텍처

```
[자동 수집] cron → scheduler.py → fetch.py (새 task 가져오기 + ZIP 자동 해제)
                                    ↓
                              tasks/{ID}/task.json 저장
                              tasks/{ID}/images/ (이미지 + 아카이브 해제)

[수동 분석] 사용자 → Claude Code → "IMX-9355 분석해줘"
                                    ↓
                              Agent Teams로 심층 분석
                              ┌─────────────────────────────────┐
                              │  Team Lead (조율만)              │
                              │    ├── researcher → analyzer     │
                              │    │   (탐색)     (분석+보고서)  │
                              │    │   직접 소통 (peer-to-peer)  │
                              │    └── analyzer → report.md 작성 │
                              └─────────────────────────────────┘
                                    ↓
                              tasks/{ID}/report.md 생성
                              tasks/{ID}/context.md 생성

[팔로업]   사용자 → "IMX-9355 팔로업: 추가 질문..."
                                    ↓
                              followup agent (context.md 기반)
                                    ↓
                              report.md에 추가 분석 append
                              context.md 업데이트
```

### 핵심 구성 요소

| 파일 | 역할 |
|------|------|
| `issuebot/fetch.py` | ClickUp API에서 태스크 다운로드 + ZIP 자동 해제 |
| `issuebot/scheduler.py` | fetch 자동화 스케줄러 (cron용) |
| `.claude/agents/issue-researcher.md` | 코드베이스 탐색 agent 정의 |
| `.claude/agents/issue-analyzer.md` | 분석 + report.md/context.md 작성 agent 정의 |
| `.claude/agents/issue-followup.md` | 팔로업 질문 처리 agent 정의 |
| `config/config.json` | ClickUp 및 스케줄러 설정 |
| `config/prompts.json` | 분석 템플릿 (참조용) |

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
  "scheduler": {
    "list_id": "YOUR_LIST_ID",
    "filter_status": "open"
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

**fetch.py 주요 기능:**
- 이미지 첨부파일 자동 다운로드
- **ZIP 아카이브 자동 해제**: 로그 파일, 설정 파일 등을 자동 추출
- 첨부파일 메타데이터 저장: `original_name`, `type`, `extracted_dir`, `extracted_files`

**fetch.py 옵션:**
| 옵션 | 설명 |
|------|------|
| `--task-id` | 특정 태스크 ID (IMX-9326 또는 숫자 ID) |
| `--list-id` | 리스트 ID (여러 태스크 다운로드) |
| `--status` | 상태 필터 (open, in progress 등) |
| `--tags` | 태그 필터 (콤마 구분) |
| `--new-only` | 이미 다운로드된 태스크 스킵 |

### 2. Agent Teams로 심층 분석

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

**분석 과정:**
```
1. Team Lead가 tasks/{ID}/task.json을 읽고 태스크 유형 판별
2. researcher가 코드베이스에서 관련 파일 탐색 → analyzer에게 직접 전달
3. analyzer가 분석 후 report.md + context.md 직접 작성
4. Team Lead가 결과 확인 후 팀 정리
```

**태스크 유형:**
| 유형 | 키워드 | 핵심 질문 |
|------|--------|----------|
| 이슈 분석 | "안 됨", "오류", "에러" | 뭐가 안 되나? 왜? |
| 사양 문의 | "가능한지", "사양", "확인" | 이 기능이 있나? 어떻게 쓰나? |
| 개선 검증 | "개선", "추가", "변경" | 개선이 제대로 됐나? |

### 3. 팔로업 분석

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

### 4. 결과 확인

```bash
# 분석 보고서 확인
cat tasks/IMX-9326/report.md

# 분석 컨텍스트 확인 (팔로업용)
cat tasks/IMX-9326/context.md
```

---

## 자동화 (Scheduler)

### scheduler.py 사용법

새 태스크를 자동으로 가져오는 스케줄러입니다 (fetch만 수행).

```bash
# 기본 사용
python issuebot/scheduler.py --list-id 901234567

# 상태 필터 지정
python issuebot/scheduler.py --list-id 901234567 --status open

# 미리보기 (실제 실행 없음)
python issuebot/scheduler.py --list-id 901234567 --dry-run
```

**scheduler.py 옵션:**
| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--list-id` | ClickUp 리스트 ID (필수) | config.json |
| `--status` | 필터링할 상태 | open |
| `--dry-run` | 실제 실행 없이 미리보기 | false |

### Cron 설정

```bash
# crontab 편집
crontab -e

# 매 시간 정각에 fetch 실행
0 * * * * cd /mnt/d/jar-decompiler && /path/to/venv/bin/python issuebot/scheduler.py >> logs/scheduler.log 2>&1
```

> **참고**: scheduler는 fetch만 담당합니다. 분석은 Claude Code 인터랙티브 세션에서 Agent Teams로 수동 실행합니다.

---

## 트러블슈팅

### "report.md가 생성되지 않아요"

**원인**: Agent Teams 분석이 실행되지 않았습니다.

**해결**: Claude Code를 실행하고 `"IMX-XXXX를 agent team으로 분석해줘"` 라고 요청하세요.

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

## 디렉토리 구조

```
jar-decompiler/
├── .claude/agents/          # Agent Teams 정의
│   ├── issue-researcher.md    # 코드베이스 탐색 agent
│   ├── issue-analyzer.md      # 분석 + 보고서 작성 agent
│   └── issue-followup.md      # 팔로업 분석 agent
├── issuebot/                # Issue Analysis Bot
│   ├── fetch.py               # ClickUp 태스크 다운로드 + ZIP 해제
│   └── scheduler.py           # fetch 자동화 스케줄러 (cron용)
├── decompiler/              # 디컴파일 스크립트
│   ├── decompile.ps1          # Windows
│   └── decompile.sh           # Linux/Mac
├── config/                  # 설정 파일
│   ├── config.json            # 설정
│   └── prompts.json           # 분석 템플릿 (참조용)
├── tools/                   # 디컴파일러 도구 (CFR, ILSpy)
├── packages/                # 디컴파일된 패키지들 (gitignore)
│   └── {패키지}/
│       └── decompiled/        # 디컴파일된 소스
├── tasks/                   # 분석 결과 (gitignore)
│   └── {TASK_ID}/
│       ├── task.json          # 태스크 메타데이터 (첨부파일 메타 포함)
│       ├── images/            # 첨부파일 (이미지 + 아카이브 해제)
│       ├── report.md          # 분석 보고서 (추가 분석 누적)
│       └── context.md         # 분석 컨텍스트 (팔로업용)
├── logs/                    # 스케줄러 로그 (gitignore)
├── .env                     # API 키 (gitignore)
├── CLAUDE.md                # Claude Code 지침
├── README.md
└── requirements.txt
```

---

## 주요 특징

- **Agent Teams 심층 분석**: researcher + analyzer 2인 협업, direct communication으로 병목 제거
- **3가지 태스크 유형**: 이슈 분석, 사양 문의, 개선 검증 각각 맞춤 보고서
- **ZIP 첨부파일 자동 해제**: 로그, 설정 파일 등 아카이브를 자동 추출하여 분석에 활용
- **팔로업 분석**: context.md 기반으로 후속 질문 처리 (크로스 세션 지원)
- **이미지 분석 지원**: 첨부된 스크린샷을 Claude가 직접 분석
- **버전 자동 매칭**: Custom Fields에서 버전 추출 후 패키지 매칭
- **한국어 분석 보고서**: 보고서 대상 = QA/현장 엔지니어 (코드 분석은 참고 섹션으로 분리)
- **자동 fetch 스케줄러**: Cron으로 새 이슈 자동 감지
- **Claude Code Max Plan**: API 키 불필요 (Max Plan 로그인만 필요)

---

## 라이센스

이 프로젝트는 EXEM, Inc.의 InterMax 지원팀을 위한 내부 도구입니다.
