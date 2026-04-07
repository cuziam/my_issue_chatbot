# Wiki Index

## Symptoms (증상별 패턴)

- [UI 렌더링 오류](symptoms/UI-렌더링-오류.md) — 텍스트 겹침/잘림, 노드 겹침, 화면 미표출, 위젯 사라짐, 차트 색상 불일치, 칼럼 공백, 트리 오배치 등 UI 표시 관련 전반
- [데이터 조회 이상](symptoms/데이터-조회-이상.md) — 데이터 미조회(JOIN/필터 불일치), 조회 데이터 중복, 조회 조건 불일치, 첫 조회 실패
- [데이터 수집 오류](symptoms/데이터-수집-오류.md) — SQL 미수집, 수집 설정 미동작, SQL 정렬 실패, E2E 데이터 유실, 패킷 미전송, 데이터 중복 삽입
- [설정 적용 실패](symptoms/설정-적용-실패.md) — 설정 CRUD 오동작, 설정 미적용, 신규 타입 미반영, 연계 타입 불일치
- [알람/알림 오류](symptoms/알람-알림-오류.md) — SMS 미발송, 알람 연계 실패, 알람 소리 오작동, 알람 타입 오설정, 파라미터 누락, DB 알람 정보 부족
- [성능/리소스 이상](symptoms/성능-리소스-이상.md) — DB/에이전트 CPU 과부하, 메모리 누수/OOM, 로그 폭증, 로그 파일 미생성, 무한 로딩
- [에이전트 연결 문제](symptoms/에이전트-연결-문제.md) — Alive/Down 표시 오류, 에이전트 목록 불일치, Autowasid 발급 실패, 공유 메모리 오류, EtoE 프레임 오류, MFO 세션 미표시
- [호환성/버전 오류](symptoms/호환성-버전-오류.md) — 패치 호환성 오류, 클래스 버전 호환성, 모듈 버전 불일치, 인코딩 깨짐
- [지표/수치 불일치](symptoms/지표-수치-불일치.md) — CPU 수치 비정상, 동시사용자 집계 오류, 지표명 불일치, 시간 조건 역전

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
