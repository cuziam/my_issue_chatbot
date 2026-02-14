# InterMax Decompiler Script
# Decompile JAR files (Java) and DLL files (.NET) from InterMax packages
# Supports: archive extraction (tar.gz, tar, zip), folder processing
# Usage: .\decompile.ps1 [-PackageName "package_v5.4.11.1"] [-DeleteArchives $true]

param(
    [string]$PackageName = "",
    [string]$BaseDir = "",
    [bool]$DeleteArchives = $true,
    [bool]$OverwriteExisting = $false,
    [bool]$NonInteractive = $false
)

$ErrorActionPreference = "Stop"

#region Helper Functions

function Prompt-Overwrite {
    param([string]$Path)
    
    if ($NonInteractive) { return $OverwriteExisting }
    if ($OverwriteExisting) { return $true }
    
    Write-Host "  [!] Target already exists: $Path" -ForegroundColor Yellow
    $choice = Read-Host "  Do you want to overwrite? (y/n/all)"
    
    if ($choice -eq "all") {
        $script:OverwriteExisting = $true
        return $true
    }
    return ($choice -eq "y" -or $choice -eq "yes")
}

function Resolve-BaseDir {
    param([string]$BaseDir)
    if (-not [string]::IsNullOrEmpty($BaseDir)) { return $BaseDir }
    # Use parent directory of script location (project root)
    if ($PSScriptRoot) { return (Split-Path $PSScriptRoot -Parent) }
    return (Get-Location).Path
}

function Get-ArchiveBaseName {
    param([Parameter(Mandatory=$true)][string]$FileName)
    $name = $FileName
    if ($name -match '\.tar\.gz$') { return $name -replace '\.tar\.gz$', '' }
    if ($name -match '\.tgz$') { return $name -replace '\.tgz$', '' }
    if ($name -match '\.tar$') { return $name -replace '\.tar$', '' }
    if ($name -match '\.zip$') { return $name -replace '\.zip$', '' }
    return [System.IO.Path]::GetFileNameWithoutExtension($name)
}

function Test-IsArchive {
    param([Parameter(Mandatory=$true)][string]$Path)
    $ext = $Path.ToLowerInvariant()
    return $ext.EndsWith('.zip') -or $ext.EndsWith('.tar') -or $ext.EndsWith('.tar.gz') -or $ext.EndsWith('.tgz')
}

function Ensure-EmptyOrOverwrite {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][bool]$Overwrite
    )
    if (-not (Test-Path $Path)) { return $true }
    
    $shouldOverwrite = $Overwrite
    if (-not $shouldOverwrite) {
        $shouldOverwrite = Prompt-Overwrite -Path $Path
    }

    if (-not $shouldOverwrite) {
        Write-Host "  -> Skipping: $Path (User cancelled)" -ForegroundColor Gray
        return $false
    }
    
    Remove-Item -LiteralPath $Path -Recurse -Force
    return $true
}

function Convert-TarPath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return "" }
    $sanitized = $Path -replace '\\', '/'
    while ($sanitized.StartsWith('./')) {
        $sanitized = $sanitized.Substring(2)
    }
    return $sanitized.TrimStart('/')
}

