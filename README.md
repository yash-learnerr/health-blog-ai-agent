# 🌍 Global Health Intelligence Agent

A **Markdown-defined autonomous research and publishing agent** for MyDrScripts health content.

This repository produces evidence-grounded health articles for healthcare professionals through a structured workflow covering planning, execution, testing, verification, publishing, memory, and logging.

Approved content is published to the MySQL database `mydrscripts_new` using `blog_category` and `blog_master` with `status = active`. Operational memory and run logs are stored in `health_ai_agent`.

---

## New Developer Quick Start

If you are opening this repository for the first time, use this order:

1. Read `AGENT.md` to understand the agent contract and operating rules.
2. Read `docs/workflows/MAIN_WORKFLOW.md` for the end-to-end execution path.
3. Copy `.env.example` to `.env` and fill in the database settings you need.
4. Run the test suite to confirm your local environment can execute the repository.
5. Start the workflow through `scripts/start_agent.ps1` or `scripts/run_workflow.py`.

### Recommended first-run checklist

- **Python:** Use a Python environment that can run the scripts in `scripts/`.
- **Database access:** Set `DATABASE_ACCESS` plus the matching connection variables in `.env`.
- **Publish database:** `PUBLISH_DB_NAME` defaults to `mydrscripts_new`.
- **Operational database:** `AGENT_DB_NAME` defaults to `health_ai_agent`.
- **Optional uploads:** Only configure the Spaces or app upload settings if you need file/image upload behavior.

### Minimum local setup

- Copy `.env.example` to `.env`
- Review and update:
  - `DATABASE_ACCESS`
  - `DB_HOST`
  - `DB_PORT`
  - `DB_USER`
  - `DB_PASSWORD`
  - `PUBLISH_DB_NAME`
  - `AGENT_DB_NAME`
- Keep optional keys commented out unless you need them

### Suggested first commands

- Validate the repository locally:
  - `python -m unittest discover -s tests`
