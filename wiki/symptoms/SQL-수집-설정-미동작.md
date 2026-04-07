# SQL 수집 설정 미동작

## 관련 키워드
SQL_DETAIL_ELAPSE_LIMIT, SQL 수집 제한, SQL 필터링, elapse, Exception SQL, 설정 미적용, 모든 SQL 수집, imx.prop, jspd.prop.ini, DISABLE_SQL_DETAIL_ELAPSE_LIMIT

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-9356 | 농협경제 | JSPD | 21.12.01.14.hotfix.nh.260306 | hotfix 버전은 imx.prop에서 SQL_DETAIL_ELAPSE_LIMIT를 읽으나, jspd.prop.ini에 설정하여 필터 미동작. 2509.04 최신 버전은 jspd.prop.ini 참조로 변경됨. | udp/d.java:152, XmProperties.java:549 |

## 공통 패턴

## 조사 시 체크포인트
1. JSPD 버전에 따라 SQL_DETAIL_ELAPSE_LIMIT 설정 파일이 다름: base/hotfix는 **imx.prop**, 2509.04 이후는 **jspd.prop.ini**
2. `DISABLE_SQL_DETAIL_ELAPSE_LIMIT` 옵션은 **imxtxn(네이티브 바이너리)** 전용이며, JSPD Java 코드에는 존재하지 않음
3. 2계층 필터 구조 확인: JSPD(Java) 필터 + imxtxn(Native) 필터가 독립적으로 동작
4. Exception SQL 우회 로직: `!bl &&` 조건이 있는지 확인 (bl=true이면 Exception SQL)
5. JEUS 재기동 후 imx.prop이 기본값으로 덮어쓰기되는지 재기동 스크립트 확인
6. DataGather 연결 전 XmProperties static 초기화가 먼저 실행되어 기본값(0)이 설정될 수 있음 — WAS ID 수신 시 복구됨
