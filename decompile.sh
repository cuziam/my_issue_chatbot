#!/bin/bash
# InterMax Decompiler Script (Bash)
# Decompile JAR files (Java) and DLL files (.NET) from InterMax packages
# Supports: archive extraction (tar.gz, tar, zip), folder processing

set -e

# --- Configuration ---
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
BASE_DIR="${BASE_DIR:-$SCRIPT_DIR}"
PACKAGES_DIR="$BASE_DIR/packages"
TOOLS_DIR="$BASE_DIR/tools"
CFR_VERSION="0.152"
CFR_URL="https://github.com/leibnitz27/cfr/releases/download/$CFR_VERSION/cfr-$CFR_VERSION.jar"
CFR_JAR="$TOOLS_DIR/cfr-$CFR_VERSION.jar"

OVERWRITE_EXISTING=false
DELETE_ARCHIVES=true
PACKAGE_NAME=""

# --- Helper Functions ---

log_info() { echo -e "\033[36m$1\033[0m"; }
log_warn() { echo -e "\033[33m$1\033[0m"; }
log_err() { echo -e "\033[31m$1\033[0m"; }
log_success() { echo -e "\033[32m$1\033[0m"; }
log_debug() { echo -e "\033[90m$1\033[0m"; }

prompt_overwrite() {
    local path="$1"
    if [ "$OVERWRITE_EXISTING" = true ]; then
        return 0
    fi
    
    log_warn "  [!] Target already exists: $path"
    read -p "  Do you want to overwrite? (y/n/all) " choice
    case "$choice" in 
        y|Y|yes|YES) return 0 ;;
        all|ALL) OVERWRITE_EXISTING=true; return 0 ;;
        *) return 1 ;;
    esac
}

ensure_empty_or_overwrite() {
    local path="$1"
    if [ ! -e "$path" ]; then return 0; fi
    
    if prompt_overwrite "$path"; then
        rm -rf "$path"
        return 0
    else
        log_debug "  -> Skipping: $path (User cancelled)"
        return 1
    fi
}

get_archive_basename() {
    local filename="$1"
    if [[ "$filename" =~ \.tar\.gz$ ]]; then echo "${filename%.tar.gz}"; return; fi
    if [[ "$filename" =~ \.tgz$ ]]; then echo "${filename%.tgz}"; return; fi
    if [[ "$filename" =~ \.tar$ ]]; then echo "${filename%.tar}"; return; fi
    if [[ "$filename" =~ \.zip$ ]]; then echo "${filename%.zip}"; return; fi
    echo "$filename"
}

is_archive() {
    local filename="$1"
    local lower=$(echo "$filename" | tr '[:upper:]' '[:lower:]')
    [[ "$lower" == *.zip || "$lower" == *.tar || "$lower" == *.tar.gz || "$lower" == *.tgz ]]
}

extract_archive() {
    local archive_path="$1"
    local dest_dir="$2"
    
    mkdir -p "$dest_dir"
    local lower=$(echo "$archive_path" | tr '[:upper:]' '[:lower:]')
    
    if [[ "$lower" == *.zip ]]; then
        unzip -q -o "$archive_path" -d "$dest_dir"
    elif [[ "$lower" == *.tar || "$lower" == *.tar.gz || "$lower" == *.tgz ]]; then
        tar -xf "$archive_path" -C "$dest_dir"
    else
        log_err "Unsupported archive type: $archive_path"
        exit 1
    fi
}

find_cmd() {
    command -v "$1" >/dev/null 2>&1
}

# --- Main Logic ---

# Parse args
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -p|--package)
        PACKAGE_NAME="$2"
        shift; shift
        ;;
        -o|--overwrite)
        OVERWRITE_EXISTING=true
        shift
        ;;
        -k|--keep)
        DELETE_ARCHIVES=false
        shift
        ;;
        *)
        echo "Unknown option: $1"
        exit 1
        ;;
    esac
done

echo "========================================"
log_info " InterMax Decompiler (Bash)"
echo "========================================"
echo ""

if [ ! -d "$PACKAGES_DIR" ]; then
    log_err "Packages directory not found: $PACKAGES_DIR"
    exit 1
fi

