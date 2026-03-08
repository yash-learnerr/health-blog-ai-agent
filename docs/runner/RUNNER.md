# Runner Layer

## Purpose

This layer is responsible for starting a run safely and preparing both the publication and operational targets.

## Responsibilities

1. Load configuration from `.env` or the execution environment.
2. Confirm the selected publish database name for the active `DATABASE_ACCESS` target.
3. Confirm the selected operational database name for the active `DATABASE_ACCESS` target.
4. Confirm `blog_category` and `blog_master` are the active publication tables.
5. Confirm `agent_memory` and `agent_run_logs` are the active operational tables.
6. Load `AGENT.md`, `docs/verifier/MEDICAL_EVIDENCE_RUBRIC.md`, and `docs/execution/EXECUTION.md`.
7. Start the workflow without waiting for human confirmation.
8. Run required local helper commands directly when needed, including `python3`, `bash`, `mysql`, and validation commands, without requesting separate approval.
9. Never emit a "run this command" instruction for a repository-owned step when the command can be executed in the current runtime.
10. If a required dependency is missing, install or recover it directly and continue instead of asking the human to do it.

## Pre-Run Checklist

- publish database target is `mydrscripts_new`
- operational database target is `health_ai_agent`
- category table is `blog_category`
- blog table is `blog_master`
- memory table is `agent_memory`
- run log table is `agent_run_logs`
- live publish status is `active`
- logs path is writable

## Rule

If the database contract does not match the expected publish or operational targets, stop writes and log the mismatch instead of writing to the wrong table.
