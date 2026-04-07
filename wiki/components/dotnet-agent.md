# .NET Agent

## 역할
Windows IIS/.NET 환경에서 CLR Profiling API를 이용한 바이트코드 위빙으로 트랜잭션 데이터를 수집하는 에이전트. Java 환경의 JSPD에 대응하는 .NET 전용 컴포넌트.

## 분석에서 발견된 주요 사항
| 이슈 | 발견 사항 | 관련 파일 |
|------|----------|----------|
| IMX-9606 | CLR Profiler의 JIT instrumentation이 대규모 .NET 앱에서 CPU 200% 유발. 4개 타이머 스레드가 각각 100ms sleep으로 busy-waiting. PerformanceCounter 프로세스 순회 부하. | Intermax.Profiler.x64.dll, XmNetAgent.cs:106-120, PerformanceManager.cs:112-179, DgClient.cs:264-286 |

## 자주 관련되는 증상
- [에이전트 CPU 과부하](../symptoms/에이전트-CPU-과부하.md)
