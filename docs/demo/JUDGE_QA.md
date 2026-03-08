# Judge Q&A

## 1) Is this really an AI agent, or just automation?

It is an agent because it follows an end-to-end operating contract in `AGENT.md` and `docs/workflows/MAIN_WORKFLOW.md`, makes intermediate execution decisions autonomously, and completes a multi-step workflow without hand-holding.

## 2) What real problem does it solve?

It solves a real healthcare content operations problem: manual monitoring, research, drafting, review, and publishing were slow and repetitive. The repository documents a manual baseline of `90 minutes to 3 hours` per article.

## 3) What does the agent do from start to finish?

It initializes required tables, retrieves memory, fetches trusted health news, selects relevant topics, checks duplicates, researches, writes, validates, verifies, publishes, stores memory, and logs the run.

## 4) What proof do you have that it works?

`logs/RUN_LOG.md`, `frontend/dashboard.html`, and the dashboard server support in `scripts/agent_dashboard.py` show successful runs, published blogs, stored memory, and recent operational activity.

## 5) How autonomous is it?

The autonomy contract is explicit: the agent should not pause for human confirmation during workflow-owned steps. It is designed to continue until the run is complete or externally blocked.

## 6) How do you prevent unsafe or hallucinated medical content?

The workflow uses trusted sources, duplicate checks, deterministic testing, and a final verification layer defined in `docs/verifier/VERIFIER.md` and `docs/verifier/MEDICAL_EVIDENCE_RUBRIC.md`.

## 7) What KPIs do you use?

Use `docs/KRA_KPI.md` during judging. The main KPIs are source fetch success, relevant topics selected, duplicate prevention, validation/verifier pass rate, published articles per run, memory facts stored, and dashboard-visible run logging.

## 8) What is the measurable business value?

Judge-safe claim: the workflow reduces article production from `90–180 minutes` manually to about `5–10 minutes` per published article end-to-end. At 10 articles per week, that is about `13 hours 20 minutes` to `28 hours 20 minutes` saved weekly.

## 9) Is it deployable in a real client environment?

Yes. The project already targets real MySQL publishing tables, operational memory tables, and includes a dashboard for monitoring runs. It is designed for scheduled execution with external orchestration.

## 10) What is your strongest judging advantage?

This is not a concept-only hackathon project. The repository already contains workflow contracts, run logs, dashboard visibility, memory persistence, and evidence of successful publishing runs.

## 11) What is the biggest current limitation?

The latest dashboard evidence shows a recent DB collation mismatch error on one run. This is a reliability issue to fix before a high-risk live publish demo, but it does not erase the repository evidence of multiple successful autonomous runs.

## 12) Why not do a live full publish run in front of judges?

The safest demo is to show existing successful runs, dashboard visibility, and workflow evidence unless the current DB issue is fixed first. That keeps the presentation reliable and judge-focused.

## 13) What would you improve next?

Next priorities are: fix the collation issue, add automated KPI rollups, package screenshots/video backup for demo resilience, and extend weekly ROI reporting for stakeholders.

## 14) Why is this valuable beyond the hackathon?

It converts a repeatable client workflow into a scalable operating system for content production, with traceability, memory reuse, and measurable time savings.