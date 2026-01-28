import os
import subprocess

def run_cmd(cmd):
    try:
        process = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"Success: {cmd}")
        print(process.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error: {cmd}")
        print(e.stderr)

run_cmd("git init")

gitignore_content = """packages/*
!packages/.gitkeep
analysis/
*.log
__pycache__/
"""

with open(".gitignore", "w") as f:
    f.write(gitignore_content)

os.makedirs("packages", exist_ok=True)
with open("packages/.gitkeep", "w") as f:
    f.write("")

run_cmd("git add .gitignore")
