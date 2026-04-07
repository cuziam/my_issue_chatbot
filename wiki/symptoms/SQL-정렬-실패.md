# SQL 정렬 실패

## 관련 키워드
SQL 문 정렬, SQL 포맷팅, sqlFormat, gudusoft, gsqlparser, NoClassDefFoundError, SQL 문 사라짐, SQL 정렬 버튼 동작 안함, SQLSERVER, T-SQL

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-9235 | HL만도 | PlatformJS | 5.4.8.2-patch.1 | SqlFormat.java에서 Oracle 벤더 하드코딩 → SQLSERVER 쿼리 파싱 실패. gudusoft gsqlparser static initializer 실패 시 JVM 재시작 전까지 전체 SQL 포맷팅 불가. 프론트엔드 에러 처리 미흡으로 SQL 텍스트 사라짐. | SqlFormat.java:28, SQLSyntax.java:98, SQLEditorBaseFrame.js:236-250 |

## 공통 패턴

## 조사 시 체크포인트
1. PJS 로그에 `NoClassDefFoundError: Could not initialize class gudusoft.gsqlparser.c` 에러 확인
2. `SqlFormat.java`에서 벤더 처리 방식 확인 — Oracle 고정인지 VENDER 순회 방식인지 (v5.4.12.0+에서 수정됨)
3. gudusoft `gsp.jar` 라이브러리 존재 여부 및 라이선스 파일 확인
4. PJS 재시작 후 재시도 — static initializer 실패 시 한 번 실패하면 JVM 재시작 전까지 복구 불가
5. 고객사 DB 타입 확인 — Oracle/DB2 외 타입(SQLSERVER, PostgreSQL, MariaDB)에서 발생 가능
6. 프론트엔드에서 SQL 텍스트 사라짐 여부 — `_onSQLFormattedData()`의 result 필드 검사 로직 유무
