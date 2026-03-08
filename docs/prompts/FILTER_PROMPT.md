# Prompt: Filter Topics

## Purpose
Step 2: Select top 3 clinical topics.

## ⚠️ Autonomous Decision
- One-shot filtering. You are the sole judge.
- Prioritize: Evidence strength, outbreaks, clinical guidelines, actionable research.

## Prompt
```
Filter raw news for medical/clinical value.
Rule 1: Rank by [Evidence Strength > Urgency > Clinical Impact > Novelty].
Rule 2: Reject topics that are only secondary summaries unless the primary source is identifiable.
Rule 3: Select top 3 topics maximum.
If zero relevant: "PLAN: NO RELEVANT TOPICS FOUND".

Output Schema:
PLAN:
1. Topic: [Name]
   Source: [URL]
   Insight: [Factual summary]
   Evidence Basis: [Official / Peer-reviewed / Institutional / Cross-check required]
   Category: [Category Name]
   Category Slug: [category-slug]
   Focus: [Clinical value]
...
```
