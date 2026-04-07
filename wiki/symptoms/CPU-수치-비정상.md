# CPU 수치 비정상

## 관련 키워드
CPU 100배, CPU 퍼센트 초과, 스케일링 누락, 단위 변환 오류, 9850%, permille, raw 값, /100 누락, MFT, MFO

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-9284 | 현대차증권 | PeakVisor + MFT PlatformJS | v1.0.1.0-alpha.2 | MFT CPU 데이터가 100배 스케일 정수로 전송되지만 수신측에서 /100 변환 누락 | BinaryPaser_MFT_DBCPU_STAT.java:68-101, SendMFT2MFJStore.java:227 |

## 공통 패턴

## 조사 시 체크포인트
1. CPU 값이 100% 초과인지 확인 — 100배 스케일(permille x10) 전송 후 변환 누락 가능성
2. 동일 API를 다른 연계 제품(MFO, MFS 등)에서 호출할 때 정상인지 비교
3. 송신측(Send*Store.java)에서 100배 곱셈 여부 확인 — MFO는 명시적 `* 100.0`, MFT는 raw getStatIDX_cpuValue()
4. 수신측 바이너리 파서에서 /100 변환 여부 확인 — 디버그 로그에서만 나누고 실제 처리에 미반영되는 패턴 주의
5. PeakVisor(통합 대시보드) API 응답에서 연계 제품별 CPU 단위 정규화 여부 확인
