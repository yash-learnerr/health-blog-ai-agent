# Verifier Layer

## Purpose

This layer performs the final publication gate after Tester checks pass.

## Responsibilities

1. Confirm evidence integrity using `docs/verifier/MEDICAL_EVIDENCE_RUBRIC.md`.
2. Confirm the topic is not a duplicate in `blog_master`.
3. Review Google Chrome MCP browser/search corroboration notes when available.
4. Confirm the article is appropriate for MyDrScripts publication.
5. Confirm the category choice is sensible.
6. Approve or reject publication.

## Fail Conditions

- unsupported material claims
- contradictions surfaced by Google Chrome MCP browser/search verification that were not resolved
- invented statistics, quotations, or study details
- causal overreach
- duplicate slug or duplicate source URL
- invalid or missing category assignment
- publish target not aligned with `blog_category` / `blog_master`

## Rule

Only a fully supported, non-duplicate, category-mapped article may proceed to the Publisher.
