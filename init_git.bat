@echo off
git init
if not exist .gitignore (
    echo packages/*> .gitignore
    echo !packages/.gitkeep>> .gitignore
    echo analysis/>> .gitignore
    echo *.log>> .gitignore
)
if not exist packages\.gitkeep (
    type nul > packages\.gitkeep
)
git add .
git commit -m "Initial commit: Decompiler tools"
echo Git repository initialized.
pause
