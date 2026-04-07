# JSPD

## 역할
WAS 내에서 바이트코드 위빙(weaving)으로 트랜잭션 데이터를 수집하는 Agent. jspd.prop.ini/imx.prop으로 설정하며, imxtxn(C/C++ 네이티브 바이너리)과 연동하여 DataGather로 데이터를 전송한다.

## 분석에서 발견된 주요 사항
| 이슈 | 발견 사항 | 관련 파일 |
|------|----------|----------|
| IMX-9356 | SQL_DETAIL_ELAPSE_LIMIT 설정 로딩 소스가 버전별로 다름: base/hotfix는 `intValueImx()`(imx.prop), 2509.04는 `intValue()`(jspd.prop.ini). Exception SQL 우회 로직(`!bl &&`)이 hotfix에서 sidExecuteAllEnd에 추가됨. fetch 필터에는 미반영(2509.04에만 있음). | udp/d.java:152, XmProperties.java:549, state/a.java:211 |
| IMX-9356 | JEUS 재기동 시 XmProperties static 초기화가 XmConfig.loadProperty()보다 먼저 실행되어 SQL_DETAIL=0(기본값)으로 설정됨. DataGather WAS ID 수신 시 복구되나, 재기동 스크립트가 imx.prop을 덮어쓰면 복구 불가. | XmProperties.java:997, f/d.java:35-43, agent/a.java:50-56 |
| IMX-9452 | IMX-9300 수정으로 `l.a()` 시그니처 변경(4→3파라미터). local.advice 제외 패턴(`-oracle/*`)이 JDBC SQL 위빙까지 차단하게 됨. 이전 버전은 advice map 등록 여부가 우선하여 영향 없었음. | org/bsp/weave/l.java:96-97, org/bsp/weave/i.java:127-133 |
| IMX-9480 | HotDeploy 환경에서 `org.bsp.weave.b.c`의 ConcurrentHashMap에 ByteBuddy auxiliary 클래스가 무한 누적(remove 로직 부재). 4,194,304개 엔트리, Retained 1.5GB(40.3%). `jspd.local.advice` 중간 `*`는 리터럴 처리되어 제외 규칙 무효. | org/bsp/weave/b/c.java:21-29, org/bsp/weave/i.java:144, org/bsp/weave/o.java |
| IMX-9494 | USE_SESSIONID_FOR_WEBID=true 시 세션 기반 webId 생성으로 쿠키 집계 무효화. DISABLE_WEBID 기본값이 true(!)로 명시적 false 설정 필요. JDK 17 모듈 접근 제약으로 com.sun.management.ThreadMXBean 리플렉션 시 IllegalAccessException 발생. | com/exem/jspd/state/b.java:492-537, XmProperties.java:455-458, config/XmConfig.java:611-626 |
| IMX-9504 | imxtxn alive 체크 메커니즘: XmTask(n.java)가 5초 간격으로 imxtxn.alive 파일 lastModified를 모니터링, IMXTXN_CHECK_COUNT(기본3) 카운트다운 후 IMXAgent.sh로 재기동. imxtpm_info UCS와 imxtxn은 독립 프로세스로, UCS 수동 중지/재기동은 안전함. | com/exem/jspd/agent/n.java:178-191, com/exem/jspd/agent/a.java |
| IMX-9508 | TYPE_AUTOMATIC_WASID 설정(1~4)에 따라 autowasid 요청 패킷(10032) 전송. TYPE=3은 hostname+uniqueName hash, TYPE=4는 service/group/name 등 8~9개 필드 포함. DG에서 TYPE=4만 처리하므로 TYPE=3 사용 시 wasid=0 유지, 5초마다 재요청 무한 반복. | com/exem/jspd/g/am.java, com/exem/jspd/y.java:402-422 |
| IMX-9512 | 농협 커스텀 ext(21.12.01.14.hotfix.nh 기반)와 imxtxn 2509.04 간 호환성 불일치로 세션 인증키 누락. TxnCallbackBase.getLoginName() 콜백 경로에서 ext가 기대하는 API와 2509.04 API 불일치 추정. 표준 JSPD 코드(2509.03↔2509.04)에는 세션 처리 변경 없음. | config/a.java:100, state/c.java:494, XmProperties.java:318-321 |
| IMX-9534 | ext jar 환경에서 XM_BOUND_EJB 클래스 로딩 시 `a(ClassLoader, String)` 메서드의 `findClass()` 실패 → catch 블록에서 Throwable 인자 포함 XmLog.print 호출로 ERROR 레벨 로깅. 패키지에 EJB 클래스 미포함이나 코드에서 하드코딩 로딩 시도. 매 touch(3초 주기)마다 반복. | com/exem/jspd/e/a.java:128-142, XmLog.java:554-558 |
| IMX-9537 | PROTOCOL_VERSION 40→41 업그레이드. 가변 필러 인코딩 방식 변경: v40(순서 기반, null은 0x00) → v41(1-based 인덱스+값 쌍, null skip sparse 인코딩). VARIABLE_FILLER_MAX_COUNT(숨겨진 옵션, 기본10, 최대255)로 필러 수 제어. DataGather 측에서 index < 100은 검색용 EXT_FIELD, ≥100은 분류용 variable_fillers로 분기. | com/exem/jspd/state/c.java:662-676, XmVersion.java:9,11 |
| IMX-9604 | `xHeaderInfoSecure()`에 `SEND_TXN_DATA_DIRECTLY` 분기 누락. txn spec out 모드에서 UDP 큐가 비활성화되어 `this.new()`가 false 반환 → 암호화 패킷 조기 리턴. 250905.dev.1에서 공통 private 헬퍼로 리팩토링하여 수정. | com/exem/jspd/udp/e.java:280-348 |
| IMX-9675 | EXCLUDE_SERVICE 매칭 로직: `/`로 시작하면 startsWith, 아니면 endsWith. contains(부분 문자열) 매칭은 미지원 (정상 동작). 전 버전(2105.17~2509.06) 동일 로직. EXCLUDE_SERVICE_AT_END_TIME도 동일. | XmProperties.java:1146-1157, XmThread.java:425,437 |
| IMX-9689 | jspd.jar 내장 ext 클래스(XM_RT, XM_BOUND_HTTP 등)가 JDK 1.7+로 컴파일되어 IBM JDK 1.6 런타임에서 UnsupportedClassVersionError 발생. ext 로딩 순서: jspd-ext*.jar 우선 → 없으면 built-in 사용. build-ext의 JAVA_VERSION 미설정으로 현장 빌드 시에도 버전 주의 필요. | com/exem/jspd/e/a.java:104-209, build-ext/build.xml |
| IMX-9652 | 바이트코드 위빙으로 메서드 정보 수집 시 class_name(256 bytes)에 return type이 포함된 전체 메서드 시그니처가 들어감. return type 포함/제외를 제어하는 설정(jspd.prop.ini 등)은 없음. IMX-4179에서 리턴타입 표시 요청으로 패치됨. | class_name 필드 (256 bytes) |

## 자주 관련되는 증상
- [데이터 수집 오류](../symptoms/데이터-수집-오류.md)
- [성능/리소스 이상](../symptoms/성능-리소스-이상.md)
- [에이전트 연결 문제](../symptoms/에이전트-연결-문제.md)
- [호환성/버전 오류](../symptoms/호환성-버전-오류.md)
- [설정 적용 실패](../symptoms/설정-적용-실패.md)
- [지표/수치 불일치](../symptoms/지표-수치-불일치.md)
