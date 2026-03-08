# Database Configuration & Initialization

## Overview
The agent uses **two MySQL databases** with separate responsibilities.

### Publish database
- database: `mydrscripts_new`
- category table: `blog_category`
- blog table: `blog_master`
- live status value: `active`

### Operational database
- database: `health_ai_agent`
- memory table: `agent_memory`
- run log table: `agent_run_logs`

Markdown files under `logs/` remain as human-readable mirrors of the operational data.

---

## Connection Settings
- **Database target selector:** `DATABASE_ACCESS` (`local`, `staging`, or `production`; default: `local`)
- **Host:** `DB_HOST` (default: `localhost`)
- **Port:** `DB_PORT` (default: `3306`)
- **User:** `DB_USER` (default: `root`)
- **Password:** `DB_PASSWORD` (default: ``)
- **Publish Database:** `PUBLISH_DB_NAME` (default: `mydrscripts_new`)
- **Operational Database:** `AGENT_DB_NAME` (default: `health_ai_agent`)

For non-local targets, use the matching prefixed variables:

- staging: `STAGING_DB_HOST`, `STAGING_DB_PORT`, `STAGING_DB_USER`, `STAGING_DB_PASSWORD`, `STAGING_PUBLISH_DB_NAME`, `STAGING_AGENT_DB_NAME`
- production: `PRODUCTION_DB_HOST`, `PRODUCTION_DB_PORT`, `PRODUCTION_DB_USER`, `PRODUCTION_DB_PASSWORD`, `PRODUCTION_PUBLISH_DB_NAME`, `PRODUCTION_AGENT_DB_NAME`

Set these in environment variables in your execution environment:

```bash
export DATABASE_ACCESS=local
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=your_user
export DB_PASSWORD=your_password
export PUBLISH_DB_NAME=mydrscripts_new
export AGENT_DB_NAME=health_ai_agent
```

---

## Initialization Rule
At the start of every run, the Runner must verify:

1. `mydrscripts_new.blog_category`
2. `mydrscripts_new.blog_master`
3. `health_ai_agent.agent_memory`
4. `health_ai_agent.agent_run_logs`

If any required table is missing, the agent may create it using the SQL below.

---

## Initialization SQL

```sql
CREATE DATABASE IF NOT EXISTS mydrscripts_new;
USE mydrscripts_new;

CREATE TABLE IF NOT EXISTS blog_category (
  createdAt BIGINT NULL,
  updatedAt BIGINT NULL,
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  UNIQUE KEY uq_blog_category_name (name)
);

CREATE TABLE IF NOT EXISTS blog_master (
  createdAt BIGINT NULL,
  updatedAt BIGINT NULL,
  id INT PRIMARY KEY AUTO_INCREMENT,
  blog_name VARCHAR(512) NOT NULL,
  category_id INT NOT NULL,
  meta_title VARCHAR(512),
  description LONGTEXT,
  meta_description TEXT,
  meta_tags TEXT,
  file VARCHAR(500) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  slug VARCHAR(512) UNIQUE,
  CONSTRAINT fk_blog_master_category
    FOREIGN KEY (category_id) REFERENCES blog_category(id)
);

CREATE DATABASE IF NOT EXISTS health_ai_agent;
USE health_ai_agent;

CREATE TABLE IF NOT EXISTS agent_memory (
  id INT PRIMARY KEY AUTO_INCREMENT,
  topic_slug VARCHAR(512),
  category_name VARCHAR(255),
  memory_key VARCHAR(255) NOT NULL,
  verified_fact TEXT NOT NULL,
  source_url VARCHAR(1024),
  confidence VARCHAR(32),
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_run_logs (
  id INT PRIMARY KEY AUTO_INCREMENT,
  run_id VARCHAR(255) NOT NULL,
  step VARCHAR(128) NOT NULL,
  item_slug VARCHAR(512),
  status VARCHAR(64) NOT NULL,
  message TEXT,
  details_json JSON,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Publish Contract
1. Final content must be inserted into `blog_master`.
2. Each blog must reference a valid row in `blog_category`.
3. Both category and blog rows must use `status = active` for live content.
4. Duplicate checking must be performed against `blog_master` before insert.
5. Existing databases must be migrated non-destructively: rename legacy publish columns where safe, add the new columns, and do not auto-drop legacy columns during migration.

---

## Operational Contract
1. Reusable memory must be stored in `health_ai_agent.agent_memory`.
2. Run lifecycle details, retries, skips, and errors must be stored in `health_ai_agent.agent_run_logs`.
3. `logs/MEMORY_STORE.md` and `logs/RUN_LOG.md` may mirror the operational DB contents for human inspection.
4. Dashboard or review pages must read operational status from `AGENT_DB_NAME` tables, not from Markdown mirrors.

---

## Rules
1. Never ask for permission to verify or create the required publish or operational tables.
2. Never redirect final published content to any table other than `mydrscripts_new.blog_category` and `mydrscripts_new.blog_master`.
3. Keep operational memory and run tracking in `health_ai_agent`.
4. Treat the Markdown logs under `logs/` as mirrors, not the primary source of truth.
5. Never execute `DELETE`, `DROP`, `TRUNCATE`, or any remove/purge operation in either database.
