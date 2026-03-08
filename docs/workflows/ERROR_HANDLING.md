# Error Handling Workflow

## ⚠️ Core Rule

**No routine error should stop the agent. Every error must have a defined autonomous resolution.**

The agent does not report an error to a human and wait. It resolves, logs, and continues whenever possible.

---

## Execution Errors

### Step Failure / Timeout / Temporary Overload

**Trigger:** A workflow step fails, times out, or returns unusable output.

**Resolution — follow this order immediately, without pausing:**

```text
Step 1: Log the failure with timestamp, step name, and reason.

Step 2: Wait briefly and retry the same step.

Step 3: If helpful, simplify the query or narrow the scope while keeping the same objective.

Step 4: If the retry succeeds, log the recovery and continue.

Step 5: If the retry fails again, log that the current item is being skipped.

Step 6: Continue the workflow with the remaining items.
```

Never ask the user for intervention. Do **not** hand work off to another runner, provider, or model family.

### Malformed Output

**Resolution:**

- Parse what you can from the output.
- If JSON or formatting is malformed, repair it once yourself.
- If the result is still unusable, skip that topic only and continue.

---

## Source / Network Errors

### News Fetch Failure (one source)

- Skip that source.
- Try the next source in `config/NEWS_SOURCES.md`.
- Continue without reporting to a human.

### News Fetch Failure (all sources)

- Retry all sources once with narrower or simpler retrieval.
- If still failing, log `ERROR: All news sources unreachable` and stop the run.
- This is the **only** case where the run may stop due to an operational error.

### Web Search Fails During Research

- Retry once with a shorter or alternate query.
- If still failing, use the original source article and existing memory only.
- Never pause to ask for different search terms.

---

## Content Errors

### No Relevant Topics Found

- Log: `INFO: No relevant health topics this run.`
- Stop the run gracefully. This is not an error.

### All Topics Are Duplicates

- Log: `INFO: All planned topics already published.`
- Stop the run gracefully. This is not an error.

### Writer Produces Invalid Blog JSON

- Attempt self-correction once.
- If still invalid after self-correction, skip this topic and continue.
- Log: `WARN: Skipped topic [name] — invalid Writer output after retry.`

### Validation Fails Twice

- Skip this topic.
- Log: `WARN: Skipped blog [title] — failed validation twice.`
- Continue to the next blog.

---

## Database Errors

### DB Insert Fails

- Log: `ERROR: DB insert failed for slug [slug]. Reason: [message]`
- Do not retry indefinitely.
- Continue with remaining blogs.

### Slug Already Exists (UNIQUE constraint)

- Auto-generate a new slug by appending `-2`, `-3`, and so on.
- Retry the insert with the new slug.
- No human input is needed.

### DB Connection Failure

- Retry the connection once after 5 seconds.
- If still failing, log the error and skip publishing for this run.
- Do not stop research or writing if publishing is the only blocked step.

---

## Third-Party Access Decisions

The agent makes all third-party access decisions autonomously:

| Decision | Agent Action |
|---|---|
| Which news source to use | Try sources in tier order and continue if one fails |
| Which search query to use | Generate the best query for the topic and refine once if needed |
| Which evidence to trust | Prefer official and peer-reviewed sources over lower-tier reporting |
| Whether to insert into DB | Insert only if validation passes |
| Whether to retry a failed step | Retry once, then skip the current item if still blocked |

**Never ask a human for any of these decisions.**

---

## Logging All Errors

Every error must be appended to `health_ai_agent.agent_run_logs` and may be mirrored to `logs/RUN_LOG.md`:

```text
- Errors: [description of what failed and how it was resolved]
- Retries: [step, reason, retry outcome]
- Skipped Items: [topic or blog skipped and why]
```