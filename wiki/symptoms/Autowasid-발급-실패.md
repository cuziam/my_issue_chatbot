# Autowasid 발급 실패

## 관련 키워드
autowasid, 자동 WAS ID, TYPE_AUTOMATIC_WASID, auto_scale_was_id_mode, 유령 에이전트, wasid 0, 에이전트 자동 발급, pktAutoAssignWasId, XmWasIDManage, 에이전트 설정 404

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-9508 | 공통 | JSPD, DataGather, PlatformJS | DG 5.4.11.1, JSPD 25.09.12.02 | DG의 pktAutoAssignWasId가 TYPE=4(auto scale)만 처리, TYPE=3(normal)은 무시 → wasid=0 → 유령 에이전트 3개 생성 + 프론트 PUT /serverInfo에 agent_id 누락으로 404 | pktAutoAssignWasId.java:51, XmWasIDManage.java:70-72, config_agentTab.js:1826-1857 |

## 공통 패턴

## 조사 시 체크포인트
1. `jspd.prop.ini`의 `TYPE_AUTOMATIC_WASID` 값 확인 (1~4 중 어떤 모드인지)
2. DGServer.xml의 `auto_scale_was_id_mode` 설정이 `true`인지 확인 (DGS 필수, DGM 선택)
3. DG 로그에서 `[AUTO ASSIGN WAS ID]` 또는 `auto_scale_was_id_mode is false. return 0` 메시지 확인
4. JSPD 로그에서 `received wasid : N` 확인 (N=0이면 실패)
5. 현재 5.4 DG에서는 TYPE=4만 정상 동작 — TYPE=3 사용 시 DG 코드 수정 또는 TYPE=4로 변경 필요
6. Kafka/Ingester 통신 문제 시 TYPE=4에서도 wasid=0 발급 가능 (findAvailableWasID 60초 타임아웃)
7. `use_was_id_valid_check=false`이면 wasid=0이 JSPD에 전송되어 유령 에이전트 생성
8. 에이전트 설정 화면에서 ID 빈 항목 존재 시 수정 버튼 → 404 에러 확인 (agent_id 누락 문제)