function Get-SafeDestinationPath {
    param(
        [Parameter(Mandatory=$true)][string]$DestinationRoot,
        [Parameter(Mandatory=$true)][string]$EntryName
    )

    $relative = Convert-TarPath -Path $EntryName
    if ([string]::IsNullOrWhiteSpace($relative)) {
        return $DestinationRoot
    }

    $relative = $relative -replace '/', [System.IO.Path]::DirectorySeparatorChar
    $relative = $relative.TrimStart([System.IO.Path]::DirectorySeparatorChar)
    $combined = Join-Path $DestinationRoot $relative
    $fullPath = [System.IO.Path]::GetFullPath($combined)

    if (-not $fullPath.StartsWith($DestinationRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Tar entry path escapes extraction root: $EntryName"
    }

    return $fullPath
}

function Resolve-LinkTargetPath {
    param(
        [Parameter(Mandatory=$true)][string]$DestinationRoot,
        [Parameter(Mandatory=$true)][string]$EntryName,
        [string]$LinkEntryName
    )

    if ([string]::IsNullOrWhiteSpace($LinkEntryName)) {
        return $null
    }

    $relativeEntry = Convert-TarPath -Path $EntryName
    $entryDir = if ([string]::IsNullOrWhiteSpace($relativeEntry)) { "" } else { [System.IO.Path]::GetDirectoryName($relativeEntry -replace '/', [System.IO.Path]::DirectorySeparatorChar) }
    if (-not $entryDir) { $entryDir = "" }

    $linkRelative = Convert-TarPath -Path $LinkEntryName
    $linkRelative = $linkRelative -replace '/', [System.IO.Path]::DirectorySeparatorChar

    if (-not $linkRelative) { return $null }

    if ([System.IO.Path]::IsPathRooted($linkRelative)) {
        $linkRelative = $linkRelative.TrimStart([System.IO.Path]::DirectorySeparatorChar)
    } elseif ($entryDir) {
        $linkRelative = Join-Path $entryDir $linkRelative
    }

    return Get-SafeDestinationPath -DestinationRoot $DestinationRoot -EntryName $linkRelative
}

function Copy-LinkTargetContent {
    param(
        [Parameter(Mandatory=$true)][string]$TargetPath,
        [Parameter(Mandatory=$true)][string]$DestinationPath
    )

    if (-not (Test-Path $TargetPath -PathType Leaf)) {
        return $false
    }

    $parent = [System.IO.Path]::GetDirectoryName($DestinationPath)
    if ($parent) {
        [System.IO.Directory]::CreateDirectory($parent) | Out-Null
    }

    Copy-Item -LiteralPath $TargetPath -Destination $DestinationPath -Force
    return $true
}

function Extract-TarArchiveSafe {
    param(
        [Parameter(Mandatory=$true)][string]$ArchivePath,
        [Parameter(Mandatory=$true)][string]$DestinationDir
    )

    $destinationRoot = [System.IO.Path]::GetFullPath($DestinationDir)
    if (-not (Test-Path $destinationRoot)) {
        New-Item -ItemType Directory -Path $destinationRoot -Force | Out-Null
    }

    # Check if .NET System.Formats.Tar API is available (PowerShell 7+ on .NET 7+)
    $hasTarApi = $false
    try {
        [void][System.Formats.Tar.TarEntryType]
        $hasTarApi = $true
    } catch { }

    if ($hasTarApi) {
        Extract-TarWithDotNet -ArchivePath $ArchivePath -DestinationRoot $destinationRoot
    } else {
        Extract-TarWithExe -ArchivePath $ArchivePath -DestinationRoot $destinationRoot
    }
}

function Extract-TarWithExe {
    param(
        [Parameter(Mandatory=$true)][string]$ArchivePath,
        [Parameter(Mandatory=$true)][string]$DestinationRoot
    )

    $tarExe = Get-Command tar.exe -ErrorAction SilentlyContinue
    if (-not $tarExe) {
        throw "tar extraction unavailable: System.Formats.Tar API not found (requires PowerShell 7+ on .NET 7+) and tar.exe not found in PATH."
    }

    Write-Host "  -> Using tar.exe (System.Formats.Tar API not available)" -ForegroundColor Gray

    # Capture stderr separately - Windows tar.exe fails on symlinks (no admin privilege)
    # but continues extracting regular files, so we tolerate those errors
    $oldEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $tarOutput = & $tarExe.Source -xf $ArchivePath -C $destinationRoot 2>&1
    $tarExit = $LASTEXITCODE
    $ErrorActionPreference = $oldEAP

    # Check if anything was extracted despite symlink errors
    $extractedItems = @(Get-ChildItem -Path $destinationRoot -ErrorAction SilentlyContinue)
    if ($tarExit -ne 0 -and $extractedItems.Count -eq 0) {
        throw "tar extraction failed with exit code: $tarExit"
    }

    if ($tarExit -ne 0) {
        # Count symlink-related warnings
        $symlinkErrors = @($tarOutput | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] })
        if ($symlinkErrors.Count -gt 0) {
            Write-Host "  -> Skipped $($symlinkErrors.Count) symlink(s) (Windows limitation, non-critical)" -ForegroundColor Yellow
        }
    }
}

function Extract-TarWithDotNet {
    param(
        [Parameter(Mandatory=$true)][string]$ArchivePath,
        [Parameter(Mandatory=$true)][string]$DestinationRoot
    )

    $lower = $ArchivePath.ToLowerInvariant()
    $needsDecompress = $lower.EndsWith('.tar.gz') -or $lower.EndsWith('.tgz')
    $tempTarPath = $ArchivePath
    $cleanupTar = $false

    if ($needsDecompress) {
        $tempTarPath = [System.IO.Path]::GetTempFileName()
        $cleanupTar = $true
        $inputStream = [System.IO.File]::OpenRead($ArchivePath)
        $gzipStream = [System.IO.Compression.GZipStream]::new($inputStream, [System.IO.Compression.CompressionMode]::Decompress, $false)
        $outputStream = [System.IO.File]::Create($tempTarPath)
        $gzipStream.CopyTo($outputStream)
        $outputStream.Dispose()
        $gzipStream.Dispose()
        $inputStream.Dispose()
    }

    $fileEntries = @(
        [System.Formats.Tar.TarEntryType]::V7RegularFile,
        [System.Formats.Tar.TarEntryType]::RegularFile,
        [System.Formats.Tar.TarEntryType]::ContiguousFile
    )

    $linkEntries = @(
        [System.Formats.Tar.TarEntryType]::HardLink,
        [System.Formats.Tar.TarEntryType]::SymbolicLink,
        [System.Formats.Tar.TarEntryType]::RenamedOrSymlinked
    )

    $fileStream = [System.IO.File]::OpenRead($tempTarPath)
    $reader = [System.Formats.Tar.TarReader]::new($fileStream, $false)

    try {
        while ($true) {
            $entry = $reader.GetNextEntry()
            if ($null -eq $entry) { break }

            if ([string]::IsNullOrWhiteSpace($entry.Name)) { continue }
            $destinationPath = Get-SafeDestinationPath -DestinationRoot $DestinationRoot -EntryName $entry.Name

            if ($entry.EntryType -eq [System.Formats.Tar.TarEntryType]::Directory) {
                [System.IO.Directory]::CreateDirectory($destinationPath) | Out-Null
                continue
            }

            if ($fileEntries -contains $entry.EntryType) {
                $parent = [System.IO.Path]::GetDirectoryName($destinationPath)
                if ($parent) {
                    [System.IO.Directory]::CreateDirectory($parent) | Out-Null
                }

                if ($null -ne $entry.DataStream) {
                    if ($entry.DataStream.CanSeek) {
                        $entry.DataStream.Seek(0, [System.IO.SeekOrigin]::Begin) | Out-Null
                    }
                    $outFile = [System.IO.File]::Create($destinationPath)
                    $entry.DataStream.CopyTo($outFile)
                    $outFile.Dispose()
                }
                continue
            }

            if ($linkEntries -contains $entry.EntryType) {
                $targetPath = Resolve-LinkTargetPath -DestinationRoot $DestinationRoot -EntryName $entry.Name -LinkEntryName $entry.LinkEntryName
                if ($targetPath -and (Copy-LinkTargetContent -TargetPath $targetPath -DestinationPath $destinationPath)) {
                    continue
                }

                Write-Host "  -> Skipped link entry (target unavailable): $($entry.Name)" -ForegroundColor Yellow
                continue
            }

            # Skip unsupported entry types silently
        }
    } finally {
        $reader.Dispose()
        $fileStream.Dispose()
        if ($cleanupTar -and (Test-Path $tempTarPath)) {
            Remove-Item -LiteralPath $tempTarPath -Force
        }
    }
}

