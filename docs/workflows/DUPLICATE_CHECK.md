# Duplicate Check Workflow

## Purpose

Before generating a blog, verify that the topic has not already been published into `mydrscripts_new.blog_master`.

---

## When to Run

Run this workflow during **Step 3 of MAIN_WORKFLOW.md**, after the Planner has selected topics and proposed a category.

---

## Input

For each planned topic, you need:

- `topic name`
- `source URL`
- `proposed slug`
- `recommended category_name`

---

## Database Schema Reference

Based on `config/DATABASE_TABLES.md`, the relevant publish table is:

### blog_master table

- `createdAt`
- `updatedAt`
- `id`
- `blog_name`
- `category_id`
- `meta_title`
- `description`
- `meta_description`
- `meta_tags`
- `file`
- `status`
- `slug`

---

## Check 1 — Slug Match in blog_master

```sql
SELECT id, blog_name, createdAt
FROM blog_master
WHERE slug = '[proposed-slug]'
  AND status = 'active';
```

If a row is returned → **Duplicate. Skip this topic.**

---

## Check 2 — Source URL Match in blog_master (legacy installs only)

```sql
SELECT id, blog_name, slug
FROM blog_master
WHERE source_url = '[article-url]'
  AND status = 'active';
```

If the legacy `source_url` column exists and a row is returned → **Duplicate. Skip this topic.**

---

## Check 3 — Recent Title Similarity

```sql
SELECT blog_name, slug
FROM blog_master
WHERE createdAt >= ((UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 60 DAY))) * 1000)
  AND status = 'active'
ORDER BY createdAt DESC;
```

Compare the proposed topic against recent active titles. Treat it as a duplicate if it covers the same disease/condition and the same development.

---

## Output

For each topic, return one of:

```text
DUPLICATE CHECK: UNIQUE — Proceed with blog generation.
```

or

```text
DUPLICATE CHECK: DUPLICATE — Skipping.
Reason: [slug match / source URL / title similarity]
Matched Record: [id or title of existing record]
```

---

## Rules

- Run all checks in sequence.
- Even one failed check means the topic is a duplicate.
- Log each duplicate skip in `health_ai_agent.agent_run_logs` and mirror it in `logs/RUN_LOG.md` if needed.
- Never bypass this check before publishing to `blog_master`.
