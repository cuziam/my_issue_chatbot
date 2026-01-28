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

## 편의 기능 개선 사항 (2025.01 업데이트)

1. **단일 스크립트 통합**: 아카이브 처리 로직(`process_archives`)이 메인 스크립트에 통합되었습니다.
2. **자동 압축 해제**: `.zip`, `.tar`, `.tar.gz` 파일을 자동으로 감지하여 해제 후 분석합니다.
3. **.NET 디컴파일 지원**: Java(JAR)뿐만 아니라 .NET(DLL) 에이전트도 자동으로 감지하여 `ilspycmd`로 디컴파일합니다.
4. **Git 통합**: 초기 설정 시 `.gitignore`를 생성하여 패키지 바이너리를 제외하고 소스만 관리하도록 돕습니다.

## 사용법

### Windows (PowerShell)

```powershell
# 대화형 모드 (패키지 목록에서 선택)
.\decompile.ps1

# 특정 패키지 지정 (압축 파일 또는 폴더)
.\decompile.ps1 -PackageName "package_v5.4.12.0-alpha.3.tar.gz"

# 덮어쓰기 강제 옵션
.\decompile.ps1 -OverwriteExisting $true
```

### Linux / Mac (Bash)

```bash
# 실행 권한 부여
chmod +x decompile.sh

# 대화형 모드
./decompile.sh

# 특정 패키지 지정
./decompile.sh -p "package_v5.4.12.0.tar.gz"
```

## Git 저장소 설정 (최초 1회)

스크립트와 함께 제공된 `init_git.bat` (Windows) 또는 `init_git.sh` (Linux)를 실행하여 Git 저장소를 초기화하고 `.gitignore`를 설정할 수 있습니다.

```bash
# Windows
.\init_git.bat

# Linux
./init_git.sh
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
