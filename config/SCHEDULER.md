# Scheduler Configuration

## Overview

The Global Health Intelligence Agent runs on a scheduled basis. This file defines the schedule and trigger settings.

---

## Schedule

| Setting         | Value               |
| --------------- | ------------------- |
| Frequency       | Every 2 hours       |
| Cron Expression | `0 */2 * * *`       |
| Timezone        | UTC                 |
| First Run       | On first deployment |

---

## Cron Expression Breakdown

```
0 */2 * * *
│  │   │ │ │
│  │   │ │ └── Day of week (any)
│  │   │ └──── Month (any)
│  │   └────── Day of month (any)
│  └────────── Every 2 hours
└───────────── At minute 0
```

---

## Trigger Methods

### Method 1: System Cron (Linux/macOS)

Add to your crontab:

```
0 */2 * * * /path/to/trigger-agent.sh >> /var/log/health-agent.log 2>&1
```

### Method 2: Manual Start of the Autonomous Agent

Trigger the workflow once with `AGENT.md` and `docs/workflows/MAIN_WORKFLOW.md` as inputs.

Primary trigger command: `start-agent`

Accepted trigger command aliases and equivalent start phrases: `start`, `start agent`, `start work`, `start-work`, `run-agent`, `create-blog`, `init-blog-agent`, `agent-start`, `begin-task`, `generate-blog`, `execute-agent`

Legacy trigger phrases such as `Read AGENT.md`, `Start AGENT.md`, or equivalent review/start instructions should be treated as the same authorization to read the contract first and then begin the workflow automatically.

After the trigger, the agent must continue autonomously without human intervention or approval prompts.
If the run needs local commands or dependency recovery, the agent performs those actions itself and does not hand commands back to the human.

---

## Run Limits

| Setting                     | Value     |
| --------------------------- | --------- |
| Max articles per run        | 20        |
| Max topics per run          | 3         |
| Max blogs per run           | 3         |
| Max retries on Writer fail  | 1         |
| Timeout per blog generation | 5 minutes |

---

## Notes

- Do not run more frequently than every 30 minutes to avoid source throttling and duplicate coverage.
- If a run is already in progress, the next scheduled run should be skipped.
- All run results are stored in `health_ai_agent.agent_run_logs` and may be mirrored in `logs/RUN_LOG.md`.
