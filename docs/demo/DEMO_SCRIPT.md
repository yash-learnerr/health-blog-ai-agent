# Demo Script

## Demo objective

Show judges that this is a **real autonomous agent** that solves a client publishing problem, not just a chat demo.

## Judge-safe claims

- Manual process takes about `90 minutes to 3 hours` per article
- The autonomous workflow can complete in about `5 to 10 minutes` per published article
- The repo contains evidence of successful runs with `3 published blogs in ~15 minutes`

## Pre-demo checklist

1. Keep these files ready:
   - `frontend/blog-workflow.html`
   - `frontend/dashboard.html`
   - `logs/RUN_LOG.md`
   - `AGENT.md`
   - `docs/KRA_KPI.md`
2. If serving locally, use:
   - `python3 scripts/agent_dashboard.py --serve --port 8765`
3. Keep `frontend/dashboard.html` open as the backup if live serving is unavailable.
4. Do **not** promise a fresh full publish run during judging unless the latest DB collation issue is fixed.

## 3-minute pitch flow

### 0:00–0:30 — Problem

Open `frontend/blog-workflow.html`.

Say:

> Healthcare content publishing was manual, repetitive, slow, and hard to scale. A single article could take 90 minutes to 3 hours from monitoring through publishing.

### 0:30–1:10 — Solution

Still on the workflow page, show the manual-vs-AI comparison and process diagram.

Say:

> We converted that process into an autonomous agent workflow: fetch trusted health sources, select relevant topics, check duplicates, research, write, validate, verify, publish, store memory, and log the run.

### 1:10–1:50 — Proof this is an agent

Open `AGENT.md` and briefly show the autonomy rules, then show `docs/workflows/MAIN_WORKFLOW.md`.

Say:

> This is not a single prompt. The agent is governed by a workflow contract and is expected to complete the full run end-to-end without hand-holding.

### 1:50–2:30 — Working evidence

Open `frontend/dashboard.html` or the served dashboard.

Point to:

- recent runs
- recent agent activity
- memory facts
- published blog outputs

Then open `logs/RUN_LOG.md`.

Say:

> We have repository evidence of successful autonomous runs, including one run that published 3 articles in about 15 minutes and other runs that published single articles in about 8 to 10 minutes.

### 2:30–3:00 — Business value

Open `docs/KRA_KPI.md`.

Say:

> For a team producing 10 articles a week, this shifts work from roughly 15 to 30 hours of manual effort down to about 50 to 100 minutes of supervised agent output, saving roughly 13 to 28 hours per week.

## Fallback demo order

If live serving fails, use this order:

1. `frontend/blog-workflow.html`
2. `frontend/dashboard.html`
3. `logs/RUN_LOG.md`
4. `docs/KRA_KPI.md`

## What not to say

- Do not claim `under 1 minute` for the full end-to-end workflow.
- Do not promise zero errors forever.
- Do not position this as a chatbot.

## Best closing line

> We turned a real client publishing workflow into a measurable autonomous system with evidence-safe output, reusable memory, and dashboard-visible operations.