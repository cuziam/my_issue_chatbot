# DB 알람 정보 부족

## 관련 키워드
DB 지표, 알람 색상, 색상 기준, 도움말, 툴팁, MFO 연계, alertLevel, linkAlarm, 주황색, 빨간색, 게이지

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-8945 | 한국신용정보원 | PlatformJS | 5.4.12.0 | DB 알람 색상 변경 기준 안내 부재 + 알람 상세 확인 불가 → 도움말 팝업 및 마우스오버 툴팁으로 개선 | rtmDatabase.js:144-163,578-613, rtmDatabaseChart.js:523-634 |

## 공통 패턴

## 조사 시 체크포인트
1. MFO 연계가 설정되어 있는지 확인 (`useExtMaxGaugeDetail` 활성화 여부)
2. InterMax PlatformJS ↔ MFO 서버 간 WebSocket 연결 상태 확인
3. `/api/v1/intermax/rtm/linkAlarm` API 응답에서 alertLevel 값 확인 (1: 주황색, 2: 빨간색)
4. `ThreadMap.map_last_link_data` 캐시에 데이터가 존재하는지 확인
5. 도움말 팝업/알람 툴팁이 해당 버전에 구현되어 있는지 코드 확인