function Extract-Archive {
    param(
        [Parameter(Mandatory=$true)][string]$ArchivePath,
        [Parameter(Mandatory=$true)][string]$DestinationDir
    )
    if (-not (Test-Path $DestinationDir)) {
        New-Item -ItemType Directory -Path $DestinationDir -Force | Out-Null
    }
    $lower = $ArchivePath.ToLowerInvariant()
    if ($lower.EndsWith('.zip')) {
        Expand-Archive -LiteralPath $ArchivePath -DestinationPath $DestinationDir -Force
        return
    }
    if ($lower.EndsWith('.tar') -or $lower.EndsWith('.tar.gz') -or $lower.EndsWith('.tgz')) {
        Extract-TarArchiveSafe -ArchivePath $ArchivePath -DestinationDir $DestinationDir
        return
    }
    throw "Unsupported archive type: $ArchivePath"
}

function Get-RootCandidates {
    param([Parameter(Mandatory=$true)][string]$PackageDir)
    $candidates = @()
    
    # Add the package root itself as a candidate
    if (Test-Path $PackageDir -PathType Container) {
        $candidates += (Get-Item $PackageDir)
    }

    $level1 = @(Get-ChildItem -Path $PackageDir -Directory -ErrorAction SilentlyContinue)
    $candidates += $level1
    foreach ($dir in $level1) {
        $level2 = @(Get-ChildItem -Path $dir.FullName -Directory -ErrorAction SilentlyContinue)
        $candidates += $level2
    }
    $seen = @{}
    $unique = @()
    foreach ($d in $candidates) {
        if (-not $seen.ContainsKey($d.FullName)) {
            $seen[$d.FullName] = $true
            $unique += $d
        }
    }
    return $unique
}

function Score-RootCandidate {
    param([Parameter(Mandatory=$true)]$Dir)
    $path = $Dir.FullName
    $name = $Dir.Name
    $score = 0

    if ($name -like "InterMax*") { $score += 2 }
    if ($name -ieq "intermax") { $score += 2 }
    if ($name -like "intermax_v*") { $score += 2 }

    # Collector markers
    if (Test-Path (Join-Path $path "DGServer_M")) { $score += 10 }
    if (Test-Path (Join-Path $path "PlatformJS")) { $score += 10 }
    if (Test-Path (Join-Path $path "Database")) { $score += 6 }
    if (Test-Path (Join-Path $path "script")) { $score += 4 }
    if (Test-Path (Join-Path $path "jspd\jspd.jar")) { $score += 6 }
    if (Test-Path (Join-Path $path "ant")) { $score += 3 }

    # Java agent markers
    if (Test-Path (Join-Path $path "jspd\lib\jspd.jar")) { $score += 6 }

    # .NET agent markers
    if (Test-Path (Join-Path $path "dotnet\binary")) { $score += 8 }
    if (Test-Path (Join-Path $path "dotnet\binary\InterMax.NetAgent.dll")) { $score += 10 }
    if (Test-Path (Join-Path $path "dotnet\binary\core")) { $score += 8 }

    # JDK markers
    if (Test-Path (Join-Path $path "zulu11")) { $score += 2 }
    if (Test-Path (Join-Path $path "zulu8")) { $score += 2 }
    if (Test-Path (Join-Path $path "zulu7")) { $score += 2 }
    if (Test-Path (Join-Path $path "zulu6")) { $score += 2 }

    return $score
}

