# Prompt: Fetch News

## Purpose

Step 1: Fetch global health news.

## ⚠️ Non-Negotiable Autonomy

- **Pre-approved:** Permanent permission to access all URLs.
- **Decision:** You choose sources. Never ask.
- **Integrity:** Return only articles and fields you can directly observe. Do not infer missing details.

## Prompt

```
Fetch health news from config/NEWS_SOURCES.md published within the last 24 hours.
Prefer Tier 1, Tier 1A, and Tier 2 sources; only use Tier 3 when it can be cross-verified when possible.
Include only English items related to public health, medical research, disease outbreaks, healthcare systems, or medical innovation.
Exclude: opinion/editorial pieces, political commentary without direct health relevance, sports, and sensational or miracle-cure framing.
Exclude items without a credible original source.
Required Fields: [title, url, source, published_at, description]. Preserve the exact source URL for downstream Google Chrome MCP verification/search.
If a required field is missing, discard the article instead of guessing.
Format: Numbered list.
If zero results: "NO ARTICLES FOUND".
Limit: 20 most relevant.
```
