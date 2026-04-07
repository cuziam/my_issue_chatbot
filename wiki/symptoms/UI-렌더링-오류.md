# UI 렌더링 오류

## 관련 키워드
텍스트 겹침, 텍스트 잘림, text overlap, ellipsis, 박스 텍스트, CSS position absolute, 고정 너비, 한글 업무명, box_name, box_txn_name, 노드 겹침, 경로 겹침, DB 노드, 트랜잭션 경로, node overlap, 레벨 계산, level, 자동 배치, 격자형 레이아웃, jsPlumb, createDesign, getBoxLevel, 화면 미표출, 대시보드 안 보임, 빈 화면, 렌더링 실패, SyntaxError, script 오류, JS 에러, view.html, 위젯 사라짐, 카드 사라짐, 깜빡임, 통합대시보드, 그룹 카드, disable 토글, 연계 제품 연결 실패, 빈 리스트, 레이아웃 유실, 토폴로지, 세로 크기, minHeight, 최소 높이, resize, 위젯 크기 고정, 대시보드 레이아웃, maxNodePosY, 크기 조절 불가, 스캐터 차트, 예외 트랜잭션, 색상, 파란색, 빨간색, exception, elapse, D3ScatterSelectable, 토글, 공백, 빈 칼럼, 업무명 공백, 거래코드 공백, business_id=0, 업무 미등록, getBusinessHierarchy, Comm.etoeBizInfos, X축, 시간 표시, 시간 포맷, timeformat, 추이분석, ComparisonTrend, CanvasChartForPa, 트리 구조, 노드 오배치, findNode, searchNode, DFS, 깊이 우선 탐색, ID 충돌, 네임스페이스 충돌, groupId, subGroupId, 하위그룹 중첩, 트리 그리드, exTree, BaseGridForPa, 에이전트 그룹

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 해결 방법 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|----------|
| IMX-9291 | 현대차증권 | PlatformJS | 5.4.12.0-alpha.2 | 고정 너비(146~148px) 박스 + box_txn_name의 position:absolute가 box_name과 겹침 유발 | 패치 (CSS/너비 조정) | txndetail.css:255-265, XMTransactionPath.js:1484-1491 |
| IMX-9317 | 한국신용정보원 | PlatformJS | 5.4.12.0-alpha.4 | 토폴로지뷰 getWordWrap() maxWidth=150px로 긴 그룹명이 잘려 줄바꿈 발생. 300px(2배)로 확대하여 개선 | 패치 (maxWidth 확대) | topology.js:3108 |
| IMX-9527 | 공통 | PlatformJS | 5.4.12.1-alpha.2 | 상단 탭 컨텍스트 메뉴에서 글자와 체크박스 겹침 + 체크 해제 박스 내부 라운드 이슈. PA 디자인 리뉴얼 시 미고려. | - | MainTabPanel.js:146-166 |
| IMX-9380 | 엔지니어링공제조합 | PlatformJS | 5.4.7.4 | DB 노드 레벨 계산 시 직접 호출 WAS만 고려하고 상위 WAS 미고려 → 같은 레벨에 DB 노드 밀집·겹침 | 패치 (상위 WAS 고려 로직 추가) | XMTransactionPath.js:337-372 (getBoxLevel), :1291-1545 (createDesign) |
| IMX-9532 | 롯데렌탈 | PlatformJS | 5.3.2502.06 | 패치 빌드 시 개발환경(pjs_sample/) 코드 혼입 → `<script>` 내부에 `<img>` 태그 삽입 → JS SyntaxError → 화면 렌더링 실패 | 패치 (불필요 태그 삭제) | RTM/view.html (패치본 line ~1065-1066) |
| IMX-9237 | HL만도 | PeakVisor | v1.0.0.5-alpha.0 | 연계 제품 API 실패 시 캐시 빈 리스트 전파 + disable 상태 빠른 토글로 카드 레이아웃 자체 유실 | - | ApiProcessor.java:74-98, LinkInfoProvider.java:31-69, CacheScheduler.java:58-108 |
| IMX-9503 | ABL생명 | PlatformJS | 5.4.12.0 | topology.js resize()에서 maxNodePosY를 최소 높이로 강제하여 노드 위치 이하로 축소 불가 | 패치 (minHeight 600→300) | topology.js:2453-2467, rtmTopologyView.js:90-105 |
| IMX-9365 | HL만도 | PlatformJS | Client 5.4.8.2-patch.1 | PA 스캐터 차트가 예외 여부를 exception 필드가 아닌 elapse 부호로 판단하여, elapse≥0인 예외 트랜잭션이 파란색(정상)으로 표시됨 | 패치 (exception 필드 기반 판단으로 변경) | D3ScatterSelectable.js:239 |
| IMX-9565 | 현대차증권 | PlatformJS, DataGather | 5.4.12.1-alpha3 | 업무 미등록(BUSINESS_ID=0) 또는 업무 삭제 시 getBusinessHierarchy()가 빈 객체 반환 → 업무그룹/업무/세부업무 3개 칼럼 공백 | 패치 (business_id=0 제외 쿼리) | TxnSummaryHeatmap.js:1551-1646, CommonRTM.java:426-479 |
| IMX-9525 | 공통 | PlatformJS | 5.4.13.0-alpha.2 | PA 추이분석 화면별 X축 시간 포맷 불일치: 일반 추이(`%d %H:%M`), 비교 추이(인덱스 모드 시간만), RTM(`%H:%M:%S`→`%H:%M` 동적 변경) | - | CanvasChartForPa.js:295, ComparisonTrend.js:1444-1454, rtmChartFrame.js:155,608 |
| IMX-9474 | ABL생명 | PlatformJS | 5.4.12.0 | groupId와 subGroupId가 동일 네임스페이스로 트리에 저장되어 DFS findNode가 잘못된 노드 반환 → 하위그룹이 다른 하위그룹 아래 중첩 배치 | 패치 (ID 네임스페이스 분리) | config_agentGroup.js:616-644, BaseGridForPa.js:3390-3440 |

