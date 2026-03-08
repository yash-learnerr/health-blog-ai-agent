# News Sources Configuration

## Overview

The agent fetches health news from these trusted sources. They are prioritized in order of credibility.

---

## Tier 1 — Official Health Bodies (Highest Priority)

| Source | URL | Type |
|---|---|---|
| World Health Organization | `https://www.who.int/news` | RSS / Web |
| Centers for Disease Control | `https://www.cdc.gov/media/releases` | RSS / Web |
| National Institutes of Health | `https://www.nih.gov/news-events` | RSS / Web |
| European Centre for Disease Prevention | `https://www.ecdc.europa.eu/en/news-events` | Web |

---

## Tier 2 — Medical Journals

| Source | URL | Type |
|---|---|---|
| The Lancet | `https://www.thelancet.com/news` | Web |
| New England Journal of Medicine | `https://www.nejm.org/medical-news` | Web |
| BMJ (British Medical Journal) | `https://www.bmj.com/news` | Web |
| JAMA Network | `https://jamanetwork.com/news` | Web |

---

## Tier 3 — Reputable Health News Sites

| Source | URL | Type |
|---|---|---|
| Medscape News | `https://www.medscape.com/news` | Web |
| HealthDay News | `https://consumer.healthday.com` | Web |

---

## Filtering Rules

Only accept articles that:
- Were published within the last **24 hours**
- Come from a **Tier 1 or Tier 2** source (preferred), or a verified Tier 3 source
- Have a non-empty `description` field
- Are written in **English**

---

## Notes

- Always cross-reference findings from Tier 3 sources against Tier 1 or Tier 2.
- Prefer direct web pages or RSS feeds over third-party aggregation layers.
- Do not use social media, blogs, or unverified news sites as sources.
- If a source is unavailable, skip it and use the next available source.