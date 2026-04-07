# HL만도

## 환경
| 항목 | 값 |
|------|-----|
| 사용 버전 | PlatformJS 5.4.8.2-patch.1, DataGather 5.4.8.0, Ingester 5.4.8.0, PeakVisor v1.0.0.4~v1.0.0.5 |
| 커스텀 패키지 | - |
| 특이사항 | SQLSERVER DB 타입 사용 (8개 수집서버 전체), PeakVisor 통합대시보드 운영 |

## 이슈 이력
| 이슈 | 유형 | 증상 | 상태 | 요약 |
|------|------|------|------|------|
| IMX-9235 | issue_analysis | [데이터 수집 오류](../symptoms/데이터-수집-오류.md) | closed | SQL 문 정렬 버튼 클릭 시 SQLSERVER 쿼리 포맷팅 실패 (Oracle 벤더 하드코딩) |
| IMX-9236 | issue_analysis | [지표/수치 불일치](../symptoms/지표-수치-불일치.md) | closed | PA DatePicker에서 매시 정각 전후 FromTime>ToTime 역전 (toHour 변수 참조 오류) |
| IMX-9237 | issue_analysis | [UI 렌더링 오류](../symptoms/UI-렌더링-오류.md) | reopened | PeakVisor 통합대시보드 그룹 카드 위젯이 연계 서버 불안정 시 사라지는 현상 (disable 토글 + 캐시 빈 리스트 전파) |
| IMX-9365 | issue_analysis | [UI 렌더링 오류](../symptoms/UI-렌더링-오류.md) | closed | 예외 트랜잭션 토글 조회 시 elapse≥0인 예외 트랜잭션이 스캐터 차트에서 파란색(정상)으로 표시 (elapse 부호 기반 판단 오류) |
