# SSG

## 환경
| 항목 | 값 |
|------|-----|
| 사용 버전 | InterMax 5.3 (패키지 2305), PostgreSQL 12 |
| 커스텀 패키지 | - |
| 특이사항 | autowasid On-Premise 모드 사용, WAS 자동 추가 빈번 |

## 이슈 이력
| 이슈 | 유형 | 증상 | 상태 | 요약 |
|------|------|------|------|------|
| IMX-9643 | issue_analysis | [알람/알림 오류](../symptoms/알람-알림-오류.md) | closed | autowasid로 추가된 WAS에서 sms_server_list 매핑 누락으로 SMS 미발송, 수동 등록으로 해결 |
