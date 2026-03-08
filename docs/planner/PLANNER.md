# Planner Layer

## Purpose

This layer decides which health topics should become MyDrScripts blog posts and which category each article belongs to.

## Responsibilities

1. Review fetched health news.
2. Score each topic by evidence strength, urgency, and healthcare relevance.
3. Recommend a publish category for each selected topic.
4. Pass only high-value, non-duplicate topics into execution.

## Required Output

For each selected topic, provide:
- topic name
- source URL
- key insight
- evidence basis
- recommended category name
- recommended category slug

## Category Guidance

Use practical MyDrScripts blog categories such as:
- infectious-disease
- public-health
- clinical-guidelines
- therapeutics
- medical-research
- healthcare-operations

## Rule

If a topic cannot be assigned to a sensible category, do not advance it for publishing.