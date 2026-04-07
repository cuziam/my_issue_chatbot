# Wiki Index

## Symptoms (증상별 패턴)

- [UI 텍스트 겹침/잘림](symptoms/UI-텍스트-겹침.md) — 고정 너비 박스에서 텍스트가 겹치거나 ellipsis로 잘리는 현상
- [무한 로딩](symptoms/무한-로딩.md) — 화면 진입 시 무한 로딩, Scale in/out 환경에서 초기화 타이밍 이슈
- [로그 폭증](symptoms/로그-폭증.md) — 에러 반복으로 로그 용량 급증, 디스크 풀 위험
- [DB CPU 사용률 과다](symptoms/DB-CPU-과부하.md) — 자정 일변경 배치 작업으로 PostgreSQL CPU 급등
- [UI 노드/경로 겹침](symptoms/UI-노드-겹침.md) — 트랜잭션 경로 화면에서 DB 노드 레벨 계산 오류로 노드가 겹쳐 표시
- [지표명 불일치](symptoms/지표명-불일치.md) — .NET 알람 지표명이 JVM 이름으로 표시되는 라벨 불일치 현상
- [SMS 미발송](symptoms/SMS-미발송.md) — 서버 알람 SMS_FLAG=0 저장으로 SMS 연동 미동작
- [알람 연계 실패](symptoms/알람-연계-실패.md) — 대시보드 알람 자동 연계 미동작, CommDash.js 서비스명 설정 오류
- [DB 알람 정보 부족](symptoms/DB-알람-정보-부족.md) — DB 지표 색상 변경 기준 불명확, MFO 알람 상세 확인 불가
- [데이터 중복 삽입](symptoms/데이터-중복-삽입.md) — 패치 후 중복 방지 로직 무효화로 테이블 비대화 및 조회 장애
- [SQL 정렬 실패](symptoms/SQL-정렬-실패.md) — SQL 문 정렬 버튼 클릭 시 벤더 하드코딩/라이브러리 초기화 실패로 포맷팅 불가
- [시간 조건 역전](symptoms/시간-조건-역전.md) — PA DatePicker에서 매시 정각 전후 From>To 시간 역전, 서버 시간 동기화 패치 후 변수 참조 오류
- [위젯 사라짐/깜빡임](symptoms/위젯-사라짐.md) — 통합대시보드 카드 위젯이 연계 서버 불안정 시 사라지는 현상, disable 토글 + 캐시 빈 리스트 전파
- [CPU 수치 비정상](symptoms/CPU-수치-비정상.md) — 연계 제품 CPU 값이 100배 과대 표시, 송수신 단위 변환(스케일링) 누락
- [데이터 미조회](symptoms/데이터-미조회.md) — 삭제/scale-in Agent의 과거 데이터가 INNER JOIN·cascade delete로 조회 누락
- [로그 파일 미생성](symptoms/로그-파일-미생성.md) — logger 레벨 불일치(info→debug)로 로그파일이 자정에 생성되지 않는 현상
- [SQL 수집 설정 미동작](symptoms/SQL-수집-설정-미동작.md) — SQL_DETAIL_ELAPSE_LIMIT 설정이 버전별로 참조 파일이 다르거나, 재기동 시 초기화되는 현상
- [차트 색상 불일치](symptoms/차트-색상-불일치.md) — 스캐터 차트에서 예외 트랜잭션이 정상 색상으로 표시되는 현상 (elapse 부호 기반 판단 오류)
- [연계 타입 불일치](symptoms/연계-타입-불일치.md) — PeakVisor↔InterMax 간 에이전트 타입명(CDM/CD) 불일치로 연계 기능 동작 실패
- [모듈 버전 불일치](symptoms/모듈-버전-불일치.md) — nginx 동적 모듈(.so) 버전 불일치로 기동 실패, patch 버전까지 정확히 매칭 필요
- [EtoE 프레임 오류](symptoms/EtoE-프레임-오류.md) — EtoE 액티브 트랜잭션에서 txnName null/undefined 시 .trim() TypeError로 모니터링 불가
- [Alive/Down 표시 오류](symptoms/Alive-Down-표시-오류.md) — WEB 모니터링 alive/down 표시가 정상 복귀 후에도 갱신되지 않는 현상
- [설정 CRUD 오동작](symptoms/설정-CRUD-오동작.md) — 설정 테이블 유니크 키 변경 후 DTO/WHERE절 미반영으로 추가/삭제 실패·연쇄 수정
- [SQL 데이터 미수집](symptoms/SQL-데이터-미수집.md) — JSPD 업그레이드 후 local.advice 제외 패턴이 SQL/RemoteCall 위빙을 차단하는 현상
- [트리 노드 오배치](symptoms/트리-노드-오배치.md) — 트리 그리드에서 ID 네임스페이스 충돌 + DFS 탐색으로 노드가 잘못된 부모에 배치
- [메모리 누수 / OOM](symptoms/메모리-누수-OOM.md) — HotDeploy 환경에서 JSPD 캐시 Map에 임시 클래스 무한 누적, ConcurrentHashMap remove 부재
- [E2E 데이터 유실 / 화면 멈춤](symptoms/E2E-데이터-유실.md) — 거래량 급증 시 pootprinter TCP 스트림 바이트 정렬 불일치로 E2E 데이터 유실
- [동시사용자 집계 오류](symptoms/동시사용자-집계-오류.md) — JSPD webId 설정(USE_SESSIONID_FOR_WEBID, DISABLE_WEBID)으로 쿠키 기반 집계 미동작
- [위젯 크기 조절 불가](symptoms/위젯-크기-조절-불가.md) — 토폴로지 뷰 등 위젯의 최소 높이가 내부 요소에 의해 강제 고정되어 크기 축소 불가
- [Autowasid 발급 실패](symptoms/Autowasid-발급-실패.md) — autowasid TYPE=3/4 모드 불일치로 wasid=0 발급, 유령 에이전트 생성 및 설정 404 에러
- [알람 타입 오설정](symptoms/알람-타입-오설정.md) — AlertConfig에서 alert_type 하드코딩으로 TP Stat Alert 등이 Stat Alert로 잘못 세팅
- [패치 호환성 오류](symptoms/패치-호환성-오류.md) — 커스텀 ext와 표준 패치(imxtxn) 간 버전 불일치로 세션 인증키 누락 등 서비스 장애
- [알람 소리 오작동](symptoms/알람-소리-오작동.md) — 알람 소리 필터 조건 통과로 의도하지 않은 소리 재생
- [MFO 세션 목록 미표시](symptoms/MFO-세션-목록-미표시.md) — MFO 연동 DB 모니터에서 차트는 정상이나 세션 그리드가 빈 상태
- [X축 시간 표시 불일치](symptoms/X축-시간-표시-불일치.md) — PA 추이분석 화면별 X축 시간 포맷이 통일되지 않은 현상
- [화면 미표출](symptoms/화면-미표출.md) — 패치 빌드 코드 혼입 등으로 JS 에러 발생, 대시보드 화면이 렌더링되지 않는 현상
- [신규 타입 미반영](symptoms/신규-타입-미반영.md) — 새 에이전트 타입 추가 시 기존 UI 분기에서 해당 타입 미처리로 탭/버튼 미동작
- [인코딩 깨짐](symptoms/인코딩-깨짐.md) — FileReader charset 미지정으로 UTF-8 SQL 파일의 한글이 깨져 DB에 저장되는 현상
- [공유 메모리 오류](symptoms/공유-메모리-오류.md) — APIM 에이전트 기동 시 공유 메모리 미생성으로 shopen failed 에러 발생
- [칼럼 공백 표시](symptoms/칼럼-공백-표시.md) — 업무 미등록/삭제 시 히트맵 업무명·거래코드 칼럼이 공백으로 표시
- [알람 파라미터 누락](symptoms/알람-파라미터-누락.md) — SMS adaptor 연계 시 Alert 유형별 SMSData 생성자 분기에서 guid 등 필드 누락
- [패킷 미전송](symptoms/패킷-미전송.md) — txn spec out 모드에서 특정 전송 메소드의 분기 누락으로 패킷이 전송되지 않는 현상
- [에이전트 CPU 과부하](symptoms/에이전트-CPU-과부하.md) — .NET 에이전트 CLR Profiler의 JIT instrumentation으로 대상 프로세스 CPU 200% 상승
- [조회 데이터 중복](symptoms/조회-데이터-중복.md) — 비동기 API 로딩 플래그 조기 해제로 조회 버튼 연속 클릭 시 데이터 2배/N배 표시
- [에이전트 목록 불일치](symptoms/에이전트-목록-불일치.md) — RTM과 PA 에이전트 목록 차이, oldServerInfo 이력 기반 삭제 Agent 포함 (의도된 동작)
- [조회 조건 불일치](symptoms/조회-조건-불일치.md) — 점차트 드래그 시 선택 조건과 조회 결과가 다른 현상, 특수문자 에이전트명 매칭 실패
- [첫 조회 실패](symptoms/첫-조회-실패.md) — AllWasList 비동기 로딩 미완료 상태에서 첫 조회 시 에러, 재조회 시 정상
- [설정 미적용](symptoms/설정-미적용.md) — 설정값의 매칭 규칙(startsWith/endsWith) 오해로 필터/제외 조건이 적용되지 않는 현상
- [클래스 버전 호환성 오류](symptoms/클래스-버전-호환성-오류.md) — JDK 버전 불일치로 클래스 로딩 실패(UnsupportedClassVersionError), ext 기능 미동작

