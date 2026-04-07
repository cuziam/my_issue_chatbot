# DataGather

## 역할
JSPD Agent에서 수집된 데이터를 집계하고 처리하는 수집 서버. DGM(Master)과 DGS(Slave)로 구성되며, PostgreSQL/ClickHouse와 연동.

## 분석에서 발견된 주요 사항
| 이슈 | 발견 사항 | 관련 파일 |
|------|----------|----------|
| IMX-8586 | Tanzu/K8s 환경에서 checkTanzuStatus()가 주기적으로 만료 Pod 정리 시 remove_auto_id 프로시저의 서브쿼리 다중행 반환으로 PSQLException + NullPointerException 반복 발생 | XmWasIDManage.java:228-354, DGMMaster.java:1511-1597 |
| IMX-8972 | 자정 일변경 시 checkPartition()→analyze_pg_catalog() 실행 시 analyze_timeout=0(무제한)으로 장시간 ANALYZE 실행, 장기 운영(6년)으로 파티션 대량 누적 시 pg_catalog 비대화로 CPU 과부하 유발 | PostgresPartitionManage.java:47, DGMMaster.java:454, XmConfig.java:300 |
| IMX-7631 | .NET 에이전트 알람 설정 시 DB(XAPM_ALERT_CONFIG)에 JVM 이름으로 통일 저장하는 의도적 설계. DOTNET 초기 설정에 "JVM CPU Usage(%)" 하드코딩. | InsertValue.java:8, pktJvmStat.java:189-193, AlertEnv.java:336 |
| IMX-8895 | 서버 알람 SMS_FLAG 판정에서 ThreadMap.map_server_alert_sms_enable 로딩 결함으로 SMS_FLAG=0 저장. v5.4.12에서 ServerAlertNotiConfigLoader(MyBatis 기반)로 전면 교체하여 수정. | AlertEnv.java:1004-1006, ServerAlertNotiConfigLoader.java:48-49, pktWasAlert2.java:74 |
| IMX-8964 | DG 패치(IMX-8412 기능)로 XAPM_TP_SVR_CONFIG 시간단위 insert 추가 시, XAPM_TP_SVC_NAME insert의 NOT EXISTS 중복 방지 로직이 무효화되어 1시간 단위 중복 insert 발생. 테이블 비대화로 Tmax 서버명 조회 불가 및 속도 저하. | pktTPCfgSVCEnvInfo.java:72-80, LogTPSVCName.java:58-91, SQL_Postgres.sql:2434-2437 |
| IMX-8992 | 순수 JDBC→MyBatis 전면 마이그레이션 (346파일, +14992/-12641). DGManager.java 43% 감소(4219→2389줄), XmSQLStrings(3339줄) 삭제, PreparedStatement/ResultSet 사용 84% 감소(467→73건). MyBatisContext+Proxy 패턴 도입, CDO 89개+Mapper 149개 생성, 7개 도메인별 Query/Command 분리. | DGManager.java, MyBatisContext.java, mybatis/mapper/ |
| IMX-9333 | XmAlarmLogger.info()가 내부적으로 logger.debug()를 호출하는 버그. log_level=info(기본값)일 때 smsJar 자정 로그파일 미생성. touchLogFiles() 날짜 변경 감지 로직은 패치로 추가되었으나 logger 레벨 불일치로 동작 안 함→재패치로 수정. | XmAlarmLogger.java:33-34, XmLibraryLoader.java:59-64,87-92 |
| IMX-9356 | sendCommonConfig()에서 xapm_common_config 테이블에 imxtxn 타입 데이터가 없으면 패킷 미전송 → imxtxn 타임아웃 → 10초 간격 재연결 무한 반복. DB에 최소 1건 INSERT 필요. | pktImxAppType.java:81-83,139, XmLoadData.java:1595 |
| IMX-9399 | Active Down 알람 패킷에서 description 필드에 alive수/down수 형식으로 전달. checkBootDown()에서 alive=0&down>0이면 Server Down, 이후 alive>0이면 Server Boot 알람 생성. 정상 복귀 시 down=0 갱신 패킷 미전송 가능성. | pktAlertHistory.java:163,231-239,295-320, AlertEnv.java:257 |
| IMX-9416 | LogAgent LINE_KEY 기능 추가. DG 5.4.12.1-alpha.2에서 XAPM_LOG_AGENT_CONFIG 테이블에 LINE_KEY_START_INDEX, LINE_KEY_END_INDEX, LINE_KEY_VALUE 컬럼 추가. 동일 serverId+fileNamePattern에서 거래ID(LINE_KEY)별로 다른 FIELD_MAPPING 적용 가능. LogAgentConfig에 LINE_KEY 3개 필드 추가 필요. | jdg/server/remote/log/LogAgentConfig.java |
| IMX-9483 | slave DataGather → pootprinter TCP 통신에서 StreamInput.readBoolean()이 바이트 정렬 불일치로 실패. ProcessEtoeRemoteCall에서 E2E 트랜잭션을 pootprinter로 전송하는 경로 확인. DGS 로그에서 별도 BatchUpdateException(JVM stat 중복 INSERT) 발견. | StreamInput.java:48-61, ProcessEtoeRemoteCall.java |
| IMX-9508 | pktAutoAssignWasId.process_data()에서 platform_type==AUTO_SCALE_MODE(4)일 때만 XmWasIDManage.assignWasId() 호출. TYPE=3(normal)은 분기를 건너뜀. auto_scale_was_id_mode=false이면 즉시 0 반환. use_was_id_valid_check=false 시 wasid=0도 JSPD에 전송. Kafka 타임아웃(60초) 시에도 0 반환 가능. | pktAutoAssignWasId.java:51,89-91, XmWasIDManage.java:68-73,143-171 |
| IMX-9510 | AlertConfig.fromCDO()에서 alert_type을 "Stat Alert"로 하드코딩. v5.4.12.1-alpha.3에서 cdo.getAlertType()으로 CDO 동적 처리로 변경. AlertConfigCDO에 alertType 필드 추가. delay_time NPE 방어 코드도 추가. 타입 수정으로 TP Stat Alert에서 thread_dump/use_script 동작 변경 가능성 있음. | AlertConfig.java:51, AlertConfigCDO.java:19,42,56, pktWasStat.java:328,336,349,357 |
| IMX-9551 | DatabaseService.executeSql()에서 FileReader에 charset 미지정. JVM 플랫폼 기본 인코딩(cp949 등)으로 UTF-8 SQL 파일(option_value.sql) 읽기 → ClickHouse에 깨진 한글 저장. InsertExecutor.java는 StandardCharsets.UTF_8 명시로 정상. | DatabaseService.java:163,184, InsertExecutor.java:653 |
| IMX-9537 | 가변 필러 인덱스 분기: fillerIndex < 100 → setExtField()로 extra_fields Map에 저장(검색용 확장 필드), fillerIndex >= 100 → variable_fillers에 추가(분류 필러). XmConst.EXT_FIELD_INDEX_BOUNDARY=100, EXT_FIELD_MAX_SLOT=7 정의. RecTxnDetail/RecActiveTXN/ReqTempTxnDetail에 extra_fields HashMap 추가. 이전 버전(5.4.12.1-alpha.3)에는 없던 기능. | pktTxnDetail.java:665-670,776-783, pktActiveTXN.java:508-509,567-573, XmConst.java, RecTxnDetail.java:85 |
| IMX-9557 | Container Agent → DataGather gRPC 양방향 스트리밍 통신 구조 확인. ContainerAgentGrpcService에서 Agent 핸드셰이크(Redis 등록), 컨테이너 통계 수신(RTM+Log 변환→Kafka 전송), delta 계산(network/diskIO/OOM), 프로세스 1분 집계(동일 PID max값) 처리. | ContainerAgentGrpcService.java |
| IMX-9564 | APIM imxosm → DataGather TCP 통신 경로 확인. IdentityImxOsmApim(server_type=15)이 APIM 데이터 수신, SendClientAPIM이 alert/데이터 전송 처리. imxosm은 공유 메모리에서 읽은 데이터를 WR_ADDR(jspd.prop)로 전송. | IdentityImxOsmApim.java, SendClientAPIM.java |
| IMX-9565 | checkBusinessID()에서 tx_code 패턴(EQ/ST/CO)으로 업무 매칭 실패 시 business_id=0 저장. 업무 미등록 거래가 히트맵에 공백 행으로 표시되는 원인. | CommonRTM.java:426-479, pktActiveTXN.java:528-548 |
| IMX-9577 | APIM OS stat 패킷 수신 시 ReqClientServerStatus(status=0) 전송으로 UP 상태 갱신. TCP 연결 해제 시 status=1(DOWN) 전송. filler4 필드 15bytes(Java)와 C 데몬 간 구조체 일치 필수. 버퍼 오버플로우로 공유 메모리 손상 시 데이터 미전송 → DOWN 유지. | pktAPIMOsStat.java:50-133, pktAPIMTxnDetail.java:241-244, NettyMessageChannelHandler.java:824-831, IdentityImxOsmApim.java |
| IMX-9582 | TcpReadAlarmHistory에서 Exception Alert 분기의 SMSData 생성자가 guid 없는 13개 파라미터 버전 호출. 일반 Alert(else 분기)는 guid 포함 16개 파라미터 버전 사용하여 정상. Elapsed Time Alert, OOM Alert 분기도 동일 문제 존재. | TcpReadAlarmHistory.java:154-155,140-152,156-159, SMSData.java:39,114 |
| IMX-9605 | DestInfoMigration(버전5)에서 XAPM_DEST_INFO에 TYPE Enum8('REMOTE'=1,'KAFKA'=123) 컬럼 추가 + 기존 데이터 TYPE=1 백필. 업그레이드 후 수동 INSERT 시 TYPE 누락하면 NULL → UI 미표시. PpDestInfoMessageService 자동 수집은 TYPE 포함. | DestInfoMigration.java, PpDestInfoMessageService.java |
| IMX-9643 | autowasid ONPRE_MODE(3)에서 WAS 추가 시 xapm_was_info INSERT만 수행, sms_server_list에 SMS 매핑 자동 등록 로직 없음. K8S/AWS/AutoScale 모드에서도 동일하게 SMS 자동 매핑 미구현. XmAlarmService→XmJarSms에서 sms_server_list 조회 실패로 SMS 미발송. | pktAutoAssignWasId.java:169-195, XmWasIDOnpremiss.java, XmAlarmService.java |
| IMX-9652 | pktRespClassMethodName에서 `className|methodName|methodType` 형식으로 method_list 저장. CommonRTM에서 method_list 조회 시 className 부분(return type 포함)을 class_method 필드로 설정. return type 제거 가공 로직 없음. | pktRespClassMethodName.java:75, CommonRTM.java:261-279 |
| IMX-9668 | AUTO_WAS_ID Clear Time 경과 후 checkAutoWasIdRetry()→removeWasId()로 메모리+ClickHouse에서 삭제하고 XAPM_AUTO_ID_HISTORY에 이력 기록. PA에서 이 이력을 /rtm/autoIdRetriveList API로 조회하여 oldServerInfo에 포함하므로 Clear Time과 PA 에이전트 목록은 별개 메커니즘. | DGManager.java:3199-3256, XmWasIDManage.java:268-501 |

## 자주 관련되는 증상
- [성능/리소스 이상](../symptoms/성능-리소스-이상.md)
- [알람/알림 오류](../symptoms/알람-알림-오류.md)
- [데이터 수집 오류](../symptoms/데이터-수집-오류.md)
- [에이전트 연결 문제](../symptoms/에이전트-연결-문제.md)
- [설정 적용 실패](../symptoms/설정-적용-실패.md)
- [UI 렌더링 오류](../symptoms/UI-렌더링-오류.md)
- [호환성/버전 오류](../symptoms/호환성-버전-오류.md)
- [지표/수치 불일치](../symptoms/지표-수치-불일치.md)
