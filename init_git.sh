#!/bin/bash
git init
if [ ! -f .gitignore ]; then
    echo "packages/*" > .gitignore
    echo "!packages/.gitkeep" >> .gitignore
    echo "analysis/" >> .gitignore
    echo "*.log" >> .gitignore
fi
mkdir -p packages
touch packages/.gitkeep
git add .
git commit -m "Initial commit: Decompiler tools"
echo "Git repository initialized."
