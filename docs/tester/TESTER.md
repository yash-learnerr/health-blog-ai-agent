# Tester Layer

## Purpose

This layer performs deterministic checks before final verification.

## Required Checks

1. Output is valid JSON.
2. Required fields exist: `title`, `slug`, `category_name`, `summary`, `content`, `keywords`.
3. `slug` is URL-safe.
4. `category_name` is non-empty and publication-safe.
5. `content` includes all required sections plus `Sources`.
6. `keywords` contains 5–8 items.
7. Content length meets the minimum requirement.

## Database Compatibility Checks

1. The output can map to `blog_category` and `blog_master`.
2. The final publish status is `active`.
3. The category can be created or matched before the blog insert.

## Rule

If any deterministic check fails, return the blog to the Writer before the Verifier step.