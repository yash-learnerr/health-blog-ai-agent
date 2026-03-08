# Prompt: Validate Blog

## Purpose
Step 6: Autonomous quality gate.

## ⚠️ Decision Rule
- Direct PASS/FAIL. No human review.
- If FAIL, Writer resubmits once.
- Unsupported major claims require FAIL.

## Prompt
```
Input: [BLOG JSON] + [RESEARCH SUMMARY] + [Browser Verification Notes if available]
Rubric: MEDICAL_EVIDENCE_RUBRIC.md
Check:
1. Healthcare relevance?
2. Factual/Verified?
3. No passive voice/filler?
4. 700+ words?
5. All required sections present, including Sources?
6. Metadata valid, including category_name?
7. Every material claim traceable to evidence?
8. No invented statistics, quotes, recommendations, or study details?
9. Preliminary evidence labeled with appropriate caution?
10. No causal overreach beyond the evidence type?
11. If Google Chrome MCP verification was available, does it confirm the rendered source content or clearly document contradictions?
12. Compatible with `blog_category` and `blog_master` publish contract?

Output:
VALIDATION: [PASS/FAIL]
Reason: [List if FAIL]
Fix: [Instruction if FAIL]
```
