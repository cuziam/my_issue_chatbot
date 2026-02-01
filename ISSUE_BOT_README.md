# InterMax Issue Analysis Bot

Automated ClickUp issue analysis system using Claude Code.

## Overview

This bot automatically fetches ClickUp tasks, analyzes them using Claude Code with access to decompiled InterMax source code, and generates detailed analysis reports.

## Features

- Fetch tasks from ClickUp API (including comments and attachments)
- Automatically extract version information from custom fields
- Match versions to decompiled package directories
- Run Claude Code analysis with predefined prompts
- Generate markdown reports for manual upload to ClickUp
- Support batch processing (sequential or parallel)

## Requirements

### Software

- Python 3.8 or higher
- Claude Code CLI (https://claude.ai/download)
- InterMax packages (decompiled using decompile.ps1/sh)

### API Keys

- ClickUp API key (https://app.clickup.com/settings/apps)
- Anthropic API key (https://console.anthropic.com/settings/keys)

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Claude Code CLI

Windows (PowerShell):
```powershell
irm https://claude.ai/install.ps1 | iex
```

Windows (WinGet):
```powershell
winget install Anthropic.ClaudeCode
```

Linux/Mac:
```bash
curl -fsSL https://claude.ai/install.sh | bash
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Edit `.env`:
```env
CLICKUP_API_KEY=pk_your_clickup_api_key_here
ANTHROPIC_API_KEY=sk-ant-your_anthropic_api_key_here
```

### 4. Configure ClickUp settings

Edit `config.json` and set your workspace/list IDs:

```json
{
  "clickup": {
    "workspace_id": "your_workspace_id",
    "list_id": "your_list_id"
  }
}
```

### 5. Prepare packages

Ensure InterMax packages are decompiled in the `packages/` directory:

```
packages/
├── package_v5.4.11.1/
│   └── InterMax_v5.4/
│       └── decompiled/
│           ├── datagather/
│           ├── PlatformJS/
│           └── jspd/
└── package_v5.3.231227.05/
    └── ...
```

Use the existing decompiler scripts:
```bash
# Windows
.\decompile.ps1

# Linux/Mac
./decompile.sh
```

## Usage

### Single Task Analysis

1. Fetch a task from ClickUp:
```bash
python fetch.py --task-id abc123
```

2. Analyze the task:
```bash
python analyze.py --task-id abc123 --template issue_analysis
```

3. View the report:
```bash
cat tasks/abc123/report.md
```

4. Manually copy the report content to ClickUp

### Batch Analysis

Fetch multiple tasks and analyze them:

```bash
# Fetch all tasks with specific tag
python fetch.py --list-id 123456 --tags needs-analysis

# Analyze all fetched tasks (sequential)
python batch.py --template issue_analysis

# Analyze with parallel processing (3 concurrent)
python batch.py --template issue_analysis --parallel 3
```

### Analysis Templates

Three analysis templates are available:

- `issue_analysis`: Analyze customer support issues
  - Version information
  - Issue summary
  - Reproduction steps
  - Root cause analysis
  - Proposed solution

- `spec_inquiry`: Research feature specifications
  - Version information
  - Request summary
  - Specification verification
  - Configuration methods

- `improvement_request`: Analyze improvement requests
  - Version information
  - Request summary
  - Related feature check
  - Implementation proposal

## Directory Structure

```
my_issue_chatbot/
├── .env                    # API keys (gitignored)
├── config.json             # ClickUp configuration
├── prompts.json            # Analysis templates
├── fetch.py                # ClickUp task fetcher
├── analyze.py              # Claude Code analyzer
├── batch.py                # Batch processor
├── requirements.txt        # Python dependencies
│
├── tasks/                  # Task storage (gitignored)
│   └── {TASK_ID}/
│       ├── task.json       # Task data
│       ├── images/         # Downloaded images
│       ├── prompt.txt      # Generated prompt
│       └── report.md       # Analysis report
│
├── packages/               # InterMax packages
│   └── package_vX.X.X/
│       └── InterMax_vX.X/
│           └── decompiled/
│
└── tools/                  # Decompiler tools
    └── cfr-0.152.jar
```

## Automated Scheduling

### Windows Task Scheduler

Create a PowerShell script `daily_analysis.ps1`:

```powershell
cd C:\path\to\my_issue_chatbot

# Fetch new tasks
python fetch.py --list-id 123456 --tags needs-analysis

# Analyze in batch
python batch.py --template issue_analysis --parallel 3
```

Register in Task Scheduler:
```powershell
$action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-File C:\path\to\daily_analysis.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At 9am
Register-ScheduledTask -TaskName "InterMax Issue Analysis" -Action $action -Trigger $trigger
```

## Customization

### Adding New Analysis Templates

Edit `prompts.json` to add custom templates:

```json
{
  "my_custom_template": {
    "name": "My Custom Analysis",
    "description": "Custom analysis description",
    "template": "Your prompt template here with {variables}"
  }
}
```

### Adjusting Version Fields

Edit `config.json` to modify which custom fields are used for version detection:

```json
{
  "version_fields": [
    "Product",
    "Agent Version",
    "PlatformJS Version",
    "Your Custom Field"
  ]
}
```

## Troubleshooting

### Claude Code not found

Make sure Claude Code CLI is installed and in your PATH:
```bash
claude --version
```

### API authentication failed

Verify your API keys in `.env` file:
- ClickUp API key format: `pk_...`
- Anthropic API key format: `sk-ant-...`

### No packages found

Ensure packages are decompiled and located in the correct directory structure:
```
packages/package_vX.X.X/*/decompiled/
```

### Task fetch failed

Check your ClickUp list ID and permissions in `config.json`

## License

Internal use only for InterMax support team.

## Support

For issues or questions, contact the development team.