function Get-IntermaxRoot {
    param([Parameter(Mandatory=$true)][string]$PackageDir)
    $candidates = Get-RootCandidates -PackageDir $PackageDir
    if (-not $candidates -or $candidates.Count -eq 0) { return $null }

    $best = $null
    $bestScore = -1
    foreach ($c in $candidates) {
        $score = Score-RootCandidate -Dir $c
        if ($score -gt $bestScore) {
            $best = $c
            $bestScore = $score
        }
    }
    if ($bestScore -le 0) { return $null }
    return $best
}

function Get-PackageType {
    param([Parameter(Mandatory=$true)][string]$RootPath)

    # Collector: DGServer_M or PlatformJS
    if ((Test-Path (Join-Path $RootPath "DGServer_M")) -or (Test-Path (Join-Path $RootPath "PlatformJS"))) {
        return "collector"
    }
    # Java Agent
    if (Test-Path (Join-Path $RootPath "jspd\lib\jspd.jar")) {
        return "agent"
    }
    # Collector with jspd
    if (Test-Path (Join-Path $RootPath "jspd\jspd.jar")) {
        return "collector"
    }
    # .NET Agent (Framework)
    if (Test-Path (Join-Path $RootPath "dotnet\binary\InterMax.NetAgent.dll")) {
        return "dotnet-agent"
    }
    # .NET Core Agent
    if (Test-Path (Join-Path $RootPath "dotnet\binary\core")) {
        $coreDlls = Get-ChildItem -Path (Join-Path $RootPath "dotnet\binary\core") -Recurse -Filter "InterMax.*.dll" -ErrorAction SilentlyContinue
        if ($coreDlls -and $coreDlls.Count -gt 0) {
            return "dotnet-core-agent"
        }
    }
    return "unknown"
}

#endregion

#region Decompiler Setup

function Ensure-JavaAvailable {
    param([string]$IntermaxPath)
    
    $JAVA_CMD = $null
    
    # Priority 1: Zulu JDK from package
    $ZULU_PATHS = @(
        (Join-Path $IntermaxPath "zulu11\bin\java.exe"),
        (Join-Path $IntermaxPath "zulu8\bin\java.exe"),
        (Join-Path $IntermaxPath "zulu7\bin\java.exe"),
        (Join-Path $IntermaxPath "zulu6\bin\java.exe")
    )
    foreach ($zuluPath in $ZULU_PATHS) {
        if (Test-Path $zuluPath) {
            $JAVA_CMD = $zuluPath
            Write-Host "  -> Found Zulu JDK from package: $JAVA_CMD" -ForegroundColor Green
            return $JAVA_CMD
        }
    }

    # Priority 2: JAVA_HOME
    if ($env:JAVA_HOME -and (Test-Path "$env:JAVA_HOME\bin\java.exe")) {
        $JAVA_CMD = "$env:JAVA_HOME\bin\java.exe"
        Write-Host "  -> Found host Java via JAVA_HOME: $JAVA_CMD" -ForegroundColor Green
        return $JAVA_CMD
    }

    # Priority 3: PATH
    $javaInPath = Get-Command java.exe -ErrorAction SilentlyContinue
    if ($javaInPath) {
        $JAVA_CMD = $javaInPath.Source
        Write-Host "  -> Found host Java in PATH: $JAVA_CMD" -ForegroundColor Green
        return $JAVA_CMD
    }

    # Priority 4: Common installation paths
    $commonPaths = @(
        "C:\Program Files\Java\*\bin\java.exe",
        "C:\Program Files (x86)\Java\*\bin\java.exe",
        "C:\Program Files\Eclipse Adoptium\*\bin\java.exe",
        "C:\Program Files\Zulu\*\bin\java.exe",
        "C:\Program Files\Microsoft\*\bin\java.exe"
    )
    foreach ($pattern in $commonPaths) {
        $found = Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            $JAVA_CMD = $found.FullName
            Write-Host "  -> Found host Java at: $JAVA_CMD" -ForegroundColor Green
            return $JAVA_CMD
        }
    }

    return $null
}

function Ensure-ILSpyAvailable {
    param([string]$ToolsDir)
    
    $ILSPY_DIR = Join-Path $ToolsDir "ilspycmd"
    $ILSPY_EXE = Join-Path $ILSPY_DIR "ilspycmd.exe"
    
    if (Test-Path $ILSPY_EXE) {
        Write-Host "  -> ILSpyCMD already exists: $ILSPY_EXE" -ForegroundColor Green
        return $ILSPY_EXE
    }

    # Install via dotnet tool
    $dotnet = Get-Command dotnet.exe -ErrorAction SilentlyContinue
    if (-not $dotnet) {
        Write-Host "  -> dotnet CLI not found. Cannot install ILSpyCMD." -ForegroundColor Red
        Write-Host "  -> Please install .NET SDK from: https://dotnet.microsoft.com/download" -ForegroundColor Yellow
        return $null
    }

    Write-Host "  -> Installing ILSpyCMD..." -ForegroundColor Gray
    try {
        & $dotnet.Source tool install ilspycmd --tool-path $ILSPY_DIR --version 9.0.0.7889-preview2
        if (Test-Path $ILSPY_EXE) {
            Write-Host "  -> ILSpyCMD installed: $ILSPY_EXE" -ForegroundColor Green
            return $ILSPY_EXE
        }
    } catch {
        Write-Host "  -> Failed to install ILSpyCMD: $_" -ForegroundColor Red
    }
    return $null
}

