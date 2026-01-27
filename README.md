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

1. **덮어쓰기 보호**: 출력 폴더나 추출된 폴더가 이미 존재할 경우 덮어쓸지 묻습니다. `all`을 입력하면 이후 모든 질문에 예(yes)로 답합니다.
2. **종료 옵션**: 패키지 선택 화면에서 `q`, `quit`, `exit`를 입력하여 종료할 수 있습니다.
3. **Bash 스크립트 업데이트**: Linux/macOS 환경 지원을 위해 `decompile_v2.sh`가 추가되었습니다. (기능은 PS1과 동일)

## 사용법

```powershell
# 대화형 모드 (패키지 목록에서 선택)
.\decompile.ps1

# 특정 패키지 지정 및 기존 파일 덮어쓰기 강제
.\decompile.ps1 -PackageName "package_v5.4.11.1" -OverwriteExisting $true

# 압축파일 직접 지정
.\decompile.ps1 -PackageName "package_v5.4.12.0-alpha.2.tar.gz"
```

### Linux / Git Bash

```bash
# 실행 권한 부여
chmod +x decompile_v2.sh

# 실행
./decompile_v2.sh

# 덮어쓰기 강제 옵션
./decompile_v2.sh --overwrite
```

## 주의사항
- `decompile.sh`는 구버전 파일일 수 있으므로 `decompile_v2.sh`를 사용하거나 이름을 변경하여 사용하세요.


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
