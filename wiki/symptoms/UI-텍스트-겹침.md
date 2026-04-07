# UI 텍스트 겹침/잘림

## 관련 키워드
텍스트 겹침, 텍스트 잘림, text overlap, ellipsis, 박스 텍스트, CSS position absolute, 고정 너비, 한글 업무명, box_name, box_txn_name

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-9291 | 현대차증권 | PlatformJS | 5.4.12.0-alpha.2 | 고정 너비(146~148px) 박스 + box_txn_name의 position:absolute가 box_name과 겹침 유발 | txndetail.css:255-265, XMTransactionPath.js:1484-1491 |

## 공통 패턴

(2건 이상 사례 축적 시 작성)

## 조사 시 체크포인트
1. CSS에서 `position: absolute`로 배치된 텍스트 요소가 다른 요소와 겹치는지 확인
2. 박스/컨테이너의 너비가 고정값(px)으로 하드코딩되어 있는지 확인
3. 한글 등 넓은 글리프 문자에서 `text-overflow: ellipsis`가 과도하게 잘리는지 확인
4. `title` 속성(tooltip)이 제공되더라도 겹침으로 인해 가려지는지 확인
5. 배경 이미지(PNG) 기반 박스 디자인이 크기 조정을 제한하는지 확인
