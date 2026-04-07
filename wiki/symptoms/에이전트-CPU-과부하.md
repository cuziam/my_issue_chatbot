# 에이전트 CPU 과부하

## 관련 키워드
CPU 200%, CPU 과부하, 에이전트 CPU, .NET 에이전트, CLR Profiler, JIT instrumentation, w3wp, IIS, 프로파일링 오버헤드, busy-waiting

## 과거 사례
| 이슈 | 고객사 | 컴포넌트 | 버전 | 근본 원인 요약 | 핵심 파일 |
|------|--------|----------|------|--------------|----------|
| IMX-9606 | HD현대인프라코어 | .NET Agent | InterMax_DotNet_2602.03 | CLR Profiler의 JIT 리컴파일 시 바이트코드 주입 오버헤드 (enable_trycatch + trace_code_depth=5) | Intermax.Profiler.x64.dll, XmNetAgent.cs:106-120 |

## 공통 패턴

## 조사 시 체크포인트
1. 에이전트 적용 전후 대상 프로세스(w3wp.exe 등)의 CPU 사용률 비교
2. profile.conf의 `enable_trycatch`, `enable_static`, `trace_code_depth` 설정 확인
3. calltree.advice의 계측 대상 범위 확인
4. net.conf의 `DISABLE_PERFORMANCE_COUNTER` 설정 확인
5. 타이머 스레드 sleep 간격 (100ms busy-waiting 패턴) 확인
6. 참조 이슈 IMX-4671(우리은행) 패치 적용 여부 확인