# Select Package
if [ -z "$PACKAGE_NAME" ]; then
    log_warn "  Available packages in 'packages' folder:"
    echo ""
    
    # List directories and archives
    options=()
    i=1
    for item in "$PACKAGES_DIR"/*; do
        fname=$(basename "$item")
        if [ "$fname" == "_incoming" ]; then continue; fi
        
        if [ -d "$item" ]; then
            echo "  [$i] [DIR] $fname"
            options+=("$fname")
            ((i++))
        elif is_archive "$fname"; then
            echo "  [$i] [ARC] $fname"
            options+=("$fname")
            ((i++))
        fi
    done
    
    if [ ${#options[@]} -eq 0 ]; then
        log_err "  No packages found."
        exit 1
    fi
    
    echo "  [q] Quit"
    echo ""
    read -p "  Select package number (or enter name): " selection
    
    if [[ "$selection" == "q" || "$selection" == "quit" || "$selection" == "exit" ]]; then
        log_debug "  Goodbye."
        exit 0
    fi
    
    if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le "${#options[@]}" ]; then
        PACKAGE_NAME="${options[$((selection-1))]}"
    else
        # Assume entered name
        if [ -e "$PACKAGES_DIR/$selection" ]; then
            PACKAGE_NAME="$selection"
        else
            log_err "  Invalid selection!"
            exit 1
        fi
    fi
fi

PACKAGE_PATH="$PACKAGES_DIR/$PACKAGE_NAME"
if [ ! -e "$PACKAGE_PATH" ]; then
    log_err "  Package not found: $PACKAGE_PATH"
    exit 1
fi

# Handle Extraction
if is_archive "$PACKAGE_NAME"; then
    echo ""
    log_warn "[EXTRACT] Processing archive: $PACKAGE_NAME"
    
    archive_basename=$(get_archive_basename "$PACKAGE_NAME")
    work_dir="$PACKAGES_DIR/_incoming/${archive_basename}_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$work_dir"
    
    log_debug "  -> Extracting..."
    extract_archive "$PACKAGE_PATH" "$work_dir"
    
    # Detect single top-level directory
    num_dirs=$(find "$work_dir" -maxdepth 1 -mindepth 1 -type d | wc -l)
    num_files=$(find "$work_dir" -maxdepth 1 -mindepth 1 -type f | wc -l)
    
    if [ "$num_dirs" -eq 1 ] && [ "$num_files" -eq 0 ]; then
        single_dir=$(find "$work_dir" -maxdepth 1 -mindepth 1 -type d)
        extracted_name=$(basename "$single_dir")
        package_dest="$PACKAGES_DIR/$extracted_name"
        
        if ensure_empty_or_overwrite "$package_dest"; then
            mv "$single_dir" "$package_dest"
        else
            rm -rf "$work_dir"
            exit 0
        fi
    else
        extracted_name="$archive_basename"
        package_dest="$PACKAGES_DIR/$extracted_name"
        
        if ensure_empty_or_overwrite "$package_dest"; then
            mkdir -p "$package_dest"
            mv "$work_dir"/* "$package_dest/"
        else
            rm -rf "$work_dir"
            exit 0
        fi
    fi
    
    rm -rf "$work_dir"
    log_success "  -> Extracted to: $extracted_name"
    
    if [ "$DELETE_ARCHIVES" = true ]; then
        rm "$PACKAGE_PATH"
        log_debug "  -> Removed archive: $PACKAGE_NAME"
    fi
    
    PACKAGE_PATH="$package_dest"
    PACKAGE_NAME="$extracted_name"
fi

# Find Root
find_intermax_root() {
    local pkg_dir="$1"
    local candidates=$(find "$pkg_dir" -maxdepth 3 -type d 2>/dev/null)
    local best_dir=""
    local best_score=0
    
    IFS=$'\n'
    for dir in $candidates; do
        local score=0
        local name=$(basename "$dir")
        
        if [[ "$name" == InterMax* ]]; then ((score+=2)); fi
        if [[ "$name" == intermax* ]]; then ((score+=2)); fi
        
        if [ -d "$dir/DGServer_M" ]; then ((score+=10)); fi
        if [ -d "$dir/PlatformJS" ]; then ((score+=10)); fi
        if [ -d "$dir/jspd/lib" ] && [ -f "$dir/jspd/lib/jspd.jar" ]; then ((score+=6)); fi
        if [ -f "$dir/jspd/jspd.jar" ]; then ((score+=6)); fi
        if [ -d "$dir/dotnet/binary" ]; then ((score+=8)); fi
        
        if [ "$score" -gt "$best_score" ]; then
            best_score=$score
            best_dir="$dir"
        fi
    done
    unset IFS
    
    if [ "$best_score" -gt 0 ]; then
        echo "$best_dir"
    fi
}

INTERMAX_PATH=$(find_intermax_root "$PACKAGE_PATH")

if [ -z "$INTERMAX_PATH" ]; then
    log_err "  InterMax root folder not found in package: $PACKAGE_PATH"
    exit 1
fi

# Determine Type
PACKAGE_TYPE="unknown"
if [ -d "$INTERMAX_PATH/DGServer_M" ] || [ -d "$INTERMAX_PATH/PlatformJS" ]; then
    PACKAGE_TYPE="collector"
elif [ -f "$INTERMAX_PATH/jspd/lib/jspd.jar" ]; then
    PACKAGE_TYPE="agent"
elif [ -f "$INTERMAX_PATH/jspd/jspd.jar" ]; then
    PACKAGE_TYPE="collector"
elif [ -f "$INTERMAX_PATH/dotnet/binary/InterMax.NetAgent.dll" ]; then
    PACKAGE_TYPE="dotnet-agent"
elif [ -d "$INTERMAX_PATH/dotnet/binary/core" ]; then
    PACKAGE_TYPE="dotnet-core-agent"
fi

if [ "$PACKAGE_TYPE" == "unknown" ]; then
    log_err "  Could not determine package type from root: $INTERMAX_PATH"
    exit 1
fi

OUTPUT_DIR="$INTERMAX_PATH/decompiled"

echo ""
log_debug "  Base Directory: $BASE_DIR"
log_debug "  Package: $PACKAGE_NAME"
log_debug "  InterMax: $(basename "$INTERMAX_PATH")"
log_debug "  Type: $PACKAGE_TYPE"
echo ""

# Process
DECOMPILED_COUNT=0
SKIPPED_COUNT=0

ensure_java() {
    JAVA_CMD=""
    for v in 11 8 7 6; do
        if [ -x "$INTERMAX_PATH/zulu$v/bin/java" ]; then
            JAVA_CMD="$INTERMAX_PATH/zulu$v/bin/java"
            log_success "  -> Found Zulu JDK from package: $JAVA_CMD"
            return
        fi
    done
    
    if [ -n "$JAVA_HOME" ] && [ -x "$JAVA_HOME/bin/java" ]; then
        JAVA_CMD="$JAVA_HOME/bin/java"
        log_success "  -> Found host Java via JAVA_HOME"
        return
    fi
    
    if find_cmd java; then
        JAVA_CMD="java"
        log_success "  -> Found host Java in PATH"
        return
    fi
    
    log_err "  -> Java not found! Please install Java JDK 11+"
    exit 1
}

ensure_cfr() {
    mkdir -p "$TOOLS_DIR"
    if [ ! -f "$CFR_JAR" ]; then
        log_debug "  -> Downloading CFR $CFR_VERSION..."
        if find_cmd curl; then
            curl -L -o "$CFR_JAR" "$CFR_URL"
        elif find_cmd wget; then
            wget -O "$CFR_JAR" "$CFR_URL"
        else
            log_err "  -> curl or wget not found. Cannot download CFR."
            exit 1
        fi
        log_success "  -> Download complete."
    else
        log_success "  -> CFR already exists."
    fi
}

ensure_ilspy() {
    ILSPY_DIR="$TOOLS_DIR/ilspycmd"
    ILSPY_CMD="$ILSPY_DIR/ilspycmd"
    
    if [ -x "$ILSPY_CMD" ]; then
        log_success "  -> ILSpyCMD already exists."
        return
    fi
    
    if ! find_cmd dotnet; then
        log_err "  -> dotnet CLI not found. Cannot install ILSpyCMD."
        exit 1
    fi
    
    log_debug "  -> Installing ILSpyCMD..."
    dotnet tool install ilspycmd --tool-path "$ILSPY_DIR" --version 9.0.0.7889-preview2 >/dev/null
    
    if [ -x "$ILSPY_CMD" ]; then
        log_success "  -> ILSpyCMD installed."
    else
        log_err "  -> Failed to install ILSpyCMD."
        exit 1
    fi
}

decompile_jar() {
    local name="$1"
    local rel_jar_paths="$2" # Space separated
    local output_rel="$3"
    
    local jar_path=""
    for p in $rel_jar_paths; do
        if [ -f "$INTERMAX_PATH/$p" ]; then
            jar_path="$INTERMAX_PATH/$p"
            break
        fi
    done
    
    if [ -z "$jar_path" ]; then
        log_debug "  [$name] File not found - skipping"
        ((SKIPPED_COUNT++))
        return
    fi
    
    local out_path="$INTERMAX_PATH/$output_rel"
    if ! ensure_empty_or_overwrite "$out_path"; then
        ((SKIPPED_COUNT++))
        return
    fi
    mkdir -p "$out_path"
    
    log_info "  [$name] Decompiling..."
    
    set +e
    "$JAVA_CMD" -jar "$CFR_JAR" "$jar_path" --outputdir "$out_path" >/dev/null 2>&1
    local ret=$?
    set -e
    
    if [ $ret -eq 0 ]; then
        log_success "  [$name] Done!"
        ((DECOMPILED_COUNT++))
    else
        log_err "  [$name] Failed (Exit Code: $ret)"
    fi
}

decompile_dll() {
    local name="$1"
    local rel_dll_paths="$2"
    local output_rel="$3"
    
    local dll_path=""
    for p in $rel_dll_paths; do
        if [ -f "$INTERMAX_PATH/$p" ]; then
            dll_path="$INTERMAX_PATH/$p"
            break
        fi
    done
    
    if [ -z "$dll_path" ]; then
        log_debug "  [$name] File not found - skipping"
        ((SKIPPED_COUNT++))
        return
    fi
    
    local out_path="$INTERMAX_PATH/$output_rel"
    if ! ensure_empty_or_overwrite "$out_path"; then
        ((SKIPPED_COUNT++))
        return
    fi
    mkdir -p "$out_path"
    
    log_info "  [$name] Decompiling..."
    
    set +e
    "$ILSPY_CMD" "$dll_path" -p -o "$out_path" >/dev/null 2>&1
    local ret=$?
    set -e
    
    if [ $ret -eq 0 ]; then
        log_success "  [$name] Done!"
        ((DECOMPILED_COUNT++))
    else
        log_err "  [$name] Failed (Exit Code: $ret)"
    fi
}

start_time=$(date +%s)

if [[ "$PACKAGE_TYPE" == "collector" || "$PACKAGE_TYPE" == "agent" ]]; then
    log_warn "[1/3] Checking Java..."
    ensure_java
    log_warn "[2/3] Preparing CFR..."
    ensure_cfr
    log_warn "[3/3] Decompiling JARs..."
    
    if [ "$PACKAGE_TYPE" == "collector" ]; then
        decompile_jar "datagather" "DGServer_M/bin/datagather.jar DGServer_M/bin/DGServer.jar" "decompiled/datagather"
        decompile_jar "PlatformJS" "PlatformJS/bin/PlatformJS.jar PlatformJS/bin/exem_platformjs.jar" "decompiled/PlatformJS"
        decompile_jar "exem_platformjs" "PlatformJS/svc/www/WEB-INF/lib/exem_platformjs.jar" "decompiled/exem_platformjs"
        decompile_jar "jspd" "jspd/jspd.jar" "decompiled/jspd"
    else
        decompile_jar "jspd" "jspd/lib/jspd.jar" "decompiled/jspd"
    fi
elif [[ "$PACKAGE_TYPE" == "dotnet-agent" || "$PACKAGE_TYPE" == "dotnet-core-agent" ]]; then
    log_warn "[1/2] Preparing ILSpyCMD..."
    ensure_ilspy
    log_warn "[2/2] Decompiling DLLs..."
    
    if [ "$PACKAGE_TYPE" == "dotnet-agent" ]; then
        decompile_dll "InterMax.NetAgent" "dotnet/binary/InterMax.NetAgent.dll" "decompiled/InterMax.NetAgent"
    else
        decompile_dll "InterMax.NetAgent.Core.6.0" "dotnet/binary/core/6.0/InterMax.NetAgent.Core.dll" "decompiled/InterMax.NetAgent.Core.6.0"
        decompile_dll "InterMax.NetAgent.Core.8.0" "dotnet/binary/core/8.0/InterMax.NetAgent.Core.dll" "decompiled/InterMax.NetAgent.Core.8.0"
        decompile_dll "InterMax.Startup.Hook" "dotnet/binary/core/startup/InterMax.Startup.Hook.dll" "decompiled/InterMax.Startup.Hook"
    fi
fi

end_time=$(date +%s)
duration=$((end_time - start_time))

echo ""
echo "========================================"
log_info " Complete!"
echo "========================================"
echo "  Decompiled: $DECOMPILED_COUNT"
echo "  Skipped:    $SKIPPED_COUNT"
echo "  Total time: ${duration}s"
echo ""
log_warn "  Output: $OUTPUT_DIR"
echo ""
