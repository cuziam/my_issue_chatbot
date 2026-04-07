# K-에듀파인

## 환경
| 항목 | 값 |
|------|-----|
| 사용 버전 | InterMax 5.2 (PlatformJS 5.2.200309.02, Client 5.2.190426.05, DG 190604.04_keris) |
| 커스텀 패키지 | keris 전용 DataGather 버전 |
| 특이사항 | 경기교육청 소속. v5.2 장기 운영 환경. 업그레이드 예정 없음. |

## 이슈 이력
| 이슈 | 유형 | 증상 | 상태 | 요약 |
|------|------|------|------|------|
| IMX-9399 | issue_analysis | [Alive/Down 표시 오류](../symptoms/Alive-Down-표시-오류.md) | qa completed | WEB 모니터링 alive/down 표시가 정상 복귀 후에도 갱신되지 않음. v5.3의 isUseAliveDownInfo 옵션을 v5.2 패치로 백포트하여 해결. |
