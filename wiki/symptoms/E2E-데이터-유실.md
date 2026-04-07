# E2E 데이터 유실 / 화면 멈춤

## 관련 키워드
E2E, EtoE, 데이터 유실, 화면 멈춤, pootprinter, StreamInput, boolean parsing error, unexpected byte, TCP 프로토콜, 바이트 정렬, 역직렬화, Netty, 거래량 급증, 채널 성능 지표 0

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-9483 | 신한은행 | pootprinter, DataGather | PlatformJS 5.3.221129.04 | 거래량 급증으로 pootprinter TCP 스트림 바이트 정렬 불일치 발생, boolean 파싱 시 GUID 문자열 바이트를 읽어 IllegalStateException. 내부 버퍼 손상이 재연결 후에도 지속되어 pootprinter 재기동 전까지 E2E 데이터 유실 | StreamInput.java:48-61, NettyTcpMessageChannelHandler, TxnDetail.readFrom:165 |

## 공통 패턴

## 조사 시 체크포인트
1. pootprinter 로그에서 `StreamInput boolean parsing error` 또는 `unexpected byte [0x..]` 에러 확인
2. 에러 발생 시점 전후 거래량 급증 여부 확인
3. DGM/PJS/DB 재기동이 아닌 **pootprinter 재기동**으로 해결되는지 확인
4. slave DataGather 노드와의 disconnect/reconnect 빈도가 비정상적으로 높은지 확인 (정상: 수분 간격, 비정상: 30초~1분 간격)
5. HEX DUMP에서 ASCII 문자열(GUID 등)이 boolean 위치에서 읽힌 흔적 확인
6. `Packet Type: -9` 등 비정상 패킷 타입 수신 여부 확인