- Start the workflow with the PowerShell launcher:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\start_agent.ps1`
- Or start it directly with Python:
  - `python scripts/run_workflow.py --recency-hours-24`

### Where new developers should look first

- `AGENT.md`: top-level behavior and safety contract
- `docs/workflows/MAIN_WORKFLOW.md`: ordered workflow
- `docs/execution/EXECUTION.md`: orchestration details
- `config/DATABASE.md`: database behavior and environment expectations
- `config/NEWS_SOURCES.md`: configured source set
- `tests/`: repository contract and script-level tests

---

## What It Does

- Monitor trusted global health sources
- Select clinically relevant topics for healthcare professionals
- Check for duplicate coverage before writing
- Reuse stored memory to avoid redundant research
- Research each topic using an evidence hierarchy
- Write publish-ready, structured blog articles
- Validate factual quality, structure, and duplication
- Publish approved articles into `mydrscripts_new.blog_category` and `mydrscripts_new.blog_master`
- Store reusable memory, logs, and run details in `health_ai_agent`
- Mirror human-readable run and memory summaries into `logs/`

---

## Why This Agent Is Powerful

- **Layered architecture:** Architecture, Runner, Planner, Execution, Tester, Verifier, and Publisher each have a clear responsibility.
- **Memory-augmented execution:** Past research is reused to improve speed and consistency.
- **Evidence hierarchy:** Official health bodies and medical journals are prioritized over lower-authority reporting.
- **Strict publish gate:** Articles only publish after structured validation.
- **Duplicate protection:** Topics are cross-checked before publication.
- **Structured outputs:** Prompts and templates keep the output consistent and production-ready.

---

## How It Works

The agent is defined primarily by Markdown contracts. An AI assistant reads those files and executes the workflow they describe.

After the required startup files are read, the agent owns execution and should continue the workflow without waiting for an additional human prompt.

Execution policy for assistants running this repository:

- Required local commands are pre-approved. If the workflow needs `python3`, `bash`, `mysql`, or repository test commands, it should run them directly instead of asking a human for permission.
- If the workflow runtime is missing a required local dependency such as the Python MySQL driver, it should install that dependency itself and continue rather than asking the human to run the command.
- AI assistants executing this repository must not reply with "run this command" or equivalent command handoff for workflow-owned steps when local command execution is available. They should execute the command themselves and continue the run.

| Layer                                      | Purpose                                                                        |
| ------------------------------------------ | ------------------------------------------------------------------------------ |
| `AGENT.md`                                 | Master identity, rules, and operating contract                                 |
| `docs/verifier/MEDICAL_EVIDENCE_RUBRIC.md` | Shared standard for evidence strength, claim safety, and publication decisions |
| `docs/architecture/*.md`                   | System context, data flow, and integration reference for MyDrScripts           |
| `docs/runner/*.md`                         | Startup and initialization contract                                            |
| `docs/planner/*.md`                        | Topic planning and category selection contract                                 |
| `docs/execution/*.md`                      | Execution order and orchestration contract                                     |
| `docs/tester/*.md`                         | Deterministic schema and output checks before final approval                   |
| `docs/verifier/*.md`                       | Final evidence, duplication, and publish-readiness gate                        |
| `docs/roles/*.md`                          | Role-specific behavior for each phase                                          |
| `docs/workflows/*.md`                      | End-to-end execution logic and error handling                                  |
| `docs/prompts/*.md`                        | Prompt patterns for each major task                                            |
| `config/*.md`                              | Database, scheduler, and source configuration                                  |
| `docs/templates/*.md`                      | Required structure for generated blogs                                         |
| `logs/*.md`                                | Human-readable mirrors of operational memory and run tracking                  |

---

## Current Repository Structure

Key files and directories currently present in the repository:

- `AGENT.md`
- `README.md`
- `.env.example`
- `config/`
  - `DATABASE.md`
  - `DATABASE_TABLES.md`
  - `NEWS_SOURCES.md`
  - `SCHEDULER.md`
- `docs/`
  - `architecture/`
  - `execution/`
  - `planner/`
  - `prompts/`
  - `roles/`
  - `runner/`
  - `templates/`
  - `tester/`
  - `verifier/`
  - `workflows/`
- `frontend/`
  - `dashboard.html`
  - `index.html`
  - `blogs.html`
  - `blog-detail.html`
  - `run-guide.html`
  - `app.js`
  - `styles.css`
- `scripts/`
  - `run_workflow.py`
  - `start_agent.ps1`
  - `agent_dashboard.py`
  - `agent_db.py`
  - `blog_file_manager.py`
  - `publish_blogs.py`
  - `publish_remaining_blogs.py`
  - `run_agent_loop.sh`
- `tests/`
  - `test_agent_dashboard.py`
  - `test_agent_db.py`
  - `test_blog_file_manager.py`
  - `test_repository_contracts.py`
  - `test_run_workflow.py`
- `logs/`
  - `MEMORY_STORE.md`
  - `RUN_LOG.md`
- `examples/`
- `tmp/`

Repository notes:

- The canonical role/task Markdown files live under `docs/roles/`; the top-level `roles/` directory currently exists but is empty.
- `frontend/` contains static UI assets and generated dashboard snapshots for browsing generated/published content.
- `tests/` contains the repository's unit and contract checks.

---

## Publish Target

- **Database:** `mydrscripts_new`
- **Category table:** `blog_category`
- **Blog table:** `blog_master`
- **Published status:** `active`

## Operational Store

- **Database:** `health_ai_agent`
- **Operational tables:** `agent_memory`, `agent_run_logs`
- **Purpose:** memory reuse, retries, skips, run logs, and execution tracking
- **Markdown mirrors:** `logs/MEMORY_STORE.md`, `logs/RUN_LOG.md`

---

## Getting Started

### Method 1 — Start the Autonomous Workflow

Read `AGENT.md` and `docs/workflows/MAIN_WORKFLOW.md`, then start the workflow.

- PowerShell launcher: `powershell -ExecutionPolicy Bypass -File .\scripts\start_agent.ps1`
- Python entrypoint: `python scripts/run_workflow.py --recency-hours-24`

### Method 2 — Schedule It with Your Own Orchestrator

This repository includes local launchers for manual runs, but scheduling/orchestration is still expected to be external. If you want recurring execution, use your own scheduler or automation wrapper and point it at this repository. See `config/SCHEDULER.md`.

### Included helper scripts

#### Workflow startup and orchestration

- `scripts/run_workflow.py`: runs the end-to-end workflow from source fetch through publish/logging.
- `scripts/start_agent.ps1`: PowerShell launcher that loads `.env` and starts the workflow with optional overrides.
- `scripts/run_agent_loop.sh`: runs any command forever, always shows a cooldown timer, and restarts after both success and failure.

#### Publishing and asset handling

- `scripts/blog_file_manager.py`: uploads a generated HTML blog artifact to Spaces and can backfill `blog_master.file` for an existing blog row.
- `scripts/publish_blogs.py` and `scripts/publish_remaining_blogs.py`: batch publishing utilities for curated blog payloads.

#### Database and dashboard utilities

- `scripts/agent_db.py`: shared environment loading, logging, and database access helpers.
- `scripts/agent_dashboard.py`: renders or serves a dashboard page backed by `AGENT_DB_NAME.agent_run_logs` and `AGENT_DB_NAME.agent_memory`.

Executable helpers live in `scripts/`.

---

## Configuration

- **News sources:** `config/NEWS_SOURCES.md`
- **Database behavior:** `config/DATABASE.md`
- **Database schema:** `config/DATABASE_TABLES.md`
- **Scheduling guidance:** `config/SCHEDULER.md`
- **Environment example:** `.env.example`

### Common commands

These are the most useful commands for a developer getting started locally.

- Backfill a missing `blog_master.file` for an existing row:
  - `python3 scripts/blog_file_manager.py --blog-id 5`
- Start the workflow through the repo launcher:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\start_agent.ps1`
- Start the workflow directly through Python:
  - `python scripts/run_workflow.py --recency-hours-24`
- Run a command continuously with a 2-minute cooldown:
  - `COOLDOWN_SECONDS=120 bash scripts/run_agent_loop.sh <your-command>`
- Generate a dashboard HTML page from the operational database:
  - `python3 scripts/agent_dashboard.py --output frontend/dashboard.html`
- Serve a live dashboard page locally:
  - `python3 scripts/agent_dashboard.py --serve --port 8765`

Optional dashboard login for `--serve` mode can be controlled from `.env`:

- `DASHBOARD_LOGIN_ENABLED=0` → dashboard opens directly
- `DASHBOARD_LOGIN_ENABLED=1` → dashboard shows a login form first
- set `DASHBOARD_LOGIN_USERNAME` and `DASHBOARD_LOGIN_PASSWORD` when enabled

### Optional convenience setup

#### Short command setup

`.env` can store launcher settings, but it does not register a universal command in every CLI or IDE by itself. This repo includes `scripts/start_agent.ps1` so you can point your shell or IDE at one stable entrypoint.

Optional launcher keys in `.env`:

- `AGENT_PYTHON_COMMAND` to choose the Python executable
- `AGENT_START_RECENCY_HOURS` to change the default workflow window
- `AGENT_START_COMMAND` to fully override the launched command

#### Testing

Start with these before making changes or before your first full workflow run.

- Run the full test suite:
  - `python -m unittest discover -s tests`
- Run the repository contract checks only:
  - `python -m unittest tests.test_repository_contracts`

PowerShell profile example:

```powershell
function health-agent {
  & "C:\Personal Projects\health-ai-agent\scripts\start_agent.ps1"
}
```

VS Code task example:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Start Health Agent",
      "type": "shell",
      "command": "powershell",
      "args": [
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "${workspaceFolder}\\scripts\\start_agent.ps1"
      ]
    }
  ]
}
```

The dashboard shows:

- two graphs for daily activity and token/request usage,
- recent run/event tables,
- recent memory facts,
- latest published blogs with category and image/file preview when available from the publish DB schema.

### Optional browser-search verification

- The Markdown workflow now treats a **Google Chrome MCP server** as an optional-but-preferred supplementary verification layer.
- Use it after source fetching/research to open rendered pages, run browser-based searches, and detect contradictions before final PASS/FAIL.
- If it is unavailable in the runtime, the workflow continues with the standard source-validation path and should log that browser verification was unavailable.

---

## Important Notes

- No external provider keys are required unless you want to upload blog files to Spaces using `scripts/blog_file_manager.py`.
- Execution is designed as one consistent workflow, not a multi-runner cascade.
- Any scheduler, secret injection, or runtime wrapper is expected to be external to this repo.
- Database credentials may still be needed in your execution environment if you want publishing to MySQL.
- The final publishing contract is `mydrscripts_new.blog_category` + `mydrscripts_new.blog_master`, both using `status = active` for live content.
- Operational details like memory and logging are stored in `health_ai_agent` and may also be mirrored into the `logs/` files for readability.
- Runtime scripts should write detailed execution events to `AGENT_DB_NAME.agent_run_logs`; Markdown files under `logs/` are only mirrors.
- Runtime DB operations use `DATABASE_ACCESS=local|staging|production`; non-local targets read `STAGING_*` or `PRODUCTION_*` connection variables and fall back to local DB names only when target-specific names are not provided.
- Request/token usage can be stored per log row via `request_count`, `prompt_tokens`, `completion_tokens`, and `total_tokens` in `agent_run_logs`.
