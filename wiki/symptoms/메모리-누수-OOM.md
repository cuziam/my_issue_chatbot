# 메모리 누수 / OOM (Out of Memory)

## 관련 키워드
메모리 누수, OOM, OutOfMemory, Heap, Old 영역, ConcurrentHashMap, 캐시 Map, 클래스로더, HotDeploy, GC root, Retained Size

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-9480 | 현대차증권 | JSPD | 2509.03 | HotDeploy 환경에서 `org.bsp.weave.b.c`의 ConcurrentHashMap에 ByteBuddy auxiliary 클래스가 무한 누적 (remove 로직 부재) | org/bsp/weave/b/c.java:21-29, org/bsp/weave/i.java:144 |

## 조사 시 체크포인트
1. 힙 덤프에서 JSPD 관련 객체(org.bsp.weave, com.exem.jspd)의 Retained Size 확인
2. ConcurrentHashMap 엔트리 수가 비정상적으로 큰지 확인 (수십만~수백만 개)
3. HotDeploy/클래스로더 교체가 반복되는 환경인지 확인
4. ByteBuddy 등 동적 프록시 프레임워크가 임시 클래스를 생성하는지 확인
5. `jspd.local.advice` 제외 패턴이 올바르게 설정되었는지 확인 (중간 `*`는 와일드카드가 아닌 리터럴로 처리됨)
6. 제외 패턴 형식: `prefix*`(접두사), `*middle*`(포함), `?regex`(정규식) — 중간 경로 `*`는 미지원
