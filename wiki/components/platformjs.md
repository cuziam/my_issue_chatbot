# PlatformJS

## 역할
InterMax의 웹 UI 및 REST API를 제공하는 Spring 기반 컴포넌트. 프론트엔드(intermax/)와 백엔드(com.exem.platform/)로 구성.

## 분석에서 발견된 주요 사항
| 이슈 | 발견 사항 | 관련 파일 |
|------|----------|----------|
| IMX-9291 | 트랜잭션 경로 박스의 고정 너비 + absolute 포지셔닝으로 텍스트 겹침. 배경 이미지(PNG) 기반 디자인이 크기 조정 제약. | txndetail.css:255-265, XMTransactionPath.js:1484-1491, XMEtoETransactionPath.js:1441-1448 |
| IMX-8586 | Scale in/out 시 Comm.serviceid 미초기화 상태에서 autoScale 호출, .join() TypeError로 RTM 무한 로딩 | ServerScale.js:62, IMXWSWorker.js:1688-1725 |
| IMX-8586 | DBStatus 테이블 db_ip varchar(50)이 AWS RDS 엔드포인트를 수용 못해 에러 로그 대량 발생 | DBStatus.java:30 |

## 자주 관련되는 증상
- [UI 텍스트 겹침/잘림](../symptoms/ui-text-overlap.md)
- [무한 로딩](../symptoms/infinite-loading.md)
- [로그 폭증](../symptoms/log-explosion.md)
