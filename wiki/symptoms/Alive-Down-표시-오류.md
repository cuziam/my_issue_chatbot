# Alive/Down 표시 오류

## 관련 키워드
alive, down, Active Down, 상태 표시, 모니터링, 갱신 안 됨, 프로세스 상태, webProcessAlarm, isUseAliveDownInfo, RTM

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-9399 | K-에듀파인 (경기교육청) | PlatformJS, DataGather | PlatformJS 5.2.200309.02, DG 190604.04_keris | DataGather가 정상 복귀 알람(down=0)을 미전송하여 프론트엔드 webProcessAlarm 객체에 기존 down 상태 잔존. v5.2에 isUseAliveDownInfo 옵션 부재. | rtmGroupList.js:2011-2034,2322-2365, OptionConfig.js:58, IMXWSWorker.js:1040-1053, pktAlertHistory.java:163,295-320 |
| IMX-9577 | 우리투자증권 | APIM (C 데몬), DataGather, PlatformJS | IMXAPIM-2.4.4, DG/PJS v5.4.12.0 | imxosm 공유 메모리 세그먼트 읽기 실패(SEGMENTINFO ERROR) → OS stat 패킷 미전송 → DataGather에서 상태 갱신 없음 → DOWN 표시. imxapim_all_sample.c의 filler4 버퍼 오버플로우(15바이트 필드에 16바이트 strcpy)가 공유 메모리 구조체 손상 유발 가능. | pktAPIMOsStat.java:50-133, pktAPIMTxnDetail.java:241-244, NettyMessageChannelHandler.java:824-831 |

## 공통 패턴
2건의 사례에서 공통적으로 DataGather로의 상태 갱신 데이터가 미도착하여 DOWN이 유지됨. 원인은 다르지만 (정상 복귀 패킷 미전송 vs 공유 메모리 읽기 실패), DataGather가 상태 갱신 신호를 받지 못하면 UI에 반영되지 않는 구조가 핵심.

## 조사 시 체크포인트
1. DGServer 로그에서 해당 서버의 "Active Down" 알람 이력 확인
2. 정상 복귀 후 active_count/down_count 갱신 패킷이 전송되었는지 확인
3. 브라우저 새로고침(F5)으로 해결되는지 확인 (checkServerStatus → checkWebProcessStatus 재실행)
4. Option.conf에 isUseAliveDownInfo 옵션 존재 여부 확인 (v5.3 이상에서만 지원)
5. v5.2 환경이면 isUseAliveDownInfo 옵션이 없으므로 패치 적용 또는 업그레이드 필요
6. APIM 에이전트의 경우: DataGather 로그에서 SEGMENTINFO ERROR 반복 여부 확인
7. APIM 공유 메모리 세그먼트 정상 여부 확인 (`ipcs -m`, `imxapim_all_sample` 실행 시 UP 전환되는지)
