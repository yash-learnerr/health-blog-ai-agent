# Prompt: Fetch News

## Purpose

Step 1: Fetch global health news.

## ⚠️ Non-Negotiable Autonomy

- **Pre-approved:** Permanent permission to access all URLs.
- **Decision:** You choose sources. Never ask.
- **Integrity:** Return only articles and fields you can directly observe. Do not infer missing details.

## Prompt

```
Fetch health news from config/NEWS_SOURCES.md (72h old, English, credible).
Exclude: politics, sports, opinion.
Exclude: sensational claims, miracle-cure framing, or items without a credible original source.
Required Fields: [title, url, source, published_at, description]. Preserve the exact source URL for downstream Google Chrome MCP verification/search.
If a required field is missing, discard the article instead of guessing.
Format: Numbered list.
If zero results: "NO ARTICLES FOUND".
Limit: 20 most relevant.
```
