# 로그 폭증 (용량 급증)

## 관련 키워드
로그 폭증, 로그 용량 증가, log explosion, 로그 누적, 디스크 풀, NullPointerException, PSQLException, DB_IP, VARCHAR, 반복 에러, 에러 로그 대량 발생

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-8586 | 아모레퍼시픽 | DataGather | 231212.01 | remove_auto_id 프로시저의 서브쿼리가 다중행 반환 -> PSQLException -> NullPointerException 반복 기록 | XmWasIDManage.java:228-354, DGMMaster.java:1511-1597 |
| IMX-8586 | 아모레퍼시픽 | PlatformJS | 5.3.231227 | DBStatus 테이블 db_ip varchar(50)이 AWS RDS 엔드포인트(50자 초과)를 수용 못해 에러 로그 대량 발생 | DBStatus.java:30 |

## 공통 패턴

2건의 사례에서 공통 패턴:
- DB 컬럼 크기 부족이나 SQL 에러가 반복적으로 발생하여 에러 로그가 대량 누적
- 에러 자체는 기능 장애보다 로그 디스크 용량 소진이 실질적 위협
- 클라우드(AWS RDS, Kubernetes) 환경 특유의 긴 엔드포인트/동적 스케일링이 원인 제공

## 조사 시 체크포인트
1. DGM/PJS 로그 디렉토리에서 특정 에러 메시지가 반복 기록되는지 확인
2. 로그 파일 용량 증가 추이가 비정상적인지 확인 (24시간 기준)
3. PostgreSQL 프로시저에서 서브쿼리가 단일행을 전제하고 있는지 확인 (= vs IN)
4. DB 테이블 컬럼 크기가 실제 데이터 길이를 수용하는지 확인 (특히 AWS RDS 엔드포인트)
5. 에러 발생 후 cleanup/retry 과정에서 2차 에러(NPE 등)가 발생하는지 확인
6. H2 인메모리 DB의 경우 PJS 재시작 시 테이블 재생성 여부 확인
