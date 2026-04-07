# KB라이프

## 환경
| 항목 | 값 |
|------|-----|
| 사용 버전 | InterMax 5.3 (Client: 5.3.2502.06-KB-LIFE-05) |
| 커스텀 패키지 | intermax_v53_kblife |
| 특이사항 | Autoscale(scale in/out) 환경 운영 |

## 이슈 이력
| 이슈 | 유형 | 증상 | 상태 | 요약 |
|------|------|------|------|------|
| IMX-9302 | issue_analysis | [데이터 조회 이상](../symptoms/데이터-조회-이상.md) | qa deploy | 성능추이분석 커넥션 풀에서 scale-in Agent 과거 데이터 미조회. INNER JOIN + DB function cascade 삭제 복합 원인 |
| IMX-9515 | issue_analysis | [알람/알림 오류](../symptoms/알람-알림-오류.md) | closed | 수집서버 재시작 후 Gather Disconnected Critical 알람이 소리 필터 통과하여 50분간 Critical 소리 지속 |