## Components (컴포넌트별 지식)

- [PlatformJS](components/platformjs.md) — 웹 UI/API (Spring 기반, 프론트엔드 + 백엔드)
- [DataGather](components/datagather.md) — 데이터 수집 서버 (DGM/DGS, PostgreSQL/ClickHouse 연동)
- [JSPD](components/jspd.md) — WAS Agent (바이트코드 위빙 기반 트랜잭션 수집)
- [PeakVisor](components/peakvisor.md) — 통합 모니터링 대시보드 (연계 제품 통합 뷰)
- [pootprinter](components/pootprinter.md) — E2E 트랜잭션 집계 프로세스 (Netty TCP 기반 slave DG 연결)
- [.NET Agent](components/dotnet-agent.md) — Windows IIS/.NET 환경 CLR Profiling 기반 트랜잭션 수집 에이전트

## Customers (고객사별 환경)

- [현대차증권](customers/현대차증권.md) — InterMax 5.4, E2E 리뷰 기반 개선 요청
- [아모레퍼시픽](customers/아모레퍼시픽.md) — InterMax 5.3, AWS RDS + Kubernetes/Tanzu 환경
- [한국가스공사](customers/한국가스공사.md) — InterMax 5.2, 장기 운영 환경
- [엔지니어링공제조합](customers/엔지니어링공제조합.md) — InterMax 5.4.7.4, LG CNS 경유 프로젝트
- [하이닉스](customers/하이닉스.md) — InterMax 5.4.9.2, SMS 연동 환경
- [롯데렌탈](customers/롯데렌탈.md) — InterMax 5.3, iframe 통합 대시보드 (5.2→5.3 업그레이드)
- [한국신용정보원](customers/한국신용정보원.md) — InterMax 5.4.12.0, MFO 연계 DB 알람 모니터링
- [유진투자증권](customers/유진투자증권.md) — InterMax 5.3, AIX/PostgreSQL, Tmax TPM 연동
- [HL만도](customers/HL만도.md) — InterMax 5.4.8.2, SQLSERVER 환경
- [KB라이프](customers/KB라이프.md) — InterMax 5.3, Autoscale 환경, 커스텀 패키지(intermax_v53_kblife)
- [울산대학교](customers/울산대학교.md) — InterMax 5.4.11.1, Windows 2016 + .NET Core 10.0 환경
- [한국투자저축은행](customers/한국투자저축은행.md) — InterMax 5.3, 폴스타 연동, smsJar 로그 자정 생성 개선
- [농협경제](customers/농협경제.md) — InterMax 5.3, JEUS 7, 농협 전용 hotfix 버전, SQL 수집 제한 개선
- [신세계포인트](customers/신세계포인트.md) — InterMax 5.2, CentOS 7.9, nginx 1.28.1 + mod_imx WSM 환경
- [K-에듀파인](customers/K-에듀파인.md) — InterMax 5.2, 경기교육청, keris 전용 DataGather
- [현대캐피탈](customers/현대캐피탈.md) — InterMax 5.3, 현대캐피탈 전용 Client 버전(hc)
- [ABL생명](customers/ABL생명.md) — InterMax 5.4.12.0, 5.4.11.1에서 업그레이드, 에이전트 그룹 트리 ID 충돌
- [신한은행](customers/신한은행.md) — InterMax 5.3, E2E 모니터링, pootprinter TCP 스트림 장애
- [한국조폐공사](customers/한국조폐공사.md) — InterMax for Mobile 5.4, mAPM HTTP Call 건수 개선
- [현대백화점](customers/현대백화점.md) — JSPD 24.08, JDK 17 환경, JSPD 업그레이드 후 webId 집계 이슈
- [KICC](customers/KICC.md) — InterMax 5.4, Tmax TPM 환경, imxtpm_info UCS 수동 제어 확인
- [신용보증기금](customers/신용보증기금.md) — InterMax 5.2, CVE 보안취약점 확인 이력
- [우리투자증권](customers/우리투자증권.md) — IMXAPIM-2.4.4, InterMax 5.4.12.0, APIM C 네이티브 에이전트 환경
- [한국예탁결제원](customers/한국예탁결제원.md) — InterMax 5.4.11.1, pac4j-jwt 보안취약점 사양 확인
- [HD현대인프라코어](customers/HD현대인프라코어.md) — InterMax 5.3, Windows IIS, .NET 에이전트 CPU 200% 이슈
- [SSG](customers/SSG.md) — InterMax 5.3, autowasid On-Premise 환경, SMS 매핑 누락 이슈
