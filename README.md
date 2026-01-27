# InterMax Decompiler

InterMax 패키지(Java JAR, .NET DLL)를 디컴파일하는 스크립트입니다.

## 요구사항

### Java 패키지 (collector, agent)
- **Java JDK 11+** (Adoptium 권장: https://adoptium.net/)
- 또는 패키지 내 포함된 Zulu JDK 사용

### .NET 패키지 (dotnet-agent, dotnet-core-agent)
- **.NET SDK 6.0+** (https://dotnet.microsoft.com/download)
- ILSpyCMD가 자동 설치됨

### 압축 파일 처리
- Windows 10+ 기본 tar.exe (tar.gz, tar 파일용)
- PowerShell 내장 Expand-Archive (zip 파일용)

## 사용법

```powershell
# 대화형 모드 (패키지 목록에서 선택)
.\decompile.ps1

# 특정 패키지 지정
.\decompile.ps1 -PackageName "package_v5.4.11.1"

# 압축파일 직접 지정 (자동 압축해제 후 디컴파일)
.\decompile.ps1 -PackageName "package_v5.4.12.0-alpha.2.tar.gz"
```

## 지원 패키지 타입

| 타입 | 설명 | 디컴파일 대상 |
|------|------|---------------|
| collector | InterMax 서버 | datagather.jar, PlatformJS.jar, jspd.jar |
| agent | Java 에이전트 | jspd.jar |
| dotnet-agent | .NET Framework 에이전트 | InterMax.NetAgent.dll |
| dotnet-core-agent | .NET Core 에이전트 | InterMax.NetAgent.Core.dll, InterMax.Startup.Hook.dll |

## 출력 위치

디컴파일된 소스는 각 패키지 내 `decompiled/` 폴더에 생성됩니다.

```
packages/
└── package_v5.4.11.1/
    └── InterMax_v5.4/
        └── decompiled/
            ├── datagather/     # .java 파일들
            ├── PlatformJS/
            └── jspd/
```

## 폴더 구조

```
jar-decompiler/
├── decompile.ps1      # 메인 스크립트
├── packages/          # 패키지 폴더 (압축파일도 여기에)
└── tools/             # 디컴파일러 (CFR, ILSpyCMD)
```
