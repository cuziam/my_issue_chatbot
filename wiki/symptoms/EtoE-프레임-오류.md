# EtoE 프레임 오류

## 관련 키워드
EtoE, 액티브 트랜잭션, 프레임 오류, TypeError, trim, undefined, null, txnName, getSplitTxnData, 모니터링 불가, JavaScript 에러

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-9388 | 한국투자저축은행 | PlatformJS | 5.3.210715.01 | txnName이 null/undefined일 때 .trim() 호출로 TypeError 발생. WAS 화면은 .trim() 없어 정상, EtoE만 영향 | rtmEtoEActiveTransaction.js (getSplitTxnData) |

## 공통 패턴

## 조사 시 체크포인트
1. 브라우저 개발자 도구(F12) Console에서 `TypeError: Cannot read property 'trim' of undefined` 확인
2. WAS 액티브 트랜잭션 화면은 정상인지 비교 확인
3. 비정상 트랜잭션(txnName null, 255자 초과 등) 유입 여부 확인
4. `rtmEtoEActiveTransaction.js`의 `getSplitTxnData` 함수에서 null/undefined 방어 코드 유무 확인
5. 난독화 패키지의 경우 원본 소스 대조 필요
