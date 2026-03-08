# Database Table Definitions

## Publish Database: `mydrscripts_new`

## Table: blog_category
Stores the category assigned to each published health article.

| Column | Type | Description |
|---|---|---|
| createdAt | BIGINT | Created timestamp |
| updatedAt | BIGINT | Updated timestamp |
| id | INT PRIMARY KEY AUTO_INCREMENT | Unique category ID |
| name | VARCHAR(255) NOT NULL | Human-readable category name |
| status | VARCHAR(32) NOT NULL DEFAULT 'active' | Category status |

---

## Table: blog_master
Stores the final published blog content for MyDrScripts.

| Column | Type | Description |
|---|---|---|
| createdAt | BIGINT | Created timestamp |
| updatedAt | BIGINT | Updated timestamp |
| id | INT PRIMARY KEY AUTO_INCREMENT | Unique blog ID |
| blog_name | VARCHAR(512) NOT NULL | Blog title |
| category_id | INT NOT NULL | Reference to `blog_category.id` |
| meta_title | VARCHAR(512) | SEO/meta title |
| description | LONGTEXT | Full blog content |
| meta_description | TEXT | Summary or excerpt |
| meta_tags | TEXT | Comma-separated meta tags |
| file | VARCHAR(500) NULL | Stored published file/media URL |
| status | VARCHAR(32) NOT NULL DEFAULT 'active' | Live publication status |
| slug | VARCHAR(512) UNIQUE | URL slug |

---

## Publishing Rule
- All final articles must be stored in `blog_master`.
- Every published article must point to an active row in `blog_category`.
- Live records must use `status = active`.
- Duplicate checks must be run against `blog_master` before insert.

---

## Operational Database: `health_ai_agent`

## Table: agent_memory
Stores reusable verified facts and memory snippets for future runs.

| Column | Type | Description |
|---|---|---|
| id | INT PRIMARY KEY AUTO_INCREMENT | Unique memory ID |
| topic_slug | VARCHAR(512) | Related topic or blog slug |
| category_name | VARCHAR(255) | Assigned content category |
| memory_key | VARCHAR(255) NOT NULL | Memory lookup key |
| verified_fact | TEXT NOT NULL | Reusable verified fact |
| source_url | VARCHAR(1024) | Evidence source URL |
| confidence | VARCHAR(32) | Evidence confidence level |
| status | VARCHAR(32) NOT NULL DEFAULT 'active' | Memory row status |
| created_at | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | Created timestamp |
| updated_at | TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | Updated timestamp |

---

## Table: agent_run_logs
Stores operational logs for runs, retries, skips, and failures.

| Column | Type | Description |
|---|---|---|
| id | INT PRIMARY KEY AUTO_INCREMENT | Unique log ID |
| run_id | VARCHAR(255) NOT NULL | Run identifier |
| step | VARCHAR(128) NOT NULL | Workflow step name |
| item_slug | VARCHAR(512) | Related blog or topic slug |
| status | VARCHAR(64) NOT NULL | Log status |
| message | TEXT | Human-readable log message |
| details_json | JSON | Structured details for debugging |
| request_count | INT NOT NULL DEFAULT 0 | Number of LLM/API requests represented by this log row |
| prompt_tokens | BIGINT NOT NULL DEFAULT 0 | Prompt/input token usage for the row |
| completion_tokens | BIGINT NOT NULL DEFAULT 0 | Completion/output token usage for the row |
| total_tokens | BIGINT NOT NULL DEFAULT 0 | Total token usage for the row |
| created_at | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | Created timestamp |

---

## Operational Rule
- Reusable memory must be stored in `agent_memory`.
- Run logs, retries, skips, and failures must be stored in `agent_run_logs`.
- Markdown files in `logs/` may mirror these records for readability.
