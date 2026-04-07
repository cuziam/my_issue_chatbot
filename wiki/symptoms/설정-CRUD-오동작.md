# 설정 CRUD 오동작

## 관련 키워드
설정 추가 실패, 설정 삭제 실패, 연쇄 수정, 유니크 키 누락, CRUD, config, LogAgent, 중복 키, WHERE절 불완전, 그룹 편집, 하위 그룹 제거, 에이전트 그룹, subGroup

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-9416 | 현대차증권 | PlatformJS | 5.4.12.1-alpha.1 | LINE_KEY 컬럼 추가 후 DTO/Entity/Repository에 미반영 → 유니크 키 불완전으로 POST 중복 실패, DELETE/UPDATE 시 동일 패턴 전체 영향 | LogAgentConfigRequest.java:14-18, SettingRepository.java:597-599, config_collectionTargetSettingSideSheet.js:1144-1162 |
| IMX-9608 | 공통 | PlatformJS | 5.4.13.0-alpha.1 | 그룹 편집 시 processSubGroupChanges()가 excludeServerIds를 saveServerIds(잔류)로 사용 → 하위 그룹 에이전트까지 제외. 백엔드도 groupId 초기화 시 subGroupId 미처리 | config_agentGroupSideSheet.js:301-409, MonitoringService.java:107-121 |

## 공통 패턴
설정 화면에서 부모-자식 관계가 있는 데이터를 수정할 때, 자식 엔티티에 대한 연쇄 처리 로직이 불완전한 패턴이 반복됨. 프론트엔드에서 변경 대상(삭제/추가)과 제외 대상을 혼동하거나, 백엔드에서 관련 필드를 함께 초기화하지 않아 데이터 불일치 발생.

## 조사 시 체크포인트
1. DB 테이블에 새 컬럼이 추가되었는데 백엔드 DTO/Entity에 해당 필드가 반영되었는가?
2. 프론트엔드 save()/delete() 요청에서 새 필드를 API로 전송하고 있는가?
3. Repository의 WHERE절이 유니크 키를 완전히 포함하는가? (DELETE, UPDATE 모두 확인)
4. 유니크 키 변경 시 기존 데이터의 마이그레이션 전략이 있는가? (NULL 허용 여부)
5. 일괄 수정(batch update) 시 개별 레코드 식별이 가능한가?
