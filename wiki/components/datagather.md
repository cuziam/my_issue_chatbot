# DataGather

## 역할
JSPD Agent에서 수집된 데이터를 집계하고 처리하는 수집 서버. DGM(Master)과 DGS(Slave)로 구성되며, PostgreSQL/ClickHouse와 연동.

## 분석에서 발견된 주요 사항
| 이슈 | 발견 사항 | 관련 파일 |
|------|----------|----------|
| IMX-8586 | Tanzu/K8s 환경에서 checkTanzuStatus()가 주기적으로 만료 Pod 정리 시 remove_auto_id 프로시저의 서브쿼리 다중행 반환으로 PSQLException + NullPointerException 반복 발생 | XmWasIDManage.java:228-354, DGMMaster.java:1511-1597 |
| IMX-8972 | 자정 일변경 시 checkPartition()→analyze_pg_catalog() 실행 시 analyze_timeout=0(무제한)으로 장시간 ANALYZE 실행, 장기 운영(6년)으로 파티션 대량 누적 시 pg_catalog 비대화로 CPU 과부하 유발 | PostgresPartitionManage.java:47, DGMMaster.java:454, XmConfig.java:300 |

## 자주 관련되는 증상
- [로그 폭증](../symptoms/로그-폭증.md)
- [DB CPU 사용률 과다](../symptoms/DB-CPU-과부하.md)
