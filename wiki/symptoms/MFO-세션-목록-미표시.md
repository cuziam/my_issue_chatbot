# MFO 세션 목록 미표시

## 관련 키워드
MFO, DB 모니터, 세션 목록, 액티브 세션, 락 세션, 그리드 빈 상태, mfoSession, mfoLockTree, 차트 정상 그리드 비어있음, intermaxTunningTid, PktSessionList, 패킷 29번

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-9518 | ABL생명 | PlatformJS | 미명시 (MFO 연동) | 차트(패킷28)와 그리드(패킷29) 데이터 소스가 다름. 액티브 세션 그리드는 intermaxTunningTid>0 조건 필요(JSPD Agent 연결 필수), 락 세션은 holderKey 존재 필요 | PktSessionList.java:130-145, MfoParser.java:140-166, rtmOracleDBMonitor.js:714-780 |

## 공통 패턴

## 조사 시 체크포인트
1. DB 모니터 타이틀에 `[MFO:...]` 형태로 MFO 이름이 표시되는지 확인 (MFO 연동 활성 여부)
2. 차트(active sessions 등)가 정상 표시되면 MFO WebSocket 연결 및 패킷 28번(통계)은 정상
3. PlatformJS 로그에서 PktSessionList(패킷 29번) 수신 여부 확인
4. API 직접 호출로 서버 캐시 데이터 확인: `/api/v1/intermax/rtm/mfoSession?instanceIds={dbId}`, `/api/v1/intermax/rtm/mfoLockTree?instanceIds={dbId}`
5. JSPD Agent가 DB 세션과 연결되어 client_identifier(`_xm` prefix)를 설정하고 있는지 확인 — 미설정 시 intermaxTunningTid=0으로 그리드 항상 빈 상태 (정상 동작)
6. DB ID 매핑 확인: `LinkUtil.getMfjDbIds("MFO", productDbId)` → ThreadMap.map_link_data에 매핑 존재 여부
7. 프론트엔드 6초 타임아웃 자동 클리어 동작 여부 확인 (간헐적 데이터 유실 가능)