function Ensure-CfrAvailable {
    param([string]$ToolsDir)
    
    $CFR_VERSION = "0.152"
    $CFR_URL = "https://github.com/leibnitz27/cfr/releases/download/$CFR_VERSION/cfr-$CFR_VERSION.jar"
    $CFR_JAR = Join-Path $ToolsDir "cfr-$CFR_VERSION.jar"

    if (-not (Test-Path $ToolsDir)) {
        New-Item -ItemType Directory -Path $ToolsDir | Out-Null
    }

    if (Test-Path $CFR_JAR) {
        Write-Host "  -> CFR already exists: $CFR_JAR" -ForegroundColor Green
        return $CFR_JAR
    }

    Write-Host "  -> Downloading CFR $CFR_VERSION..." -ForegroundColor Gray
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $CFR_URL -OutFile $CFR_JAR -UseBasicParsing
        Write-Host "  -> Download complete: $CFR_JAR" -ForegroundColor Green
        return $CFR_JAR
    } catch {
        Write-Host "  -> Download failed: $_" -ForegroundColor Red
        return $null
    }
}

#endregion

#region JAR/DLL Definitions

$COLLECTOR_JAR_FILES = @(
    @{ Name = "datagather"; Paths = @("DGServer_M\bin\datagather.jar", "DGServer_M\bin\DGServer.jar"); OutputRelativePath = "decompiled\datagather" },
    @{ Name = "PlatformJS"; Paths = @("PlatformJS\bin\PlatformJS.jar", "PlatformJS\bin\exem_platformjs.jar"); OutputRelativePath = "decompiled\PlatformJS" },
    @{ Name = "exem_platformjs"; Paths = @("PlatformJS\svc\www\WEB-INF\lib\exem_platformjs.jar", "PlatformJS\svc\www\WEB-INF\lib\exem_platformjs.jar.ori", "PlatformJS\bin\exem_platformjs.jar"); OutputRelativePath = "decompiled\exem_platformjs" },
    @{ Name = "jspd"; Paths = @("jspd\jspd.jar"); OutputRelativePath = "decompiled\jspd" }
)

$AGENT_JAR_FILES = @(
    @{ Name = "jspd"; Paths = @("jspd\lib\jspd.jar"); OutputRelativePath = "decompiled\jspd" }
)

$DOTNET_AGENT_DLL_FILES = @(
    @{ Name = "InterMax.NetAgent"; Paths = @("dotnet\binary\InterMax.NetAgent.dll"); OutputRelativePath = "decompiled\InterMax.NetAgent" }
)

$DOTNET_CORE_AGENT_DLL_FILES = @(
    @{ Name = "InterMax.NetAgent.Core.6.0"; Paths = @("dotnet\binary\core\6.0\InterMax.NetAgent.Core.dll"); OutputRelativePath = "decompiled\InterMax.NetAgent.Core.6.0" },
    @{ Name = "InterMax.NetAgent.Core.8.0"; Paths = @("dotnet\binary\core\8.0\InterMax.NetAgent.Core.dll"); OutputRelativePath = "decompiled\InterMax.NetAgent.Core.8.0" },
    @{ Name = "InterMax.Startup.Hook"; Paths = @("dotnet\binary\core\startup\InterMax.Startup.Hook.dll"); OutputRelativePath = "decompiled\InterMax.Startup.Hook" }
)

#endregion

#region Decompile Functions

