#!/bin/bash

# InterMax JAR Decompiler Script
# Decompile core JAR files using CFR decompiler
# Usage: ./decompile.sh [package_name]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$SCRIPT_DIR"

# Configuration
CFR_VERSION="0.152"
CFR_URL="https://github.com/leibnitz27/cfr/releases/download/${CFR_VERSION}/cfr-${CFR_VERSION}.jar"
TOOLS_DIR="${BASE_DIR}/tools"
CFR_JAR="${TOOLS_DIR}/cfr-${CFR_VERSION}.jar"
PACKAGES_DIR="${BASE_DIR}/packages"

# JAR files to decompile (name|path1|path2|...)
declare -a JAR_FILES=(
    "datagather|DGServer_M/bin/datagather.jar|DGServer_M/bin/DGServer.jar"
    "PlatformJS|PlatformJS/bin/PlatformJS.jar|PlatformJS/bin/exem_platformjs.jar"
    "exem_platformjs|PlatformJS/svc/www/WEB-INF/lib/exem_platformjs.jar|PlatformJS/svc/www/WEB-INF/lib/exem_platformjs.jar.ori|PlatformJS/bin/exem_platformjs.jar"
    "jspd|jspd/jspd.jar"
)

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN} InterMax JAR Decompiler${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Check packages directory
if [ ! -d "$PACKAGES_DIR" ]; then
    echo -e "${RED}  Packages directory not found: ${PACKAGES_DIR}${NC}"
    echo -e "${YELLOW}  Please create 'packages' folder and place package folders inside.${NC}"
    exit 1
fi

# Get package name from argument or prompt
PACKAGE_NAME="$1"

if [ -z "$PACKAGE_NAME" ]; then
    echo -e "${YELLOW}  Available packages in 'packages' folder:${NC}"
    echo ""
    
    # List packages
    packages=($(ls -d "$PACKAGES_DIR"/*/ 2>/dev/null | xargs -n1 basename))
    
    if [ ${#packages[@]} -eq 0 ]; then
        echo -e "${RED}  No packages found in: ${PACKAGES_DIR}${NC}"
        exit 1
    fi
    
    index=1
    for pkg in "${packages[@]}"; do
        echo -e "  ${WHITE}[$index] $pkg${NC}"
        ((index++))
    done
    
    echo ""
    read -p "  Select package number (or enter name): " selection
    
    if [[ "$selection" =~ ^[0-9]+$ ]]; then
        selected_index=$((selection - 1))
        if [ $selected_index -ge 0 ] && [ $selected_index -lt ${#packages[@]} ]; then
            PACKAGE_NAME="${packages[$selected_index]}"
        else
            echo -e "${RED}  Invalid selection!${NC}"
            exit 1
        fi
    else
        PACKAGE_NAME="$selection"
    fi
fi

# Validate package path
PACKAGE_DIR="${PACKAGES_DIR}/${PACKAGE_NAME}"

if [ ! -d "$PACKAGE_DIR" ]; then
    echo -e "${RED}  Package not found: ${PACKAGE_DIR}${NC}"
    exit 1
fi

# Find InterMax folder
INTERMAX_DIR=$(find "$PACKAGE_DIR" -maxdepth 1 -type d -name "InterMax*" | head -1)

if [ -z "$INTERMAX_DIR" ]; then
    echo -e "${RED}  InterMax folder not found in package: ${PACKAGE_DIR}${NC}"
    exit 1
fi

INTERMAX_NAME=$(basename "$INTERMAX_DIR")

# Output directory inside InterMax folder
OUTPUT_DIR="${INTERMAX_DIR}/decompiled"

echo ""
echo -e "${GRAY}  Base Directory: ${BASE_DIR}${NC}"
echo -e "${GRAY}  Package: ${PACKAGE_NAME}${NC}"
echo -e "${GRAY}  InterMax: ${INTERMAX_NAME}${NC}"
echo ""

# 1. Check Java - Prioritize Zulu from package
echo -e "${YELLOW}[1/4] Checking Java...${NC}"

JAVA_CMD=""

# Priority 1: Zulu JDK from package
ZULU_PATHS=(
    "${INTERMAX_DIR}/zulu11/bin/java"
    "${INTERMAX_DIR}/zulu8/bin/java"
    "${INTERMAX_DIR}/zulu7/bin/java"
    "${INTERMAX_DIR}/zulu6/bin/java"
)

for zulu_path in "${ZULU_PATHS[@]}"; do
    if [ -x "$zulu_path" ]; then
        JAVA_CMD="$zulu_path"
        echo -e "${GREEN}  -> Found Zulu JDK from package: ${JAVA_CMD}${NC}"
        break
    fi
done

# Priority 2: Host system Java (JAVA_HOME)
if [ -z "$JAVA_CMD" ] && [ -n "$JAVA_HOME" ] && [ -x "$JAVA_HOME/bin/java" ]; then
    JAVA_CMD="$JAVA_HOME/bin/java"
    echo -e "${GREEN}  -> Found host Java via JAVA_HOME: ${JAVA_CMD}${NC}"
fi

# Priority 3: Host system Java (PATH)
if [ -z "$JAVA_CMD" ]; then
    if command -v java &> /dev/null; then
        JAVA_CMD=$(command -v java)
        echo -e "${GREEN}  -> Found host Java in PATH: ${JAVA_CMD}${NC}"
    fi
fi

# If still not found, show instructions
if [ -z "$JAVA_CMD" ]; then
    echo -e "${RED}  -> Java not found!${NC}"
    echo ""
    echo -e "${YELLOW}  Please install Java JDK 11 or higher:${NC}"
    echo -e "${WHITE}  - Ubuntu/Debian: sudo apt install openjdk-11-jdk${NC}"
    echo -e "${WHITE}  - CentOS/RHEL: sudo yum install java-11-openjdk-devel${NC}"
    echo -e "${WHITE}  - Or download from: https://adoptium.net/${NC}"
    echo ""
    exit 1
fi

# Verify Java version
JAVA_VERSION=$("$JAVA_CMD" -version 2>&1 | head -1)
echo -e "${GRAY}  -> Version: ${JAVA_VERSION}${NC}"

# 2. Download CFR decompiler
echo ""
echo -e "${YELLOW}[2/4] Preparing CFR decompiler...${NC}"

mkdir -p "$TOOLS_DIR"

if [ ! -f "$CFR_JAR" ]; then
    echo -e "${GRAY}  -> Downloading CFR ${CFR_VERSION}...${NC}"
    if command -v curl &> /dev/null; then
        curl -L -o "$CFR_JAR" "$CFR_URL"
    elif command -v wget &> /dev/null; then
        wget -O "$CFR_JAR" "$CFR_URL"
    else
        echo -e "${RED}  -> Neither curl nor wget found. Please install one.${NC}"
        exit 1
    fi
    echo -e "${GREEN}  -> Download complete: ${CFR_JAR}${NC}"
else
    echo -e "${GREEN}  -> CFR already exists: ${CFR_JAR}${NC}"
fi

# 3. Create output directory (inside InterMax folder)
echo ""
echo -e "${YELLOW}[3/4] Preparing output directory...${NC}"

mkdir -p "$OUTPUT_DIR"
echo -e "${GREEN}  -> Output path: ${OUTPUT_DIR}${NC}"

# 4. Decompile JAR files
echo ""
echo -e "${YELLOW}[4/4] Decompiling JAR files...${NC}"
echo ""

TOTAL_START=$(date +%s)
DECOMPILED=0
SKIPPED=0

for jar_entry in "${JAR_FILES[@]}"; do
    IFS='|' read -ra PARTS <<< "$jar_entry"
    NAME="${PARTS[0]}"
    
    # Find existing JAR file from possible paths (relative to InterMax folder)
    JAR_PATH=""
    for ((i=1; i<${#PARTS[@]}; i++)); do
        FULL_PATH="${INTERMAX_DIR}/${PARTS[$i]}"
        if [ -f "$FULL_PATH" ]; then
            JAR_PATH="$FULL_PATH"
            break
        fi
    done
    
    if [ -z "$JAR_PATH" ]; then
        echo -e "${GRAY}  [${NAME}] File not found - skipping${NC}"
        ((SKIPPED++))
        continue
    fi
    
    OUTPUT_PATH="${OUTPUT_DIR}/${NAME}"
    
    # Remove existing output folder
    rm -rf "$OUTPUT_PATH"
    mkdir -p "$OUTPUT_PATH"
    
    JAR_SIZE=$(du -h "$JAR_PATH" | cut -f1)
    echo -e "${WHITE}  [${NAME}] Decompiling (${JAR_SIZE})...${NC}"
    
    START=$(date +%s)
    
    # Run CFR
    "$JAVA_CMD" -jar "$CFR_JAR" "$JAR_PATH" --outputdir "$OUTPUT_PATH"
    
    END=$(date +%s)
    ELAPSED=$((END - START))
    
    FILE_COUNT=$(find "$OUTPUT_PATH" -name "*.java" | wc -l)
    echo -e "${GREEN}  [${NAME}] Done! ${FILE_COUNT} .java files created (${ELAPSED}s)${NC}"
    ((DECOMPILED++))
done

# Completion message
TOTAL_END=$(date +%s)
TOTAL_ELAPSED=$((TOTAL_END - TOTAL_START))

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN} Complete!${NC}"
echo -e "${CYAN}========================================${NC}"
echo -e "${WHITE}  Decompiled: ${DECOMPILED}${NC}"
echo -e "${WHITE}  Skipped:    ${SKIPPED}${NC}"
echo -e "${WHITE}  Total time: ${TOTAL_ELAPSED}s${NC}"
echo ""
echo -e "${YELLOW}  Output: ${OUTPUT_DIR}${NC}"
echo ""
