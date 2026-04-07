# PeakVisor

## 역할
EXEM의 통합 모니터링 대시보드 제품. 여러 연계 제품(InterMax/APM, MaxGauge for SQLServer, MaxGauge for Oracle 등)의 데이터를 통합 대시보드로 표시한다.

## 분석에서 발견된 주요 사항
| 이슈 | 발견 사항 | 관련 파일 |
|------|----------|----------|
| IMX-9237 | disable 상태가 origin 단위로 관리되어, 동일 origin의 여러 API 중 하나만 성공해도 전체 enabled로 전환됨. 네트워크 불안정 시 빠른 토글 발생 | ApiProcessor.java:74-98, LinkInfoProvider.java:31-69 |
| IMX-9237 | CacheScheduler가 1~3초 간격으로 다수 API 호출, 캐시 TTL 만료 시 빈 리스트 전파로 프론트엔드 카드 유실 | CacheScheduler.java:58-108, MFSCacheProcessor.java:69-79 |
| IMX-9284 | MFT 연동 시 CPU 데이터가 100배 스케일 raw 값으로 표시됨. MFO는 API 레벨에서 정규화되지만 MFT는 미적용 | BinaryPaser_MFT_DBCPU_STAT.java:68-101, MFOCacheProcessor.java (참고 패턴) |
| IMX-9310 | 위젯 설정에 차트 표시유형(Line/Bar/Pie) 추가. DB에 display_type, display_option 컬럼 추가(v1.0.1.0-alpha.1), 프론트엔드 차트설정+미리보기 구현(alpha.2). QA 중 Bar 차트 showValueOnBar 옵션이 실제 값 대신 0으로 표시되는 버그 발견 → alpha.3에서 수정 확인 | PUT/POST/GET /api/v1/peakvisor/config/widget (displayType, displayOption 필드) |
| IMX-9371 | 토폴로지뷰 xview 드래그 시 InterMax 타입별 트랜잭션 이동 기능. CD 타입에서 CDM→CD 정규화 누락으로 "지원하지 않습니다" 토스트 표시(v1.0.1.0-alpha.3). alpha.4에서 CDM→CD 정규화 적용 후 PASS. LOG 에이전트 목록 미출력은 InterMax 수집서버 API 변경 필요(IMX-9617 별도 진행). | PeakVisor 프론트엔드 (v1.0.0.5 분석 패키지에 미포함, 직접 확인 불가) |
| IMX-9458 | PeakVisor→InterMax RTM 연계 시 에이전트/그룹 자동 필터링 기능 추가. PeakVisor가 URL에 wasid(타겟 모드) 또는 groupName(그룹 모드)을 포함하여 InterMax RTM을 호출하면, RTM 측에서 LNB 자동 선택 + 모니터 탭 자동 전환(WAS>TP>TUX>WEB>CD>LOG 우선순위). PeakVisor 측 URL 생성은 IMX-9529로 별도 진행. | InterMax RTM 측: urlConnects.js, baseView.js, rtmView.js, LinkedManager.js |
| IMX-9529 | IMX-9458 후속. 현대차증권 환경에 통합대시보드→InterMax 연계 URL 별도 반영. 타겟 위젯·성능 지표 목록 연계 + 그룹 위젯 연계 확인(v1.0.1.0-alpha.3). 그룹 연계 시 에이전트 타입 우선순위(WAS>TP>TUX>WEB>CD>PHP>PYTHON>LOG) 적용은 5.4.13.0-alpha.2부터 지원. | PeakVisor 프론트엔드 (minified, rtmConnect 키워드 확인) |
| IMX-9575 | IAM 인사정보 연동용 외부 Account API(/api/v1/peakvisor/external/users) 구현. UserInfo CRUD 4종 + JWT 인증(login/refresh/encode). UserGroup 미지원(합의). 사용자 삭제 시 cascade에서 xm_link_config FK 누락 → v1.0.1.0-alpha.4에서 마이그레이션 수정. | AuthController.java, ConfigController.java, AuthService.java, ConfigService.java, JwtTokenProvider.java, RsaCipher.java |

## 자주 관련되는 증상
- [위젯 사라짐/깜빡임](../symptoms/위젯-사라짐.md)
- [CPU 수치 비정상](../symptoms/CPU-수치-비정상.md)
- [연계 타입 불일치](../symptoms/연계-타입-불일치.md)