function Decompile-JarFiles {
    param(
        [string]$JavaCmd,
        [string]$CfrJar,
        [string]$IntermaxPath,
        [array]$JarFiles
    )

    $decompiled = 0
    $skipped = 0

    foreach ($jarInfo in $JarFiles) {
        $name = $jarInfo.Name
        $found = $false
        $jarPath = $null

        foreach ($path in $jarInfo.Paths) {
            $fullPath = Join-Path $IntermaxPath $path
            if (Test-Path $fullPath) {
                $jarPath = $fullPath
                $found = $true
                break
            }
        }

        if (-not $found) {
            Write-Host "  [$name] File not found - skipping" -ForegroundColor Gray
            $skipped++
            continue
        }

        $outputPath = Join-Path $IntermaxPath $jarInfo.OutputRelativePath

        if (-not (Ensure-EmptyOrOverwrite -Path $outputPath -Overwrite $script:OverwriteExisting)) {
            $skipped++
            continue
        }
        New-Item -ItemType Directory -Path $outputPath -Force | Out-Null

        $jarSize = [math]::Round((Get-Item $jarPath).Length / 1MB, 2)
        Write-Host "  [$name] Decompiling JAR (${jarSize}MB)..." -ForegroundColor White

        $start = Get-Date
        $process = Start-Process -FilePath $JavaCmd -ArgumentList @(
            "-jar", "`"$CfrJar`"",
            "`"$jarPath`"",
            "--outputdir", "`"$outputPath`""
        ) -NoNewWindow -Wait -PassThru

        $elapsed = [math]::Round(((Get-Date) - $start).TotalSeconds, 1)

        if ($process.ExitCode -eq 0) {
            $fileCount = (Get-ChildItem -Path $outputPath -Recurse -Filter "*.java" | Measure-Object).Count
            Write-Host "  [$name] Done! ${fileCount} .java files created (${elapsed}s)" -ForegroundColor Green
            $decompiled++
        } else {
            Write-Host "  [$name] Failed (Exit Code: $($process.ExitCode))" -ForegroundColor Red
        }
    }

    return @{ Decompiled = $decompiled; Skipped = $skipped }
}

function Decompile-DllFiles {
    param(
        [string]$ILSpyExe,
        [string]$IntermaxPath,
        [array]$DllFiles
    )

    $decompiled = 0
    $skipped = 0

    foreach ($dllInfo in $DllFiles) {
        $name = $dllInfo.Name
        $found = $false
        $dllPath = $null

        foreach ($path in $dllInfo.Paths) {
            $fullPath = Join-Path $IntermaxPath $path
            if (Test-Path $fullPath) {
                $dllPath = $fullPath
                $found = $true
                break
            }
        }

        if (-not $found) {
            Write-Host "  [$name] File not found - skipping" -ForegroundColor Gray
            $skipped++
            continue
        }

        $outputPath = Join-Path $IntermaxPath $dllInfo.OutputRelativePath

        if (-not (Ensure-EmptyOrOverwrite -Path $outputPath -Overwrite $script:OverwriteExisting)) {
            $skipped++
            continue
        }
        New-Item -ItemType Directory -Path $outputPath -Force | Out-Null

        $dllSize = [math]::Round((Get-Item $dllPath).Length / 1KB, 2)
        Write-Host "  [$name] Decompiling DLL (${dllSize}KB)..." -ForegroundColor White

        $start = Get-Date
        $process = Start-Process -FilePath $ILSpyExe -ArgumentList @(
            "`"$dllPath`"",
            "-p",
            "-o", "`"$outputPath`""
        ) -NoNewWindow -Wait -PassThru

        $elapsed = [math]::Round(((Get-Date) - $start).TotalSeconds, 1)

        if ($process.ExitCode -eq 0) {
            $fileCount = (Get-ChildItem -Path $outputPath -Recurse -Filter "*.cs" | Measure-Object).Count
            Write-Host "  [$name] Done! ${fileCount} .cs files created (${elapsed}s)" -ForegroundColor Green
            $decompiled++
        } else {
            Write-Host "  [$name] Failed (Exit Code: $($process.ExitCode))" -ForegroundColor Red
        }
    }

    return @{ Decompiled = $decompiled; Skipped = $skipped }
}

#endregion

#region Main Script

# Set base directory
$BaseDir = Resolve-BaseDir -BaseDir $BaseDir
$TOOLS_DIR = Join-Path $BaseDir "tools"
$PACKAGES_DIR = Join-Path $BaseDir "packages"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " InterMax Decompiler" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check packages directory
if (-not (Test-Path $PACKAGES_DIR)) {
    Write-Host "  Packages directory not found: $PACKAGES_DIR" -ForegroundColor Red
    Write-Host "  Please create 'packages' folder and place packages inside." -ForegroundColor Yellow
    exit 1
}

# List available packages/archives if not specified
if ([string]::IsNullOrEmpty($PackageName)) {
    Write-Host "  Available packages in 'packages' folder:" -ForegroundColor Yellow
    Write-Host ""

    $items = Get-ChildItem -Path $PACKAGES_DIR | Where-Object {
        $_.PSIsContainer -or (Test-IsArchive -Path $_.Name)
    } | Where-Object { $_.Name -ne "_incoming" }

    if ($items.Count -eq 0) {
        Write-Host "  No packages found in: $PACKAGES_DIR" -ForegroundColor Red
        exit 1
    }

    $index = 1
    foreach ($item in $items) {
        $type = if ($item.PSIsContainer) { "[DIR]" } else { "[ARC]" }
        Write-Host "  [$index] $type $($item.Name)" -ForegroundColor White
        $index++
    }

    Write-Host "  [q] Quit" -ForegroundColor DarkGray
    Write-Host ""
    $selection = Read-Host "  Select package number (or enter name)"

    if ($selection -eq "q" -or $selection -eq "quit" -or $selection -eq "exit") {
        Write-Host "  Goodbye." -ForegroundColor Gray
        exit 0
    }

    if ($selection -match '^\d+$') {
        $selectedIndex = [int]$selection - 1
        if ($selectedIndex -ge 0 -and $selectedIndex -lt $items.Count) {
            $PackageName = $items[$selectedIndex].Name
        } else {
            Write-Host "  Invalid selection!" -ForegroundColor Red
            exit 1
        }
    } else {
        $PackageName = $selection
    }
}

# Validate package path
$PACKAGE_PATH = Join-Path $PACKAGES_DIR $PackageName

if (-not (Test-Path $PACKAGE_PATH)) {
    Write-Host "  Package not found: $PACKAGE_PATH" -ForegroundColor Red
    exit 1
}

# Handle archive files - extract first
$isArchive = Test-IsArchive -Path $PackageName
if ($isArchive) {
    Write-Host ""
    Write-Host "[EXTRACT] Processing archive: $PackageName" -ForegroundColor Yellow

    $archiveBaseName = Get-ArchiveBaseName -FileName $PackageName
    $incomingWorkRoot = Join-Path $PACKAGES_DIR "_incoming"
    if (-not (Test-Path $incomingWorkRoot)) {
        New-Item -ItemType Directory -Path $incomingWorkRoot -Force | Out-Null
    }

    $workDir = Join-Path $incomingWorkRoot ("{0}_{1}" -f $archiveBaseName, (Get-Date -Format 'yyyyMMdd_HHmmssfff'))
    New-Item -ItemType Directory -Path $workDir -Force | Out-Null

    try {
        Write-Host "  -> Extracting..." -ForegroundColor Gray
        Extract-Archive -ArchivePath $PACKAGE_PATH -DestinationDir $workDir

        $topDirs = @(Get-ChildItem -Path $workDir -Directory -ErrorAction SilentlyContinue)
        $topFiles = @(Get-ChildItem -Path $workDir -File -ErrorAction SilentlyContinue)

        # Ensure destination is always packages/ArchiveBaseName
        $extractedPackageName = $archiveBaseName
        $packageDest = Join-Path $PACKAGES_DIR $extractedPackageName

        if (-not (Ensure-EmptyOrOverwrite -Path $packageDest -Overwrite:$OverwriteExisting)) {
             # Cleanup work dir if user skipped
             Remove-Item -LiteralPath $workDir -Recurse -Force
             exit 0
        }
        New-Item -ItemType Directory -Path $packageDest -Force | Out-Null

        # If archive contains exactly one folder AND that folder matches the archive name (roughly),
        # move contents of that folder to dest to avoid double nesting (pkg/pkg/...)
        # Otherwise, move everything in workDir to dest (pkg/...)
        
        $shouldFlatten = $false
        if ($topDirs.Count -eq 1 -and $topFiles.Count -eq 0) {
            $innerDirName = $topDirs[0].Name
            # Normalize for comparison
            if ($innerDirName -eq $extractedPackageName) {
                $shouldFlatten = $true
            }
        }

        if ($shouldFlatten) {
            Write-Host "  -> Flattening single directory: $($topDirs[0].Name)" -ForegroundColor Gray
            Get-ChildItem -Path $topDirs[0].FullName -Force | ForEach-Object {
                Move-Item -LiteralPath $_.FullName -Destination $packageDest
            }
        } else {
            Get-ChildItem -Path $workDir -Force | ForEach-Object {
                Move-Item -LiteralPath $_.FullName -Destination $packageDest
            }
        }

        Write-Host "  -> Extracted to: $extractedPackageName" -ForegroundColor Green
        $PACKAGE_PATH = $packageDest
        $PackageName = $extractedPackageName

        if ($DeleteArchives) {
            $archivePath = Join-Path $PACKAGES_DIR (Get-ArchiveBaseName -FileName $PackageName)
            # Delete original archive
            $originalArchive = Join-Path $PACKAGES_DIR ((Get-ChildItem -Path $PACKAGES_DIR -File | Where-Object { (Get-ArchiveBaseName -FileName $_.Name) -eq $extractedPackageName -and (Test-IsArchive -Path $_.Name) }).Name)
            if ($originalArchive -and (Test-Path $originalArchive)) {
                Remove-Item -LiteralPath $originalArchive -Force
                Write-Host "  -> Removed archive: $originalArchive" -ForegroundColor Gray
            }
        }
    } finally {
        if (Test-Path $workDir) {
            try {
                Remove-Item -LiteralPath $workDir -Recurse -Force -ErrorAction Stop
            } catch {
                # File lock from antivirus/indexer - retry once after short delay
                Start-Sleep -Milliseconds 500
                try {
                    Remove-Item -LiteralPath $workDir -Recurse -Force -ErrorAction Stop
                } catch {
                    Write-Host "  -> Warning: Could not fully clean temp dir (file locked by another process)" -ForegroundColor Yellow
                    Write-Host "  -> You can manually delete: $workDir" -ForegroundColor Yellow
                }
            }
        }
    }
}

# Find InterMax root folder
$INTERMAX_DIR = Get-IntermaxRoot -PackageDir $PACKAGE_PATH

if (-not $INTERMAX_DIR) {
    Write-Host "  InterMax root folder not found in package: $PACKAGE_PATH" -ForegroundColor Red
    Write-Host "  Hint: expected to find one of: InterMax*, intermax, intermax_v* or dotnet\binary" -ForegroundColor Yellow
    exit 1
}

$INTERMAX_PATH = $INTERMAX_DIR.FullName
$PACKAGE_TYPE = Get-PackageType -RootPath $INTERMAX_PATH

if ($PACKAGE_TYPE -eq "unknown") {
    Write-Host "  Could not determine package type from root: $INTERMAX_PATH" -ForegroundColor Red
    Write-Host "  Hint: expected collector markers (DGServer_M/PlatformJS), agent marker (jspd\lib\jspd.jar), or .NET marker (dotnet\binary)" -ForegroundColor Yellow
    exit 1
}

$OUTPUT_DIR = Join-Path $INTERMAX_PATH "decompiled"

Write-Host ""
Write-Host "  Base Directory: $BaseDir" -ForegroundColor Gray
Write-Host "  Package: $PackageName" -ForegroundColor Gray
Write-Host "  InterMax: $($INTERMAX_DIR.Name)" -ForegroundColor Gray
Write-Host "  Type: $PACKAGE_TYPE" -ForegroundColor Gray
Write-Host ""

$totalStart = Get-Date
$totalDecompiled = 0
$totalSkipped = 0

# Process based on package type
switch ($PACKAGE_TYPE) {
    "collector" {
        Write-Host "[1/3] Checking Java..." -ForegroundColor Yellow
        $JAVA_CMD = Ensure-JavaAvailable -IntermaxPath $INTERMAX_PATH
        if (-not $JAVA_CMD) {
            Write-Host "  -> Java not found! Please install Java JDK 11 or higher." -ForegroundColor Red
            exit 1
        }

        Write-Host ""
        Write-Host "[2/3] Preparing CFR decompiler..." -ForegroundColor Yellow
        $CFR_JAR = Ensure-CfrAvailable -ToolsDir $TOOLS_DIR
        if (-not $CFR_JAR) { exit 1 }

        Write-Host ""
        Write-Host "[3/3] Decompiling JAR files..." -ForegroundColor Yellow
        $result = Decompile-JarFiles -JavaCmd $JAVA_CMD -CfrJar $CFR_JAR -IntermaxPath $INTERMAX_PATH -JarFiles $COLLECTOR_JAR_FILES
        $totalDecompiled = $result.Decompiled
        $totalSkipped = $result.Skipped
    }
    "agent" {
        Write-Host "[1/3] Checking Java..." -ForegroundColor Yellow
        $JAVA_CMD = Ensure-JavaAvailable -IntermaxPath $INTERMAX_PATH
        if (-not $JAVA_CMD) {
            Write-Host "  -> Java not found! Please install Java JDK 11 or higher." -ForegroundColor Red
            exit 1
        }

        Write-Host ""
        Write-Host "[2/3] Preparing CFR decompiler..." -ForegroundColor Yellow
        $CFR_JAR = Ensure-CfrAvailable -ToolsDir $TOOLS_DIR
        if (-not $CFR_JAR) { exit 1 }

        Write-Host ""
        Write-Host "[3/3] Decompiling JAR files..." -ForegroundColor Yellow
        $result = Decompile-JarFiles -JavaCmd $JAVA_CMD -CfrJar $CFR_JAR -IntermaxPath $INTERMAX_PATH -JarFiles $AGENT_JAR_FILES
        $totalDecompiled = $result.Decompiled
        $totalSkipped = $result.Skipped
    }
    "dotnet-agent" {
        Write-Host "[1/2] Preparing ILSpyCMD decompiler..." -ForegroundColor Yellow
        $ILSPY_EXE = Ensure-ILSpyAvailable -ToolsDir $TOOLS_DIR
        if (-not $ILSPY_EXE) { exit 1 }

        Write-Host ""
        Write-Host "[2/2] Decompiling DLL files..." -ForegroundColor Yellow
        $result = Decompile-DllFiles -ILSpyExe $ILSPY_EXE -IntermaxPath $INTERMAX_PATH -DllFiles $DOTNET_AGENT_DLL_FILES
        $totalDecompiled = $result.Decompiled
        $totalSkipped = $result.Skipped
    }
    "dotnet-core-agent" {
        Write-Host "[1/2] Preparing ILSpyCMD decompiler..." -ForegroundColor Yellow
        $ILSPY_EXE = Ensure-ILSpyAvailable -ToolsDir $TOOLS_DIR
        if (-not $ILSPY_EXE) { exit 1 }

        Write-Host ""
        Write-Host "[2/2] Decompiling DLL files..." -ForegroundColor Yellow
        $result = Decompile-DllFiles -ILSpyExe $ILSPY_EXE -IntermaxPath $INTERMAX_PATH -DllFiles $DOTNET_CORE_AGENT_DLL_FILES
        $totalDecompiled = $result.Decompiled
        $totalSkipped = $result.Skipped
    }
}

$totalElapsed = [math]::Round(((Get-Date) - $totalStart).TotalSeconds, 1)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Decompiled: $totalDecompiled" -ForegroundColor White
Write-Host "  Skipped:    $totalSkipped" -ForegroundColor White
Write-Host "  Total time: ${totalElapsed}s" -ForegroundColor White
Write-Host ""
Write-Host "  Output: $OUTPUT_DIR" -ForegroundColor Yellow
Write-Host ""

#endregion
