# 무한 로딩 (화면 진입 시)

## 관련 키워드
무한 로딩, infinite loading, 로딩 멈춤, 화면 진입 불가, TypeError, undefined, join, 서비스 선택, RTM, 실시간 모니터링, Scale in/out, autoScale, serviceid

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-8586 | 아모레퍼시픽 | PlatformJS | 5.3.231227 | Scale in/out 반복 시 Comm.serviceid 미초기화 상태에서 autoScale -> getServerList 호출, .join() TypeError 발생 | ServerScale.js:62, IMXWSWorker.js:1688-1725 |

## 공통 패턴

(2건 이상 사례 축적 시 작성)

## 조사 시 체크포인트
1. 브라우저 개발자 도구(F12) Console에서 TypeError 또는 undefined 관련 에러가 반복 발생하는지 확인
2. WebSocket 메시지(AUTO_ID_STATUS 등) 수신 시점에 필요한 변수가 초기화되어 있는지 확인
3. Kubernetes/Tanzu 등 Scale in/out 환경에서 자동 스케일 관련 로직이 비동기 초기화와 경합하는지 확인
4. 서비스 선택 전에 주기적/자동 호출되는 함수가 서비스 ID를 전제하고 있는지 확인
5. 에러 카운트가 지속 증가하는지 확인 (화면 전체가 멈추는 것이 아니라 반복 호출에 의한 에러 누적)
