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
  ├── issuebot/                           # 분석 봇 코드
  │   ├── analyze.py                      # 분석 실행
  │   ├── fetch.py                        # ClickUp 다운로드
  │   └── scheduler.py                    # 자동화 스케줄러
  │
  └── config/
      ├── config.json                     # 설정
      └── prompts.json                    # 분석 템플릿

  ---

  ## 4. 이슈 분석 가이드

  ### 4.1 분석 전략 (필수)

  **중요**: 이슈 분석 시 반드시 Task tool을 활용하여 subagent에게 탐색/분석을 위임하세요.
  이를 통해 더 깊고 체계적인 분석이 가능합니다.

  권장 분석 흐름:
  1. Task tool (Explore agent) → 코드베이스 전체 탐색
  2. Task tool (분석 agent) → 심층 분석 및 근본 원인 파악
  3. 보고서 작성 → 발견 사항 종합

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

  ### 필수 항목
  - [ ] 이슈 재현 단계가 구체적으로 작성되었는가?
  - [ ] 근본 원인이 코드 레벨에서 설명되었는가?
  - [ ] 관련 파일 경로와 라인 번호가 명시되었는가?
  - [ ] 해결 방안이 구체적으로 제시되었는가?

  ### 권장 항목
  - [ ] 여러 버전의 코드를 비교 분석했는가?
  - [ ] 유사 기능/이슈와의 연관성을 확인했는가?
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

  ```markdown
  ### 버전 정보
  - Agent Version: x.x.x
  - DataGather Version: x.x.x
  - PlatformJS Version: x.x.x

  ### 이슈 요약
  (2-3문장으로 핵심 문제 설명)

  ### 재현 단계
  1. (구체적인 단계)
  2. (구체적인 단계)
  3. (구체적인 단계)

  ### 근본 원인 분석
  - **관련 파일**: `path/to/file.java:123`
  - **원인**: (코드 레벨 설명)
  - **증거**: (코드 스니펫 또는 로직 설명)

  ### 해결 방안
  - **접근법**: (해결 전략)
  - **구현 방안**: (구체적인 코드 수정 제안)
  - **영향 범위**: (다른 기능에 미치는 영향)

  ---
  8. 주의사항

  1. 파일 수 제한 없음: 필요한 만큼 자유롭게 파일을 탐색하고 분석하세요.
  2. subagent 활용: 복잡한 분석은 Task tool로 subagent에게 위임하세요.
  3. 이미지 분석: 첨부된 스크린샷은 Read 도구로 직접 분석 가능합니다.
  4. 버전 주의: Custom Fields의 버전 정보와 패키지 버전을 정확히 매칭하세요.

  ---