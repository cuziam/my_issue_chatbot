# InterMax Issue Analysis Bot
                                                                                                                                                                                  이 프로젝트는 ClickUp에서 가져온 InterMax 지원 이슈를 Claude AI로 자동 분석합니다.
                                                                                                                                                                                  ---                                                   
                                                                                                                                                                                
  ## 1. InterMax 시스템 개요

  InterMax는 **EXEM**에서 개발한 **APM(Application Performance Management)** 솔루션입니다.
  Java/WAS 애플리케이션의 성능을 모니터링하고 분석하는 엔터프라이즈 소프트웨어입니다.

  ### 주요 기능
  - 트랜잭션 추적 및 분석
  - 실시간 성능 모니터링
  - 에러/예외 수집 및 분석
  - WAS 인스턴스 모니터링
  - 사용자 정의 대시보드

  ---

  ## 2. 핵심 컴포넌트 아키텍처

  ┌─────────────────────────────────────────────────────────────────┐
  │                      InterMax 아키텍처                           │
  ├─────────────────────────────────────────────────────────────────┤
  │                                                                  │
  │   ┌─────────┐     ┌─────────────┐     ┌─────────────┐          │
  │   │  JSPD   │────▶│  DataGather │────▶│   Ingester  │          │
  │   │ (Agent) │     │   (수집기)   │     │ (ClickHouse)│          │
  │   └─────────┘     └─────────────┘     └─────────────┘          │
  │        │                                     │                  │
  │        │                                     ▼                  │
  │        └─────────▶┌─────────────────────────────────┐          │
  │                   │         PlatformJS              │          │
  │                   │        (웹 UI/API)              │          │
  │                   └─────────────────────────────────┘          │
  │                                                                  │
  └─────────────────────────────────────────────────────────────────┘

  ### 2.1 JSPD (Java Service Platform Daemon)

  **역할**: WAS 내에서 바이트코드 위빙(weaving)으로 트랜잭션 데이터 수집

  **소스 위치**: `packages/*/InterMax*/decompiled/jspd/`

  **주요 패키지**:
  - `com.exem.jspd` - 핵심 Agent 로직
  - `org.bsp` - 바이트코드 처리
  - `org.a` - 유틸리티

  **분석 시 주요 클래스**:
  - `*Agent*.java` - Agent 초기화 및 설정
  - `*Weaver*.java` - 바이트코드 위빙 로직
  - `*Config*.java` - 설정 관리
  - `*Collector*.java` - 데이터 수집

  ### 2.2 DataGather (데이터 수집 서버)

  **역할**: Agent에서 수집된 데이터를 집계하고 처리

  **소스 위치**: `packages/*/InterMax*/decompiled/datagather/`

  **주요 패키지**:
  - `jdg.dgs` - DataGather 서버 핵심
  - `jdg.server` - 서버 통신
  - `jdg.clickhouse` - ClickHouse 연동
  - `jdg.vo` - Value Objects
  - `com.exem` - 공통 유틸리티

  **분석 시 주요 클래스**:
  - `*Server*.java` - 서버 로직
  - `*Handler*.java` - 데이터 핸들링
  - `*Manager*.java` - 리소스 관리
  - `*Queue*.java` - 데이터 큐잉

  ### 2.3 PlatformJS (웹 UI/API)

  **역할**: 사용자 인터페이스 및 REST API 제공 (Spring 기반)

  **소스 위치**: `packages/*/InterMax*/decompiled/PlatformJS/`

  **주요 패키지**:
  - `com.exem.platform` - 플랫폼 핵심
  - `com.exem.intermax` - InterMax 특화 기능
  - `org.springframework` - Spring 프레임워크

  **분석 시 주요 클래스**:
  - `*Controller*.java` - REST API 엔드포인트
  - `*Service*.java` - 비즈니스 로직
  - `*Repository*.java` - 데이터 접근
  - `*Config*.java` - 설정

  ### 2.4 기타 컴포넌트

  | 컴포넌트 | 역할 | 소스 위치 |
  |---------|------|-----------|
  | Ingester | ClickHouse로 데이터 저장 | `ingester/` |
  | Pootprinter | 로그 수집 | `pootprinter/` |
  | Observer | 시스템 모니터링 | `observer/` |

  ---

  ## 3. 디렉토리 구조

  jar-decompiler/
  ├── packages/                           # 디컴파일된 InterMax 소스
  │   ├── package_v5.4.12.0-alpha.2/
  │   │   └── InterMax5.4/
  │   │       ├── decompiled/             # 디컴파일된 Java 소스
  │   │       │   ├── datagather/         # DataGather 컴포넌트
  │   │       │   ├── jspd/               # Agent 컴포넌트
  │   │       │   └── PlatformJS/         # 웹 UI 컴포넌트
  │   │       ├── jspd/                   # Agent 원본 JAR
  │   │       ├── DGServer_M/             # DataGather 마스터
  │   │       ├── DGServer_S1/            # DataGather 슬레이브
  │   │       ├── PlatformJS/             # 웹 서버 원본
  │   │       └── ingester/               # Ingester 원본
  │   └── intermax_v53_kblife/            # 고객사 커스텀 버전
  │
  ├── tasks/                              # ClickUp 이슈 데이터
  │   └── {TASK_ID}/
  │       ├── task.json                   # 이슈 메타데이터
  │       ├── images/                     # 첨부 이미지
  │       └── report.md                   # 분석 결과
  │
  ├── .claude/agents/                     # Agent Teams 정의
  │   ├── issue-researcher.md             # 코드베이스 탐색 agent
  │   ├── issue-analyzer.md               # 근본 원인 분석 agent
  │   └── issue-reporter.md               # 보고서 작성 agent
  │
  ├── issuebot/                           # 분석 봇 코드
  │   ├── fetch.py                        # ClickUp 다운로드
  │   └── scheduler.py                    # fetch 자동화 스케줄러
  │
  └── config/
      ├── config.json                     # 설정
      └── prompts.json                    # 분석 템플릿

  ---

  ## 4. 이슈 분석 가이드

  ### 4.1 분석 전략 (필수)

  **중요**: 이슈 분석 시 Agent Teams를 활용하세요.
  researcher → analyzer → reporter 순서로 협업하여 심층 분석합니다.

  권장 분석 흐름:
  1. issue-researcher agent → 코드베이스 전체 탐색, 관련 파일 식별
  2. issue-analyzer agent → 심층 분석 및 근본 원인 파악
  3. issue-reporter agent → 보고서 작성 (report.md)

  ### 4.2 이슈 유형별 분석 진입점

  #### UI/화면 관련 이슈
  1. 이슈 설명에서 화면명, 버튼명, 메뉴명 추출
  2. PlatformJS에서 검색:
    - Glob: packages//PlatformJS//*.java
    - Grep: 화면명, 버튼명으로 검색
  3. Controller → Service → Repository 흐름 추적

  #### Agent/JSPD 관련 이슈
  1. 이슈 설명에서 에이전트명, 설정명, 에러 메시지 추출
  2. jspd에서 검색:
    - Glob: packages//jspd//*.java
    - Grep: Agent, Config, Weaver 관련 클래스
  3. 설정 파일 (*.conf, *.properties) 확인

  #### 데이터 수집/처리 이슈
  1. 이슈 설명에서 메트릭명, 수집 항목, 에러 메시지 추출
  2. datagather에서 검색:
    - Glob: packages//datagather//*.java
    - Grep: Collector, Handler, Queue 관련 클래스
  3. jdg.dgs, jdg.server 패키지 집중 분석

  #### 성능/응답 지연 이슈
  1. 이슈 설명에서 지연 발생 구간, 조건 추출
  2. 전체 컴포넌트에서 검색:
    - Thread, Lock, Sync 관련 코드
    - Queue, Buffer 관련 코드
  3. 데이터 흐름 전체 추적 (Agent → DataGather → Ingester)

  ### 4.3 공통 이슈 패턴

  | 증상 | 가능한 원인 | 확인 포인트 |
  |------|------------|------------|
  | "설정이 적용 안 됨" | Config 로딩 순서, 캐싱 | *Config*.java, reload 로직 |
  | "데이터가 안 나옴" | 수집 필터, 전송 실패 | Collector, Filter, Queue |
  | "화면 오류" | API 응답 파싱, 권한 | Controller, Service |
  | "에이전트 연결 실패" | 네트워크, 설정 불일치 | Agent, Connection |
  | "메모리 누수" | 리소스 미해제, 캐시 | close(), clear(), pool |

  ---

  ## 5. 분석 품질 체크리스트

  분석 완료 전 다음 항목을 확인하세요:

  ### 필수 항목 (사용자/QA 관점)
  - [ ] 사용자 관점의 재현 시나리오가 UI 조작 기준으로 작성되었는가?
  - [ ] 현재 동작 vs 예상 정상 동작이 명확히 구분되었는가?
  - [ ] QA 검증 방법이 구체적으로 제시되었는가?
  - [ ] 사전 조건(환경/설정/데이터)이 명시되었는가?

  ### 권장 항목 (개발자 참고)
  - [ ] 근본 원인이 코드 레벨에서 설명되었는가?
  - [ ] 관련 파일 경로와 라인 번호가 명시되었는가?
  - [ ] 여러 버전의 코드를 비교 분석했는가?
  - [ ] 영향 범위(side effect)를 분석했는가?

  ---

  ## 6. 버전 정보

  분석 시 버전 정보에 주의하세요:

  | 필드 | 의미 | 패키지 매핑 |
  |------|------|------------|
  | Agent Version | JSPD 버전 | jspd/ |
  | DataGather Version | 수집 서버 버전 | datagather/ |
  | PlatformJS Version | 웹 UI 버전 | PlatformJS/ |
  | Ingester Version | DB 저장 버전 | ingester/ |
  | Client Version | 클라이언트 버전 | - |

  **버전 매칭 예시**:
  - `Agent Version: 5.4.12.0` → `packages/package_v5.4.12.*/InterMax*/decompiled/jspd/`

  ---

  ## 7. 분석 보고서 형식

  **대상 독자**: QA 엔지니어, 현장 설치 엔지니어, 제품 사용자 (개발자가 아님)
  **원칙**: 사용자 관점 재현 시나리오 > 코드 레벨 분석

  ```markdown
  ### 버전 정보
  - Agent Version: x.x.x
  - DataGather Version: x.x.x
  - PlatformJS Version: x.x.x

  ### 이슈 요약
  (사용자가 겪는 문제를 2-3문장으로 설명)

  ### 재현 시나리오
  **사전 조건**: (필요한 환경/설정/데이터)

  1. InterMax 웹 UI에서 [메뉴명]을 클릭한다
  2. [화면명]에서 [요소]를 [동작]한다
  3. **현재 동작**: [실제로 일어나는 것]
  4. **예상 동작**: [정상이라면 이렇게 되어야 함]

  ### QA 검증 방법
  수정 후 다음을 확인:
  1. [확인 항목과 예상 결과]
  2. [확인 항목과 예상 결과]

  ### 참고: 코드 레벨 원인 (개발자용)
  - **관련 파일**: `path/to/file.java:123`
  - **원인**: (코드 레벨 설명)
  - **수정 방안**: (구체적인 코드 수정 제안)
  - **영향 범위**: (다른 기능에 미치는 영향)

  ---

  ## 8. Agent Teams 이슈 분석

  이슈 분석은 **Agent Teams**를 통해 수행됩니다. researcher(탐색) + analyzer(분석) 2명이 협업하고, team-lead가 보고서를 작성합니다.

  ### 분석 흐름
  ```
  사용자 → Claude Code → "IMX-9355 분석해줘"
              → Team Lead가 task.json/이미지 읽기
              → researcher 스폰 (병렬 가능) → 코드베이스 탐색, 파일 목록 제공
              → analyzer 스폰 → 사용자 관점 재현 시나리오 + 근본 원인 분석
              → Team Lead가 report.md 작성
  ```

  ### Agent 구성

  | Agent | 역할 | 도구 |
  |-------|------|------|
  | `issue-researcher` | 코드베이스 탐색, 파일 위치 식별 (분석하지 않음) | Read, Glob, Grep |
  | `issue-analyzer` | 사용자 관점 재현 시나리오 + 코드 레벨 원인 분석 | Read, Glob, Grep, Bash |
  | Team Lead | 이슈 파악, agent 조율, 보고서 작성 | 전체 |

  ### 병렬 탐색
  이슈가 여러 컴포넌트에 걸쳐 있을 경우, researcher를 영역별로 병렬 스폰 가능:
  ```
  researcher-frontend → PlatformJS 프론트 탐색
  researcher-backend  → PlatformJS 백엔드/API 탐색
  researcher-agent    → JSPD/DataGather 탐색
  ```

  ### 사용법

  #### 단일 이슈 심층 분석
  ```
  "IMX-9355를 agent team으로 분석해줘"
  ```

  #### 미분석 이슈 확인
  ```
  "분석 안 된 이슈 목록 보여줘"
  ```
  → tasks/ 디렉토리에서 report.md 없는 task 목록 표시

  ### 자동화 (fetch만)
  ```
  cron → scheduler.py → fetch.py (새 task 가져오기만)
                          ↓
                    tasks/{ID}/task.json 저장
  ```
  > scheduler.py는 fetch만 담당. 분석은 Claude Code에서 Agent Teams로 수동 실행합니다.

  ---

  ## 9. 주의사항

  1. 파일 수 제한 없음: 필요한 만큼 자유롭게 파일을 탐색하고 분석하세요.
  2. Agent Teams 활용: 이슈 분석은 issue-researcher(탐색) + issue-analyzer(분석) agent team으로 수행하세요. 보고서는 team-lead가 직접 작성합니다.
  3. 이미지 분석: 첨부된 스크린샷은 Read 도구로 직접 분석 가능합니다.
  4. 버전 주의: Custom Fields의 버전 정보와 패키지 버전을 정확히 매칭하세요.

  ---