# X축 시간 표시 불일치

## 관련 키워드
X축, 시간 표시, 시간 포맷, timeformat, 추이분석, 차트, 통일, 비교분석, ComparisonTrend, CanvasChartForPa

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-9525 | 공통 | PlatformJS | 5.4.13.0-alpha.2 | PA 추이분석 화면별 X축 시간 포맷 불일치: 일반 추이(`%d %H:%M`), 비교 추이(인덱스 모드 시간만), RTM(`%H:%M:%S`→`%H:%M` 동적 변경), WAS Workload(`H` 시 단위) | CanvasChartForPa.js:295, ComparisonTrend.js:1444-1454, rtmChartFrame.js:155,608 |

## 조사 시 체크포인트
1. `CanvasChartForPa.js`의 기본 timeformat 설정 확인 (`%d %H:%M`)
2. 각 화면의 차트 모드 확인: 시간 모드(`mode: 'time'`) vs 인덱스 모드(`onIndexValue: true`)
3. DisplayTimeMode 설정 확인: HM, H, HMS, YM 등 (`Envir.js:72-79`)
4. 비교분석 화면은 여러 날짜를 겹쳐 표시하므로 인덱스 모드가 의도적 설계일 수 있음
5. RTM 차트의 동적 timeformat 변경 로직 확인 (`rtmChartFrame.js`)
6. `chartProperty` 옵션에서 개별 화면의 `xaxisTimeFormat` 오버라이드 여부 확인
