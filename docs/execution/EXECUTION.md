# Execution Layer

## Purpose

This layer defines the ordered pipeline for one full content-generation run.

## Ordered Flow

1. Runner initializes environment and both DB targets.
2. Memory Manager reads reusable facts from `health_ai_agent.agent_memory`.
3. Fetch news from trusted sources.
4. Planner selects topics and categories.
5. Duplicate check runs against `blog_master`.
6. Researcher produces evidence-grounded research and uses Google Chrome MCP browser/search verification when available.
7. Writer generates publish-ready JSON.
8. Tester checks schema, category, and required fields.
9. Verifier checks evidence integrity, Google Chrome MCP corroboration notes when available, and publication safety.
10. Publisher inserts category/blog rows with `status = active`.
11. Memory Manager stores reusable facts in `health_ai_agent.agent_memory` and mirrors them into `logs/MEMORY_STORE.md`.
12. Log the run in `health_ai_agent.agent_run_logs` and mirror a summary into `logs/RUN_LOG.md`.

## Rule

No article may reach publishing unless it passes both the Tester and Verifier layers.