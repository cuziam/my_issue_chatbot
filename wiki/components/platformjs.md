# PlatformJS

## 역할
InterMax의 웹 UI 및 REST API를 제공하는 Spring 기반 컴포넌트. 프론트엔드(intermax/)와 백엔드(com.exem.platform/)로 구성.

## 분석에서 발견된 주요 사항
| 이슈 | 발견 사항 | 관련 파일 |
|------|----------|----------|
| IMX-9291 | 트랜잭션 경로 박스의 고정 너비 + absolute 포지셔닝으로 텍스트 겹침. 배경 이미지(PNG) 기반 디자인이 크기 조정 제약. | txndetail.css:255-265, XMTransactionPath.js:1484-1491, XMEtoETransactionPath.js:1441-1448 |
| IMX-8586 | Scale in/out 시 Comm.serviceid 미초기화 상태에서 autoScale 호출, .join() TypeError로 RTM 무한 로딩 | ServerScale.js:62, IMXWSWorker.js:1688-1725 |
| IMX-8586 | DBStatus 테이블 db_ip varchar(50)이 AWS RDS 엔드포인트를 수용 못해 에러 로그 대량 발생 | DBStatus.java:30 |
| IMX-9380 | 트랜잭션 경로 DB 노드 레벨 계산 시 직접 호출 WAS만 고려 → 같은 레벨에 DB 노드 밀집·겹침. 패치로 상위 WAS 고려하도록 개선. | XMTransactionPath.js:337-372 (getBoxLevel), :1291-1545 (createDesign) |
| IMX-7631 | .NET 알람 설정 UI에서 JVM→.NET 변환은 완료(jvmStatTransObj). 알람 발생 내역 등 5개 화면에서 DB 값(JVM 이름) 그대로 표시하여 .NET 변환 미구현. | AlertHistory.js:1442, rtmAlertInfo.js:355, rtmAlertLight.js:603, config_alarmMemoHistory.js:235, config_alarmStopHistory.js:286 |
| IMX-8895 | 알람 그룹 서버 알람 설정 API 및 UI (v5.4.12+에서 추가). AdmAlarmController에 alertGroups/{id}/serverAlerts REST API, 프론트에 config_agentAlertGroupTab.js/config_sideSheetServerAlert.js 추가. | AdmAlarmController.java, AdmAlarmService.java, config_agentAlertGroupTab.js, config_sideSheetServerAlert.js |
| IMX-8931 | iframe 대시보드 업그레이드(5.2→5.3) 시 CommDash.js 서비스명 오기입으로 알람 자동 연계 실패. rtmAlertLight.js 컬럼 구조 5.2→5.3 변경(15개+ 컬럼, Tier Name/Unit 추가). | CommDash.js (svcName/svcId), rtmAlertLight.js, rtmCommon.js |
| IMX-8945 | DB 알람 색상 기준 도움말 팝업(rtmDatabase.js) + 마우스오버 알람 목록 툴팁(rtmDatabaseChart.js) 구현. MFO WebSocket → ThreadMap 캐싱 → linkAlarm API 서빙 구조. | rtmDatabase.js:144-163,578-613, rtmDatabaseChart.js:523-634, CommonStatController.java:631-640 |
| IMX-9227 | PA 에이전트 선택 팝업에 "그룹 관점" 라디오 버튼 추가. getTreeDataForGroupOnly()로 그룹/서브그룹만 표시, agentIds 배열 기반 일괄 선택. alpha.4에서 구현, alpha.6에서 isGroupOnlyHidden 미정의 TypeError 발생 후 수정. | wasDBTreeComboForPa.js:101-131,1202-1479,366-477 |
| IMX-9235 | SQL 문 정렬 시 Oracle 벤더 하드코딩으로 SQLSERVER 쿼리 파싱 실패. gudusoft gsqlparser static initializer 실패 시 JVM 재시작 전까지 전체 SQL 포맷팅 불가. 프론트엔드에서 result 미검사로 SQL 텍스트 사라짐. v5.4.12.0에서 다중 벤더 순회 로직으로 수정됨. | SqlFormat.java:28, SQLSyntax.java:98, SQLEditorBaseFrame.js:236-250 |
| IMX-9236 | PA DatePicker 서버 시간 동기화 패치에서 toHour를 tDate 대신 fDate에서 참조하여 매시 정각~+N분에 From>To 시간 역전 발생. timeGapMin(10/20/360)에 따라 역전 발생 범위가 달라짐. | DatePickerForPa.js:945, DatePicker.js:943, RTMDataManager.js:136-138 |
| IMX-9302 | 커넥션 풀 조회 SQL에서 xapm_was_info INNER JOIN으로 삭제 Agent 데이터 누락. DB function이 xapm_connection_pool 메타도 cascade 삭제. v5.4에서 LEFT JOIN + ServerNameCacheStore 캐시 조회로 수정(IMX-9334). | IMXPA_All_WasTrend_PoolStat.sql:8-16, PerformanceTrendService.java:53-54, ServerNameCacheStore.java:32-34 |
| IMX-9317 | 토폴로지뷰 그룹명 줄바꿈 기준(maxWidth) 150px→300px 확대. 노드명 편집 클릭 판정 기준도 120→150으로 조정. | topology.js:3108, topology.js:5341-5343 |
| IMX-9365 | PA 스캐터 차트가 예외 여부를 exception 필드가 아닌 elapse 부호로 판단. elapse≥0인 예외 트랜잭션이 파란색(정상)으로 표시. RTM 스캐터(XMTxnMonitorChart.js)는 exceptionType 기반으로 정상 동작. | D3ScatterSelectable.js:239, XMTxnMonitorChart.js:641,708 |
| IMX-9371 | CDM→CD 타입 정규화가 DataModule.js 내부에서만 수행되어, PeakVisor 연계 시 원본 타입(CDM)이 그대로 전달됨. LinkedManager.js에 CDResponseInspector 뷰 타입은 정의되어 있으나 PeakVisor가 올바른 타입을 전달해야 동작. LOG 에이전트는 서비스 매핑 누락으로 에이전트 목록 미출력. | LinkedManager.js:294,333-348, DataModule.js:539-581,678-696, rtmCommon.js:5736-5741 |
| IMX-9388 | EtoE 액티브 트랜잭션의 getSplitTxnData에서 txnName.trim() 호출 시 null/undefined 방어 없음. WAS 액티브 트랜잭션(rtmActiveTxnList.js)에는 .trim() 없어 정상. krinvest 패키지는 난독화 상태. | rtmEtoEActiveTransaction.js (getSplitTxnData) |
| IMX-9399 | RTM WEB 모니터링의 alive/down 표시가 DataGather 갱신 패킷 미수신 시 해제되지 않음. isUseAliveDownInfo 옵션(v5.3+)으로 표시 제어 가능. webProcessAlarm 객체에 상태 잔존. | rtmGroupList.js:2011-2034,2322-2365, OptionConfig.js:58, IMXWSWorker.js:1040-1053 |
| IMX-9416 | LogAgent 수집 설정 CRUD에서 LINE_KEY 3개 필드(lineKeyStartIndex, lineKeyEndIndex, lineKeyValue)가 DTO/Entity에 미반영. 프론트 save()/delete()에서 미전송. Repository WHERE절이 serverId+fileNamePattern만 사용하여 동일 패턴 전체 연쇄 수정/삭제. alpha.2~3에서 순차 수정. | LogAgentConfigRequest.java:14-18, LogAgentConfigDeleteRequest.java:10-11, SettingRepository.java:597-599, config_collectionTargetSettingSideSheet.js:1144-1162, config_collectionTargetSetting.js:247-253 |
| IMX-9419 | 트랜잭션 순위 분석 TOP N Limit이 1:N=10, N:M=20으로 하드코딩. 수행시간/실행건수 탭 간 크로스 컬럼 미표시. v5.3·v5.4 모두 동일. Execute Count SQL에 elapse 필드 이미 조회 중이나 프론트 colValue에서 미표시. | RankingAnalysisSingle.js:103-124, RankingAnalysisMulti.js:104-125, TxnRankingAnalysisWork.js:29-46,520-556,1693-1718 |
| IMX-9458 | PeakVisor→InterMax RTM 연계 시 URL 파라미터(wasid/groupName)로 LNB 에이전트/그룹 자동 선택 기능 추가. urlConnects.js→localStorage→baseView.applyConnectParams() 흐름. 모니터 탭(WAS/WEB/CD 등)도 서버 타입 기반 자동 전환. | urlConnects.js:113-120, baseView.js:1372-1466, rtmView.js:55-64,244-286, LinkedManager.js:34-46 |
| IMX-9465 | EtoE 거래분석 하위 그리드에 에이전트명/에이전트 ID 컬럼 추가 개선. 기존(v5.4.12.0) WAS ID(숨김)만 존재, v5.4.12.1-alpha.1에서 추가 확인. 다른 TxnDetail(WAS/TP/Tuxedo)에는 이미 was_name 컬럼 존재. 백엔드 etoeResponseInspectorGrid 쿼리에 서버명 조인 필요. | EtoETransactionTrace.js:1011-1060,2132-2164, EtoeController.java:42-44, EtoeService.java:32-33, EtoeRepository.java:23 |
| IMX-9474 | 에이전트 그룹 설정 트리에서 groupId/subGroupId 동일 네임스페이스 저장 + DFS findNode가 첫 매칭 반환 → ID 충돌 시 하위그룹이 잘못된 부모에 배치. 5.4.11.1(플랫 그리드)에서는 미발생, 5.4.12.0(트리 그리드) 전환 시 도입. | config_agentGroup.js:616-644, BaseGridForPa.js:3390-3440 |
| IMX-9492 | mAPM HTTP Call 건수 개선: 지표 알람 설정(config_sideSheetStatAlert.js)에 Mobile Stat 타입 미존재, 백엔드 AlertConfig에도 Mobile alertType 미정의. mAPM 프론트엔드는 별도 웹앱(intermax_m/)으로 패키지 미포함. MobileRepository.selectAppStatus에서 XAPM_MO_HTTP_REQUESTS 테이블 조회. | config_sideSheetStatAlert.js:31-191, AlertConfig.java, MobileRepository.selectAppStatus (SQL) |
| IMX-9503 | RTM 토폴로지 뷰 resize()에서 maxNodePosY를 캔버스 최소 높이로 강제. 노드가 많을수록 토폴로지 세로 축소 불가. minHeight 600→300 수정으로 임시 조치. | topology.js:2453-2467, rtmTopologyView.js:90-105 |
| IMX-9508 | 에이전트 설정 화면에서 agent_id가 빈 유령 항목의 수정 시 updateServerInfo()가 pathValue 빈값으로 PUT /serverInfo (pathVariable 누락) → MonitoringController 404. api.js의 res.json()이 빈 body 파싱 시 SyntaxError 발생. | config_agentTab.js:1826-1857, MonitoringController.java:146, api.js:170 |
| IMX-9515 | 수집서버 재시작 시 Gather Disconnected 알람이 alert level 2(Critical)로 생성되어 bootAlarms 필터를 통과. 사용자가 Critical 소리만 체크한 상태에서 소리가 재생됨. WAS 인스턴스 다수 시 Disconnected/Server Down 알람이 연쇄 발생하여 50분간 지속. | PacketParser.java:385-449, RTMDataManager.js:1260-1266, WebSocketWorker.js:1654-1753, XMAlarmSound.js:307-323 |
| IMX-9518 | MFO 연동 DB 모니터에서 차트(패킷28=PktDbCpuStat)와 그리드(패킷29=PktSessionList) 데이터 소스 분리. 액티브 세션 캐시 저장 조건 intermaxTunningTid>0 (JSPD Agent 연결 필수), 락 세션은 holderKey 존재 필요. 6초 타임아웃 자동 클리어 동작. | PktSessionList.java:130-145, MfoParser.java:140-166, rtmOracleDBMonitor.js:714-780,974-987 |
| IMX-9521 | 우측 상단 메뉴 아이콘(3x3 격자 그리드 PNG)이 네비게이션 메뉴로 직관적이지 않음. cursor/tooltip 미설정. RTM·PA·Config 3개 화면에서 각각 다른 방식(PNG, 스프라이트, 인라인 스타일)으로 아이콘 정의. 기존 SVG 햄버거 아이콘(intermax/images/icon/) 활용 가능. | mainMenu.css:11-23, PATheme_v1.css:477-486, Config/view.html:247-252, RTM/app.js:256 |
| IMX-9525 | PA 추이분석 화면별 X축 시간 포맷 불일치. 일반 추이(`%d %H:%M`), 비교 추이(인덱스 모드 시간만), WAS Workload(`H`), RTM(`%H:%M:%S`→`%H:%M` 동적). CanvasChartForPa 기본 timeformat과 화면별 차트 모드(time/index) 차이가 원인. | CanvasChartForPa.js:295, ComparisonTrend.js:1444-1454, rtmChartFrame.js:155,608, Envir.js:72-79 |
| IMX-9527 | 상단 탭 컨텍스트 메뉴 체크박스-텍스트 겹침 및 Tuxedo/Tmax 명칭 불일치. PA 디자인 리뉴얼 시 미고려된 UI. TP(Tmax)와 Tuxedo가 별도 모듈이나 메뉴/탭 명칭 혼용. | MainTabPanel.js:146-166, exem-lang-ko.js:1945,1574 |
| IMX-9529 | PeakVisor→InterMax RTM 연계 URL 수정(IMX-9458 후속). wasid 기반 LNB 자동 선택(autoSelectServiceByWAS)은 v5.4.12.0에서 구현 완료. groupName 파라미터는 LinkedManager.js RTM 분기에서 미처리. rtmGroupList.js에 toggleMenuBySelectedGroupName() 등 그룹 선택 함수 존재하나 연계에서 미호출. | urlConnects.js:113-120, LinkedManager.js:34-38, rtmServiceList.js:640-666, rtmGroupList.js:969,1013 |
| IMX-9532 | 패치 빌드 시 개발환경(5.3.IntermaxAPINext/pjs_sample/) 코드가 view.html에 혼입. `<script>` 블록 내부에 `<img>` 태그 2개 삽입 → JS SyntaxError(`Unexpected token '<'`) → 대시보드 화면 미표출. 원본 코드에는 해당 경로·태그 없음. | RTM/view.html (패치본 line ~1065-1066, 원본 1017줄) |
| IMX-9536 | LOG 타입 에이전트 추가 후 토폴로지 4곳에서 LOG 분기 누락: collectAgentListByMonitorType(LOG→wasIdList 오분류), openTxnMonitor(LOG 분기 없음), rtmMultipleMonitorTypeTxnMonitor(Tab 매핑 없음), AGENT 목록 버튼 비활성화 미처리. rtmLOGTransactionMonitor.js는 이미 구현되어 있으나 연결만 안 됨. | rtmTopologyView.js:767-837,1031-1081, rtmMultipleMonitorTypeTxnMonitor.js:10-21, rtmTopologyGroupChildList.js:320-336 |
| IMX-9537 | EtoE 거래분석 확장 필드(custom_filler) 기능 추가. 백엔드: @PostMapping /etoeResponseInspector, /etoeResponseInspectorGrid 신규, ExtFieldFilter DTO(index 1-6, @Min/@Max 검증). 프론트: useExtFields 옵션, 거래분류(녹색#2e7d32)/확장필드(파란색#1565c0) 라벨 색상 구분, GET→POST 전환, 파라미터 string→array 변경. EtoE 응답시간 분포도 TID 경고 후 재조회 불가 수정(retrieveLoading=false 추가). | EtoeController.java:60-68, ExtFieldFilter.java:16-48, EtoETransactionTrace.js:81-153,1679-1683,2025-2094, EtoEElapseDistribution.js:906-909,947-951 |
| IMX-9551 | 클라이언트 옵션 상세 설정 화면에서 한글 인코딩 깨짐 표시. 근본 원인은 DataGather의 DatabaseService.executeSql() FileReader 인코딩 미지정이나, 프론트엔드 config_client_option.js가 API 응답의 description을 html로 렌더링하여 깨진 문자 그대로 표시. | config_client_option.js:129-170,410-416, ConfigEnvController.java:36, ConfigRepository.java:31 |
| IMX-9562 | CVE-2026-29000(pac4j-jwt) 보안취약점 영향 없음 확인. pac4j-jwt JAR/클래스 참조 5.2/5.3/5.4 전 버전에서 0건. 5.4 JWT는 io.jsonwebtoken(jjwt) + HS512 사용, 5.2/5.3은 JWT 미사용(세션 기반). | com.exem.pjs.util.auth.JwtTokenProvider (5.4 only) |
| IMX-9565 | 거래통계 히트맵 Top-N 업무 탭에서 업무 미등록(BUSINESS_ID=0) 시 getBusinessHierarchy()가 빈 객체 반환하여 업무그룹/업무/세부업무 3개 칼럼 공백 표시. 업무 삭제 시 거래코드 칼럼까지 공백. PJS 5.4.13.0-alpha.2에서 business_id=0 데이터 제외 쿼리 수정으로 해결. | TxnSummaryHeatmap.js:1551-1646,1741-1777, DataModule.js:1284-1304, PerformanceTrendController.java:511-513 |
| IMX-9577 | APIM 모니터링에서 Kafka RtmApimOsStat 메시지를 수신하여 캐시에 저장 후 UI에 UP/DOWN 표시. DataGather에서 상태 갱신 패킷이 오지 않으면 DOWN 유지. | ApimOsStat.java |
| IMX-9578 | CVE-2026-29000(pac4j-jwt) 보안취약점 영향 없음 확인 (IMX-9562와 동일 건). pac4j-jwt 미사용, JWT는 io.jsonwebtoken(jjwt) 0.11.5 + HS512 사용. | com.exem.pjs.util.auth.JwtTokenProvider |
| IMX-9605 | 외부 호출 설정 UI가 TYPE='REMOTE'(=1) 필터로만 조회. 5.4.12.0에서 XAPM_DEST_INFO에 TYPE 컬럼 추가 후 save/delete/update 시에도 type:'1' 전송. 마이그레이션 시 TYPE 미포함 INSERT → NULL → 미표시. | config_externalCallSetting.js:843-848, ConfigCommonController.java, ConfigRepository.java |
| IMX-9608 | 에이전트 그룹 편집 시 processSubGroupChanges()의 excludeServerIds가 saveServerIds(잔류 에이전트)를 사용하여 하위 그룹 에이전트까지 제외. 백엔드 updateAgentGroup()에서 groupId 초기화 시 subGroupId 미처리로 데이터 불일치 발생. | config_agentGroupSideSheet.js:301-409, MonitoringService.java:107-121 |
| IMX-9632 | E2E 거래분석 화면에서 scatter/grid 비동기 API 중 scatter 완료 시 retrieve_loading 조기 해제 → 재조회 허용 → grid 응답 중복 누적으로 데이터 2배 표시. chart+grid 양쪽 완료 후 로딩 해제로 수정. | EtoETransactionTrace.js:1619-2059 |
| IMX-9557 | Container Agent 수집 데이터 확인: ContainerStat 엔티티(CPU/Memory/Network/DiskIO 30+ 필드), RtmContainerService(Kafka consumer), RtmContainerRepository(ClickHouse 저장). REST API: /api/v1/intermax/rtm/containerStat, containerProcess, containerIds. 권장 리소스: requests cpu:100m/mem:128Mi, limits cpu:200m/mem:256Mi. | ContainerStat.java, RtmContainerService.java, RtmContainerRepository.java, CommonStatController.java |
| IMX-9652 | WAS Active Transaction "클래스 메소드" 컬럼에 DataGather에서 받은 classMethod 값을 별도 가공(return type 제거) 없이 그대로 표시. 백엔드 ActiveTxnProcessor도 gRPC classMethod를 그대로 매핑. return type 숨김 옵션 없음. | rtmEtoEActiveTransaction.js:575, ActiveTxnProcessor.java:40 |
| IMX-9668 | PA wasDBComboBoxForPa의 isAddOldServer=true 기본값으로 Comm.oldServerInfo(삭제 이력) merge → RTM에서 제거된 Agent가 PA에 계속 표시(의도된 동작). 점차트 드래그 시 selectedWasIdArr/getSelectedIdArr 분기에서 괄호 포함 에이전트명 매칭 실패. TxnHistory._wasValidCheck()에서 AllWasList 비동기 구성 미완료 시 첫 조회 실패. | wasDBComboBoxForPa.js:19,461-463, rtmTransactionMonitor.js:428-454, TxnHistory.js:426-458, ServerScale.js:66-101 |

## 자주 관련되는 증상
- [UI 렌더링 오류](../symptoms/UI-렌더링-오류.md)
- [데이터 조회 이상](../symptoms/데이터-조회-이상.md)
- [데이터 수집 오류](../symptoms/데이터-수집-오류.md)
- [설정 적용 실패](../symptoms/설정-적용-실패.md)
- [알람/알림 오류](../symptoms/알람-알림-오류.md)
- [성능/리소스 이상](../symptoms/성능-리소스-이상.md)
- [에이전트 연결 문제](../symptoms/에이전트-연결-문제.md)
- [호환성/버전 오류](../symptoms/호환성-버전-오류.md)
- [지표/수치 불일치](../symptoms/지표-수치-불일치.md)