## 하위 증상 분류
- **텍스트 겹침/잘림**: 고정 너비 박스, absolute 포지셔닝, maxWidth 부족 등으로 텍스트가 겹치거나 잘리는 현상 (IMX-9291, IMX-9317, IMX-9527)
- **노드/경로 겹침**: 트랜잭션 경로 등에서 노드 레벨 계산 오류로 노드가 밀집·겹침 (IMX-9380)
- **화면 미표출**: JS 문법 에러 등으로 전체 화면이 렌더링되지 않는 현상 (IMX-9532)
- **위젯 사라짐/깜빡임**: 연계 서버 불안정 시 캐시 전파로 위젯이 사라지는 현상 (IMX-9237)
- **위젯 크기 조절 불가**: 내부 요소 크기 강제로 축소 불가 (IMX-9503)
- **차트 색상 불일치**: 데이터 판단 로직 오류로 차트 색상이 잘못 표시 (IMX-9365)
- **칼럼 공백 표시**: 메타데이터 미등록/삭제로 칼럼이 공백으로 표시 (IMX-9565)
- **X축 시간 표시 불일치**: 화면별 시간 포맷이 통일되지 않은 현상 (IMX-9525)
- **트리 노드 오배치**: ID 네임스페이스 충돌 + DFS 탐색으로 노드가 잘못된 부모에 배치 (IMX-9474)

## 공통 패턴

- **고정 너비 하드코딩**: 텍스트 표시 영역의 너비가 px 단위 고정값으로 설정되어, 긴 텍스트(특히 한글)에서 잘림/줄바꿈 발생. 해결 시 고정값을 늘리거나 동적 계산으로 전환.
- **Canvas/CSS 기반 텍스트 렌더링**: Canvas measureText() 또는 CSS text-overflow로 텍스트 잘림을 처리하나, 한글 글리프 폭을 충분히 고려하지 않음.
- **JavaScript TypeError로 화면 장애**: 신규 기능 추가나 패치 시 코드 혼입/함수 미정의로 TypeError가 발생하여 전체 화면 렌더링이 중단되는 패턴.

## 조사 시 체크포인트
1. CSS에서 `position: absolute`로 배치된 텍스트 요소가 다른 요소와 겹치는지 확인
2. 박스/컨테이너의 너비가 고정값(px)으로 하드코딩되어 있는지 확인
3. 한글 등 넓은 글리프 문자에서 `text-overflow: ellipsis`가 과도하게 잘리는지 확인
4. 브라우저 F12 Console에서 `SyntaxError: Unexpected token` 에러가 있는지 확인
5. view.html (RTM/PA/Config) 내 `<script>` 블록 안에 HTML 태그가 혼입되어 있지 않은지 확인
6. 패치 적용 후 화면 미표출이면 원본 view.html과 라인 수 비교 (불필요한 코드 혼입 여부 판단)
7. 연계 제품 서버(MFS, APM 등)의 네트워크 연결 상태 확인
8. Caffeine 캐시 TTL 만료 시 빈 리스트로 전파되는지 확인
9. topology.js의 resize() 함수에서 componentHeight와 resizeHeight(maxNodePosY) 비교 로직 확인
10. 스캐터 차트의 색상 판단 로직이 `exception` 필드를 사용하는지, `elapse` 부호를 사용하는지 확인
11. 해당 화면에서 표시하는 칼럼이 별도 등록/설정이 필요한 메타데이터인지 확인
12. 각 화면의 차트 모드 확인: 시간 모드(`mode: 'time'`) vs 인덱스 모드(`onIndexValue: true`)
13. 트리 그리드에서 서로 다른 엔티티의 ID가 동일 컬럼에 저장되는지 확인
14. `findNode`/`searchNode`가 DFS로 첫 번째 매칭을 반환하는지 확인 — ID 충돌 시 잘못된 노드 반환 가능
