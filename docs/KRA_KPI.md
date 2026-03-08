# KRA & KPI Reference

## Purpose

This file defines the **judge-facing KRA/KPI set** for the Global Health Intelligence Agent.
It is intentionally based on evidence already present in this repository.

## Relationship to `frontend/blog-workflow.html`

This file is **not the same** as `frontend/blog-workflow.html`.

- `frontend/blog-workflow.html` is the **presentation companion**
  - visual storytelling
  - manual-vs-AI comparison
  - process diagram
  - slide-style explanation for judges and stakeholders
- `docs/KRA_KPI.md` is the **measurement and judging companion**
  - KRAs
  - KPIs
  - ROI statement
  - judge-safe business claims

## Source-of-truth rule

For hackathon judging, use this document as the **source of truth** for:

- time-saved claims
- KPI wording
- ROI wording
- business-value language

Use `frontend/blog-workflow.html` as the **visual presentation layer** for the same story.

## Authoritative judging baseline

- **Manual workflow:** `90 minutes to 3 hours` per article
- **AI end-to-end workflow:** `5 to 10 minutes` per published article
- **Observed repo evidence:** `3 published blog articles in ~15 minutes` and multiple `1 article in ~8–10 minutes` runs in `logs/RUN_LOG.md`

> Judge-safe note: use **5 to 10 minutes per article** for end-to-end claims.
> Do **not** use `under 1 minute` as the end-to-end claim; that is only defensible for a narrower generation step, not the full autonomous workflow.

## Key Result Areas

| KRA | Why it matters | KPI | Target | Current repo evidence |
| --- | --- | --- | --- | --- |
| Trusted source monitoring | Ensures the agent watches real healthcare sources | Source fetch success rate | Successful fetch on every run unless sources are unavailable | `docs/workflows/MAIN_WORKFLOW.md`, `logs/RUN_LOG.md` |
| Relevant topic selection | Avoids publishing low-value updates | Clinically relevant topics selected per run | `1–3` high-value topics per run | Topic selection and category resolution are logged in `logs/RUN_LOG.md` |
| Duplicate prevention | Prevents repeated coverage | Duplicate-check success before writing/publishing | `100%` duplicate check before publish | `docs/workflows/DUPLICATE_CHECK.md`, `logs/RUN_LOG.md` |
| Evidence-safe publication | Reduces hallucinated or unsafe content | Validation/verifier pass rate for published articles | `100%` of published articles pass tester + validator | `docs/tester/TESTER.md`, `docs/verifier/VERIFIER.md`, `logs/RUN_LOG.md` |
| Publishing throughput | Converts research into published output | Published articles per run | `1–3` articles per successful run | `logs/RUN_LOG.md` shows 3-blog and 1-blog successful runs |
| Knowledge retention | Makes the agent better on later runs | New memory facts stored per run | `> 0` facts stored after successful publish | `logs/MEMORY_STORE.md`, `logs/RUN_LOG.md` |
| Operational visibility | Makes the system demoable and auditable | Run/event visibility in dashboard and logs | Every run visible in dashboard/logs | `frontend/dashboard.html`, `scripts/agent_dashboard.py`, `frontend/index.html` |

## KPI summary for judging

| KPI | Current evidence | Judge-safe statement |
| --- | --- | --- |
| End-to-end article time | `~5 minutes/article` in a 3-article, ~15 minute run | The agent reduces article production from `90–180 minutes` to about `5–10 minutes` end-to-end |
| Successful publish proof | Multiple runs with published articles in `logs/RUN_LOG.md` | The repository contains evidence of successful autonomous publishing |
| Memory growth | Multiple runs storing `3–8` facts | Each successful run increases reusable operational memory |
| Dashboard observability | `frontend/dashboard.html` + served dashboard support | Judges can inspect runs, logs, memory, and recent outputs visually |

## Judging Criteria mapping

| Judging area | Primary repo evidence |
| --- | --- |
| Solves Client Project Problems | `frontend/blog-workflow.html`, `md/blog_creation_before_ai.md`, `logs/RUN_LOG.md` |
| Documentation, Standards & KRA/KPIs | `README.md`, `AGENT.md`, `docs/KRA_KPI.md`, `docs/workflows/MAIN_WORKFLOW.md` |
| Agent Autonomy & Execution | `AGENT.md`, `docs/workflows/MAIN_WORKFLOW.md`, `scripts/run_workflow.py`, `logs/RUN_LOG.md` |
| Presentation & Demo | `frontend/blog-workflow.html`, `frontend/dashboard.html`, `docs/demo/DEMO_SCRIPT.md`, `docs/demo/JUDGE_QA.md` |

## ROI statement for the pitch

If the team publishes **10 articles per week**:

- Manual effort: `15 to 30 hours/week`
- AI effort: about `50 to 100 minutes/week`
- Estimated time saved: about `13 hours 20 minutes` to `28 hours 20 minutes` per week

Use this as the **primary ROI statement** unless you later replace it with measured production analytics.

## What judges should hear

1. This agent solves a **real client publishing bottleneck**.
2. It works across a **full autonomous workflow**, not a single prompt.
3. It already shows **published outputs, logs, dashboard visibility, and memory reuse**.
4. Its impact should be described using the **conservative, end-to-end timing claim** above.