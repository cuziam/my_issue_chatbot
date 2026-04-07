# DB CPU 사용률 과다

## 관련 키워드
CPU 사용률, CPU 과부하, PostgreSQL, DB 부하, 자정, 일변경, partition, vacuum, analyze, pg_catalog, 배치 작업, 성능 저하

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-8972 | 한국가스공사 | DataGather | 5.2 | 자정 일변경 시 자동 배치 작업(파티션 생성/ANALYZE/Summary/VACUUM) 중 analyze_timeout=0(무제한)으로 pg_catalog ANALYZE가 장시간 실행, 6년 운영으로 파티션 대량 누적 | PostgresPartitionManage.java:47, DGMMaster.java:454, XmConfig.java:300 |

## 공통 패턴

## 조사 시 체크포인트
1. `pg_stat_activity`에서 `state='active'`인 장시간 실행 쿼리 확인
2. 게더 로그에서 `[PARTITION]`, `[VACUUM]`, `[ANALYZE_PG_CATALOG]`, `[SUMMARY]` 키워드 확인
3. 게더 설정에서 `analyze_timeout` 값 확인 (기본값 0 = 무제한)
4. `analyze_pg_catalog` 설정 확인 (기본값 true)
5. `enable_vacuum` 설정 확인
6. 파티션 테이블 누적 수량 확인 (장기 운영 환경일수록 pg_catalog 비대화)
7. PostgreSQL 버전 및 autovacuum 설정 확인
8. `top` 명령어로 postgres 프로세스 CPU 점유율 확인
