# SQL 데이터 미수집

## 관련 키워드
SQL 미수집, SQL 수집 안 됨, SQL 수행시간 0, SQL 수행건수 0, RemoteCall 미수집, P Data 미생성, local.advice, 위빙 차단, weaving 차단, JSPD 업그레이드 후, oracle/*, -oracle/*, 제외 패턴, advice 파일

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-9452 | 한국신용정보원 | JSPD | 25.09.12.03 (= 2509.03) | IMX-9300 수정 과정에서 `l.a()` 메서드 시그니처 변경(4→3파라미터). local.advice의 `-oracle/*` 제외 패턴이 모든 클래스 위빙에 적용되도록 변경되어 Oracle JDBC SQL 위빙 차단 | org/bsp/weave/l.java:96-97, org/bsp/weave/i.java:127-133 |

## 공통 패턴

## 조사 시 체크포인트
1. `jspd.local.advice` 파일에 `-oracle/*`, `-com/*` 등 와일드카드 제외 패턴이 있는지 확인
2. JSPD 버전 업그레이드 이력 확인 — 이전 버전에서 정상이었는지
3. `org/bsp/weave/l.java`의 `a()` 메서드가 3파라미터(신버전)인지 4파라미터(구버전)인지 확인
4. JDBC advice map(`this.case`/`this.try`)에 Oracle JDBC 클래스가 등록되어 있는지 확인
5. 콜트리에서 메소드 유형 "SQL" 항목 존재 여부로 증상 확인
6. `-com/*` 설정 시 RemoteCall 관련 클래스도 차단되므로 P Data 생성 여부도 확인
7. 즉시 조치: `jspd.local.advice`에서 해당 제외 패턴 삭제 후 JSPD 재시작 (K8S 환경은 pod 재생성)
