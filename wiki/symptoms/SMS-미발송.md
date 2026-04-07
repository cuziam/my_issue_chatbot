# SMS 미발송

## 관련 키워드
SMS, SMS_FLAG, 알람 미발송, 서버 알람 SMS, 문자 연동 실패, SMS_FLAG=0, smsJar, 알림 미전송, sms_server_list, autowasid SMS, SMS 매핑 누락

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-8895 | 하이닉스 | DataGather | 5.4.9.2 | ThreadMap.map_server_alert_sms_enable 로딩 결함으로 checkServerAlertSMSFlag()가 항상 false 반환, SMS_FLAG=0 저장 | AlertEnv.java:1004-1006, DGManager.java:2681-2702 |
| IMX-9643 | SSG | DataGather | 5.3 (2305) | autowasid On-Premise 모드로 WAS 추가 시 sms_server_list에 자동 매핑 INSERT 로직 부재 → 알람 발생하지만 SMS 수신자 미조회로 미발송 | pktAutoAssignWasId.java:169-195, XmWasIDOnpremiss.java |

## 공통 패턴
SMS 미발송의 근본 원인은 SMS 발송 판정/수신자 조회 시 필요한 데이터가 DB에 누락되는 것이다.
- **IMX-8895**: SMS_FLAG 판정 로직의 데이터 로딩 결함으로 SMS_FLAG=0 저장 → 발송 대상에서 제외
- **IMX-9643**: autowasid로 WAS 추가 시 sms_server_list 매핑 미등록 → 수신자 미조회로 미발송
- 공통적으로 알람 자체는 정상 동작하나, SMS 연동 경로에서 DB 레코드 누락이 원인

## 조사 시 체크포인트
1. XAPM_ALERT_HISTORY 테이블에서 SMS_FLAG 값 확인 (0이면 미발송)
2. XAPM_ALERT_CONFIG에 서버 알람 레코드 존재 여부 확인
3. XAPM_ALERT_VALUE에 USE_ALERT=true 설정 존재 여부 확인
4. smsJar 로그에서 발송 이력 확인
5. XmConfig.sms_type 설정값 확인 (SMS 연동 유형)
6. DataGather 버전 확인: v5.4.12 이상은 ServerAlertNotiConfigLoader(MyBatis 기반), 이하는 ThreadMap 기반
7. 게더 재기동 여부 확인 (Redis 테이블 시퀀스 동기화 필요)
8. sms_server_list 테이블에서 해당 server_id의 매핑 존재 여부 확인 (autowasid로 추가된 WAS는 미등록 가능)
9. autowasid 사용 환경인 경우 WAS 추가 후 SMS 매핑이 자동 등록되었는지 확인
