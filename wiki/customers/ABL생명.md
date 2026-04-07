# ABL생명

## 환경
| 항목 | 값 |
|------|-----|
| 사용 버전 | InterMax 5.4.12.0 (5.4.11.1에서 업그레이드) |
| 커스텀 패키지 | 없음 |
| 특이사항 | 에이전트 그룹/하위그룹이 다수 등록된 환경, groupId와 subGroupId 간 숫자 충돌 존재. MFO 연동 환경. 일부 WAS는 IBM JDK 1.6 런타임 |

## 이슈 이력
| 이슈 | 유형 | 증상 | 상태 | 요약 |
|------|------|------|------|------|
| IMX-9474 | issue_analysis | [UI 렌더링 오류](../symptoms/UI-렌더링-오류.md) | closed | 5.4.12 업그레이드 후 에이전트 그룹 트리에서 하위그룹이 다른 하위그룹 아래 중첩 표시 |
| IMX-9503 | issue_analysis | [UI 렌더링 오류](../symptoms/UI-렌더링-오류.md) | qa completed | 토폴로지 뷰 세로 크기가 maxNodePosY로 강제 고정되어 하단 차트 배치 불가 |
| IMX-9518 | issue_analysis | [에이전트 연결 문제](../symptoms/에이전트-연결-문제.md) | closed | MFO 연동 DB 모니터에서 차트는 정상이나 액티브/락 세션 그리드 빈 상태 — JSPD Agent 미연결 시 정상 동작 |
| IMX-9689 | issue_analysis | [호환성/버전 오류](../symptoms/호환성-버전-오류.md) | closed | IBM JDK 1.6 환경에서 jspd.jar 내장 ext 클래스가 class version 불일치로 로딩 실패, HTTP 트랜잭션 자동 연계 불가 |
