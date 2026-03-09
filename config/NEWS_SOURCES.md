# News Sources Configuration

## Overview

The agent fetches health news from these trusted sources. Sources are prioritized in order of **credibility and authority**.

---

# Tier 1 — Official Global Health Bodies (Highest Priority)

| Source                                 | URL                                         | Type      |
| -------------------------------------- | ------------------------------------------- | --------- |
| World Health Organization              | `https://www.who.int/news`                  | RSS / Web |
| Centers for Disease Control            | `https://www.cdc.gov/media/releases`        | RSS / Web |
| National Institutes of Health          | `https://www.nih.gov/news-events`           | RSS / Web |
| European Centre for Disease Prevention | `https://www.ecdc.europa.eu/en/news-events` | Web       |

---

# Tier 1A — Official Australian Health Authorities (High Priority)

| Source                                     | URL                                  | Type |
| ------------------------------------------ | ------------------------------------ | ---- |
| Australian Government Department of Health | `https://www.health.gov.au/news`     | Web  |
| Therapeutic Goods Administration (TGA)     | `https://www.tga.gov.au/news`        | Web  |
| Australian Institute of Health and Welfare | `https://www.aihw.gov.au/news`       | Web  |
| NSW Health                                 | `https://www.health.nsw.gov.au/news` | Web  |
| Victoria Department of Health              | `https://www.health.vic.gov.au/news` | Web  |

---

# Tier 2 — Medical Journals

| Source                          | URL                                     | Type |
| ------------------------------- | --------------------------------------- | ---- |
| The Lancet                      | `https://www.thelancet.com/news`        | Web  |
| New England Journal of Medicine | `https://www.nejm.org/medical-news`     | Web  |
| BMJ (British Medical Journal)   | `https://www.bmj.com/news`              | Web  |
| JAMA Network                    | `https://jamanetwork.com/news`          | Web  |
| Medical Journal of Australia    | `https://www.mja.com.au/news-and-views` | Web  |

---

# Tier 3 — Reputable Health News Sites

| Source                 | URL                                  | Type |
| ---------------------- | ------------------------------------ | ---- |
| Medscape News          | `https://www.medscape.com/news`      | Web  |
| HealthDay News         | `https://consumer.healthday.com`     | Web  |
| ABC Health (Australia) | `https://www.abc.net.au/news/health` | Web  |
| SBS Health             | `https://www.sbs.com.au/news/health` | Web  |

---

# Filtering Rules

Only accept articles that:

- Were published within the last **72 hours**
- Come from **Tier 1, Tier 1A, or Tier 2** sources (preferred)
- Tier 3 sources must be **cross-verified with Tier 1/2 when possible**
- Have a **non-empty `description` field**
- Are written in **English**
- Are related to **public health, medical research, disease outbreaks, healthcare systems, or medical innovation**

---

# Exclusions

Exclude articles that:

- Are **opinion/editorial pieces**
- Are **political commentary without direct health relevance**
- Are **sports-related**
- Contain **sensational or miracle cure claims**
- Lack a **credible original source**

---

# Notes

- Prefer **official announcements and research releases**.
- Prefer **RSS feeds or direct publication pages** over aggregators.
- Preserve the **exact source URL** for downstream verification.
- If a source is unavailable, **skip it and proceed to the next**.
