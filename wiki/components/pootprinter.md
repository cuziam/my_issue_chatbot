# pootprinter

## 역할
E2E(End-to-End) 트랜잭션 데이터를 slave DataGather 노드로부터 Netty TCP 연결로 수신하여 집계하는 프로세스. 채널별 성능 지표(초당 처리 건수, 평균수행시간)를 산출하여 DGM/PJS에 전달.

## 분석에서 발견된 주요 사항
| 이슈 | 발견 사항 | 관련 파일 |
|------|----------|----------|
| IMX-9483 | 거래량 급증 시 TCP 스트림 바이트 정렬 불일치로 TxnDetail 역직렬화 실패. readBoolean()에서 0x00/0x01이 아닌 값(GUID 문자열 바이트) 수신 시 IllegalStateException. 내부 손상 상태가 재연결 후에도 초기화되지 않아 pootprinter 재기동 필요. was_add_server 정보를 WebSocket으로 1건씩 호출 → 배열로 변경하여 부하 감소. | StreamInput.java:48-61, NettyTcpMessageChannelHandler, pktTxnDetail.java |

## 자주 관련되는 증상
- [E2E 데이터 유실 / 화면 멈춤](../symptoms/E2E-데이터-유실.md)
- [EtoE 프레임 오류](../symptoms/EtoE-프레임-오류.md)
