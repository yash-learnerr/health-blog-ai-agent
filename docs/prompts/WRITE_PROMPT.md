# Prompt: Write Blog

## Purpose
Step 5: Generate professional JSON blog.

## ⚠️ Execution Rule
- No draft feedback. One-shot completion.
- If output is malformed, self-correct once before giving up.
- Use only evidence carried in the input. If support is insufficient, omit the claim.

## Prompt
```
Input: [RESEARCH SUMMARY]
Spec: docs/templates/BLOG_TEMPLATE.md
Word Count: 700-1200 words.
Tone: Medical/Professional.
Constraints: Do not add new studies, numbers, quotes, or recommendations not present in the input.
Constraints: Preserve uncertainty and label preliminary findings carefully.

JSON Output Only:
{
  "category_name": "",
  "title": "",
  "slug": "",
  "summary": "",
  "content": "MD content with 5 mandatory sections plus a Sources section with at least 2 references",
  "keywords": []
}
```
