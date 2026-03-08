# Prompt: Research Topic

## Purpose
Step 4: Deep-dive research.

## ⚠️ Token Saving Logic
- Use **Memory Context** (Step 0.5) to avoid redundant search.
- Focus ONLY on data not present in memory.
- Never fill evidence gaps by guessing.

## Prompt
```
Topic: [NAME]
Memory Context: [DATA]
Rubric: MEDICAL_EVIDENCE_RUBRIC.md

Task: Research MISSING clinical data.
Required: [Statistics, Trial Methodology, Official Statements, Clinical Impact].
Required: If Google Chrome MCP is available, search the topic/title in-browser, open corroborating pages, and compare the rendered source page with the fetched source URL.
Rule: No bluff/sensationalism. Strict factual accuracy only.
Rule: Every major claim must include source type and confidence.
Rule: Unsupported or weakly supported claims must be listed as unusable, not upgraded into facts.

Output Schema:
RESEARCH SUMMARY:
Evidence Grade: [High / Moderate / Low / Mixed]
Confirmed Findings:
- Claim: [Supported statement]
  Evidence Type: [Official guidance / Systematic review / RCT / Observational study / Institutional report / Reputable reporting]
  Confidence: [High / Moderate / Low]
  Source: [Source Name + URL]
Preliminary or Conflicting Findings:
- [Claim + why caution is required]
Do-Not-Use Claims:
- [Unsupported or unverifiable claim]
Public Health Impact: [Factual]
Clinical Relevance: [Direct action for MDs]
Limitations: [Caveats]
Browser Verification:
- Google Chrome MCP Used: [Yes / No]
- Search Queries Run: [query + purpose]
- Pages Opened: [title + URL]
- Contradictions or Missing Details: [none or list]
References: [Source Name + URL]
```
