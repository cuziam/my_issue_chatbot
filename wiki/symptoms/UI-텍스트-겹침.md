# UI 텍스트 겹침/잘림

## 관련 키워드
텍스트 겹침, 텍스트 잘림, text overlap, ellipsis, 박스 텍스트, CSS position absolute, 고정 너비, 한글 업무명, box_name, box_txn_name

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-9291 | 현대차증권 | PlatformJS | 5.4.12.0-alpha.2 | 고정 너비(146~148px) 박스 + box_txn_name의 position:absolute가 box_name과 겹침 유발 | txndetail.css:255-265, XMTransactionPath.js:1484-1491 |
| IMX-9317 | 한국신용정보원 | PlatformJS | 5.4.12.0-alpha.4 | 토폴로지뷰 getWordWrap() maxWidth=150px로 긴 그룹명이 잘려 줄바꿈 발생. 300px(2배)로 확대하여 개선 | topology.js:3108 |
| IMX-9527 | 공통 | PlatformJS | 5.4.12.1-alpha.2 | 상단 탭 컨텍스트 메뉴에서 글자와 체크박스 겹침 + 체크 해제 박스 내부 라운드 이슈. PA 디자인 리뉴얼 시 미고려. | MainTabPanel.js:146-166 |

## 공통 패턴

- **고정 너비 하드코딩**: 텍스트 표시 영역의 너비가 px 단위 고정값으로 설정되어, 긴 텍스트(특히 한글)에서 잘림/줄바꿈 발생. 해결 시 고정값을 늘리거나 동적 계산으로 전환.
- **Canvas/CSS 기반 텍스트 렌더링**: Canvas measureText() 또는 CSS text-overflow로 텍스트 잘림을 처리하나, 한글 글리프 폭을 충분히 고려하지 않음.

## 조사 시 체크포인트
1. CSS에서 `position: absolute`로 배치된 텍스트 요소가 다른 요소와 겹치는지 확인
2. 박스/컨테이너의 너비가 고정값(px)으로 하드코딩되어 있는지 확인
3. 한글 등 넓은 글리프 문자에서 `text-overflow: ellipsis`가 과도하게 잘리는지 확인
4. `title` 속성(tooltip)이 제공되더라도 겹침으로 인해 가려지는지 확인
5. 배경 이미지(PNG) 기반 박스 디자인이 크기 조정을 제한하는지 확인
