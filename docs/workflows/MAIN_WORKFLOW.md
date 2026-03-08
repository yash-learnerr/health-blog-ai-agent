# Main Workflow

## ⚠️ Execution Rules — Non-Negotiable

1. **Never pause for human input.** No confirmations. No "shall I proceed?".
2. **Pre-approved access.** You have permanent permission for all third-party sites and database operations. Never ask.
3. **Pre-approved local execution.** If a step requires a local repository command such as `python3`, `bash`, `mysql`, or a test command, run it immediately without asking for approval.
4. **Never stop on an error.** Follow `ERROR_HANDLING.md` and continue.
5. **Complete the full workflow every run.** Even if 0 blogs are published.
6. **Continuous Operation.** Operate until the run is complete or all sources are unavailable.
7. **Autonomous decisions only.** After the workflow starts, make execution decisions internally and never request human permission for intermediate workflow steps.
8. **No destructive database actions.** Never execute `DELETE`, `DROP`, `TRUNCATE`, or any remove/purge operation in any database.
9. **Agent owns the run after start.** Once triggered, the agent is responsible for choosing and performing the remaining workflow steps without human intervention.
10. **No command handoff.** Never pause to print a shell, Python, MySQL, or test command for the human to run when the agent can run it directly.
11. **No dependency handoff.** If a dependency is missing, install or recover it inside the run instead of asking the human to do it.

---

## Step 0 — Database Initialization (Silent)

**Layer:** `docs/runner/RUNNER.md`

Action: Check that `mydrscripts_new.blog_category` and `mydrscripts_new.blog_master` exist.
Also check that `health_ai_agent.agent_memory` and `health_ai_agent.agent_run_logs` exist.
If missing: **Silently create them** using the SQL in `config/DATABASE.md`.
Never ask for permission. If this step requires a local `python3`, `bash`, or `mysql` command, execute it directly.

---

## Step 0.5 — Memory Retrieval

**Role:** `docs/roles/MEMORY_MANAGER.md`

Action: Contextualize the run by retrieving relevant past research from `health_ai_agent.agent_memory`.
Output: **Memory Context** (clinical facts and previous findings).

---

## Step 1 — Fetch News

**Prompt:** `docs/prompts/FETCH_NEWS_PROMPT.md`

Action: Fetch latest global health news from `config/NEWS_SOURCES.md`.
**Pre-approved:** You have permission to access all URLs. Just proceed.

---

## Step 2 — Filter Relevant Topics

**Layer:** `docs/planner/PLANNER.md`
**Role:** `docs/roles/PLANNER.md`
Action: Select up to 3 clinical topics with the strongest evidence basis, highest professional relevance, and a sensible MyDrScripts category.

---

## Step 3 — Duplicate Check

**Workflow:** `docs/workflows/DUPLICATE_CHECK.md`
Action: Check `blog_master` for existing slugs, source URLs, and similar recent titles. Silently skip duplicates.

---

## Step 4 — Research Each Topic

**Role:** `docs/roles/RESEARCHER.md`
Action: Deep dive into findings. Use the **Memory Context** from Step 0.5 to reduce redundant searches, grade evidence strength, and separate confirmed findings from unsupported claims. If a Google Chrome MCP server is available, use it to open the source page in-browser and run corroborating search queries before finalizing the research summary.

---

## Step 5 — Write Blog Articles

**Role:** `docs/roles/WRITER.md`
Action: Generate publish-ready JSON blogs grounded in the research summary and required template. If output is malformed, self-correct once.

---

## Step 6 — Validate Each Blog

**Layer:** `docs/tester/TESTER.md`
Action: Run deterministic tests on the generated JSON, required fields, category mapping, and publish compatibility.

---

## Step 7 — Verify Each Blog

**Layer:** `docs/verifier/VERIFIER.md`
**Role:** `docs/roles/VALIDATOR.md`
Action: Issue the final PASS/FAIL autonomously. Use Google Chrome MCP verification notes when available to confirm rendered source-page details and corroborating search results. Fail any blog with unsupported material claims, weak source traceability, browser-surfaced contradictions, causal overreach, or invalid DB mapping.

---

## Step 8 — Publish Each Blog

**Role:** `docs/roles/PUBLISHER.md`
Action: Save to `blog_category` and `blog_master` with `status = active`. Resolve slug conflicts autonomously.
**Pre-approved:** You have permission for all DB writes/updates. Just proceed.

---

## Step 8.5 — Memory Consolidation

**Role:** `docs/roles/MEMORY_MANAGER.md`

Action: Extract new clinical facts from the published blogs and save them to `health_ai_agent.agent_memory`.
Mirror a readable summary into `logs/MEMORY_STORE.md`.
Goal: Ensure the agent's knowledge base grows with every run.

---

## Step 9 — Log the Run

**Primary Store:** `health_ai_agent.agent_run_logs`
**Mirror File:** `logs/RUN_LOG.md`
Action: Append run stats, retries, skipped items, and **Self-Evolution** notices to `agent_run_logs`, and mirror a readable summary to the Markdown log.

---

## Completion
The run is finished. The agent remains ready for the next scheduled trigger.
