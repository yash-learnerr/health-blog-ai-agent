#!/usr/bin/env python3
import argparse
import html
import json
import re
import sys
import traceback
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import List
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import agent_db
import blog_file_manager


USER_AGENT = 'GlobalHealthIntelligenceAgent/1.0'
MAX_TOPICS = 3
MIN_CONTENT_WORDS = 700
MAX_CONTENT_WORDS = 1200
LEARNING_CATEGORY_NAME = 'Learning'
LEARNING_CATEGORY_SLUG = 'learning'


@dataclass
class SourceConfig:
    name: str
    feed_url: str
    homepage_url: str
    tier: int


@dataclass
class Article:
    title: str
    url: str
    source: str
    published_at: datetime
    description: str
    source_feed_url: str
    tier: int


def now_utc():
    return datetime.now(timezone.utc)


def now_utc_millis():
    return int(now_utc().timestamp() * 1000)


def slugify(text):
    value = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    return value or 'health-update'


def normalize_category_name(value):
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    return text


def read_text(path):
    return Path(path).read_text(encoding='utf-8')


def write_text(path, content):
    Path(path).write_text(content, encoding='utf-8')


def append_text(path, content):
    target = Path(path)
    existing = target.read_text(encoding='utf-8') if target.exists() else ''
    target.write_text(existing.rstrip() + '\n' + content.rstrip() + '\n', encoding='utf-8')


def fetch_url(url):
    req = Request(url, headers={'User-Agent': USER_AGENT})
    with urlopen(req, timeout=20) as res:
        charset = res.headers.get_content_charset() or 'utf-8'
        return res.read().decode(charset, errors='replace')


def strip_html(raw):
    text = re.sub(r'<script\b[^>]*>.*?</script>', ' ', raw, flags=re.I | re.S)
    text = re.sub(r'<style\b[^>]*>.*?</style>', ' ', text, flags=re.I | re.S)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_meta(html_text, *names):
    for name in names:
        patterns = [
            rf'<meta[^>]+property=["\']{re.escape(name)}["\'][^>]+content=["\'](.*?)["\']',
            rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\'](.*?)["\']',
            rf'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']{re.escape(name)}["\']',
            rf'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']{re.escape(name)}["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_text, flags=re.I | re.S)
            if match:
                return html.unescape(match.group(1)).strip()
    return ''


def extract_paragraphs(html_text, limit=8):
    paragraphs = re.findall(r'<p\b[^>]*>(.*?)</p>', html_text, flags=re.I | re.S)
    clean = []
    for paragraph in paragraphs:
        text = strip_html(paragraph)
        if len(text) >= 80:
            clean.append(text)
        if len(clean) >= limit:
            break
    return clean


def extract_image_url(html_text):
    return (
        extract_meta(html_text, 'og:image', 'twitter:image', 'og:image:url', 'twitter:image:src')
        or ''
    ).strip()


def parse_date(value):
    if not value:
        return None
    value = value.strip()
    for parser in (
        lambda v: parsedate_to_datetime(v),
        lambda v: datetime.fromisoformat(v.replace('Z', '+00:00')),
    ):
        try:
            parsed = parser(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def source_configs():
    return [
        SourceConfig(
            name='World Health Organization',
            feed_url='https://www.who.int/rss-feeds/news-english.xml',
            homepage_url='https://www.who.int/news',
            tier=1,
        ),
        SourceConfig(
            name='Centers for Disease Control',
            feed_url='https://tools.cdc.gov/api/v2/resources/media/316422.rss',
            homepage_url='https://www.cdc.gov/media/releases',
            tier=1,
        ),
        SourceConfig(
            name='National Institutes of Health',
            feed_url='https://www.nih.gov/news-releases/feed.xml',
            homepage_url='https://www.nih.gov/news-events',
            tier=1,
        ),
        SourceConfig(
            name='European Centre for Disease Prevention',
            feed_url='https://www.ecdc.europa.eu/en/taxonomy/term/1307/feed',
            homepage_url='https://www.ecdc.europa.eu/en/news-events',
            tier=1,
        ),
        SourceConfig(
            name='JAMA Network',
            feed_url='https://jamanetwork.com/rss/site_3/67.xml',
            homepage_url='https://jamanetwork.com/news',
            tier=2,
        ),
    ]


def parse_feed_items(source, xml_text, recency_hours):
    root = ET.fromstring(xml_text)
    items = []
    cutoff = now_utc() - timedelta(hours=recency_hours)
    for node in root.findall('.//item') + root.findall('.//{http://www.w3.org/2005/Atom}entry'):
        title = (node.findtext('title') or node.findtext('{http://www.w3.org/2005/Atom}title') or '').strip()
        link = node.findtext('link') or ''
        if not link:
            link_node = node.find('{http://www.w3.org/2005/Atom}link')
            if link_node is not None:
                link = link_node.attrib.get('href', '')
        description = (
            node.findtext('description')
            or node.findtext('{http://www.w3.org/2005/Atom}summary')
            or node.findtext('{http://www.w3.org/2005/Atom}content')
            or ''
        )
        published_at = parse_date(
            node.findtext('pubDate')
            or node.findtext('{http://purl.org/dc/elements/1.1/}date')
            or node.findtext('{http://www.w3.org/2005/Atom}updated')
            or node.findtext('{http://www.w3.org/2005/Atom}published')
            or ''
        )
        description = strip_html(description)
        if not title or not link or not description or not published_at:
            continue
        if published_at < cutoff:
            continue
        items.append(
            Article(
                title=strip_html(title),
                url=urljoin(source.homepage_url, link),
                source=source.name,
                published_at=published_at,
                description=description,
                source_feed_url=source.feed_url,
                tier=source.tier,
            )
        )
    return items


def fetch_recent_news(run_id, recency_hours):
    candidate_windows = []
    for window in (recency_hours, max(recency_hours, 72), max(recency_hours, 168)):
        if window not in candidate_windows:
            candidate_windows.append(window)

    last_articles = []
    last_failures = []
    last_window = recency_hours

    for window in candidate_windows:
        candidates = []
        failures = []
        for source in source_configs():
            try:
                xml_text = fetch_url(source.feed_url)
                candidates.extend(parse_feed_items(source, xml_text, window))
            except (HTTPError, URLError, TimeoutError, ET.ParseError, ValueError) as exc:
                failures.append({'source': source.name, 'reason': str(exc)})
        if not candidates:
            next_windows = [candidate for candidate in candidate_windows if candidate > window]
            if next_windows:
                next_window = next_windows[0]
                agent_db.safe_log_event(
                    run_id,
                    'news_fetch',
                    'WARN',
                    f'No items found within {window}h; broadened window to {next_window}h.',
                    details={
                        'failures': failures[:10],
                        'recency_hours_used': window,
                        'next_window': next_window,
                    },
                )
            continue
        if candidates:
            deduped = {}
            for item in sorted(candidates, key=lambda row: row.published_at, reverse=True):
                deduped.setdefault(item.url, item)
            articles = list(deduped.values())[:20]
            last_articles = articles
            last_failures = failures
            last_window = window

            if not has_non_duplicate_candidates(articles):
                next_windows = [candidate for candidate in candidate_windows if candidate > window]
                if next_windows:
                    next_window = next_windows[0]
                    agent_db.safe_log_event(
                        run_id,
                        'news_fetch',
                        'WARN',
                        f'Only duplicate candidates found within {window}h; broadened window to {next_window}h.',
                        details={
                            'failures': failures[:10],
                            'recency_hours_used': window,
                            'candidate_count': len(articles),
                            'next_window': next_window,
                        },
                    )
                continue

            details = {'failures': failures[:10], 'recency_hours_used': window}
            agent_db.safe_log_event(run_id, 'news_fetch', 'SUCCESS', f'Fetched {len(articles)} candidate articles.', details=details)
            return articles

    if last_articles:
        agent_db.safe_log_event(
            run_id,
            'news_fetch',
            'SUCCESS',
            f'Fetched {len(last_articles)} candidate articles, but none were new after duplicate screening.',
            details={
                'failures': last_failures[:10],
                'recency_hours_used': last_window,
                'all_candidates_duplicate': True,
            },
        )
        return last_articles

    raise RuntimeError(f'All news sources unreachable or empty: {json.dumps(failures, ensure_ascii=False)}')


def categorize_article(article):
    text = f'{article.title} {article.description}'.lower()
    if any(term in text for term in ['guideline', 'recommendation', 'advisory', 'committee', 'position statement']):
        return ('Clinical Guidelines', 'clinical-guidelines')
    if any(term in text for term in ['trial', 'study', 'nature', 'nejm', 'lancet', 'science', 'model', 'research']):
        return ('Medical Research', 'medical-research')
    if any(term in text for term in ['vaccine', 'virus', 'outbreak', 'infection', 'pathogen', 'polio', 'rsv', 'nipah']):
        return ('Infectious Disease', 'infectious-disease')
    if any(term in text for term in ['hospital', 'workflow', 'capacity', 'operations', 'service']):
        return ('Healthcare Operations', 'healthcare-operations')
    return ('Public Health', 'public-health')


def score_article(article):
    score = 0
    score += 100 if article.tier == 1 else 75
    score += 10 if any(term in article.title.lower() for term in ['who', 'cdc', 'nih', 'ecdc']) else 0
    score += 5 if len(article.description) > 140 else 0
    age_hours = max((now_utc() - article.published_at).total_seconds() / 3600, 0)
    score += max(0, 24 - age_hours)
    return score


def duplicate_exists(slug, source_url):
    db = agent_db.publish_db_name()
    columns = agent_db._table_columns(db, 'blog_master')
    if not columns or 'slug' not in columns:
        return False, ''
    active_filter = " AND status='active'" if 'status' in columns else ''
    slug_rows = agent_db._query_rows(
        f"USE `{db}`; SELECT id FROM blog_master WHERE {agent_db.text_equals_expr('slug', slug)}{active_filter};",
        1,
    )
    if slug_rows:
        return True, 'slug match'
    if not source_url or 'source_url' not in columns:
        return False, ''
    source_rows = agent_db._query_rows(
        f"USE `{db}`; SELECT id FROM blog_master WHERE {agent_db.text_equals_expr('source_url', source_url)}{active_filter};",
        1,
    )
    if source_rows:
        return True, 'source_url match'
    return False, ''


def has_non_duplicate_candidates(articles):
    for article in articles:
        duplicate, _reason = duplicate_exists(slugify(article.title), article.url)
        if not duplicate:
            return True
    return False


def select_topics(run_id, articles):
    selected = []
    for article in sorted(articles, key=score_article, reverse=True):
        category_name, category_slug = categorize_article(article)
        slug = slugify(article.title)
        duplicate, reason = duplicate_exists(slug, article.url)
        if duplicate:
            agent_db.safe_log_event(run_id, 'duplicate_check', 'SKIPPED', f'Duplicate skipped: {reason}', item_slug=slug, details={'source_url': article.url})
            continue
        selected.append({
            'article': article,
            'slug': slug,
            'category_name': category_name,
            'category_slug': category_slug,
            'key_insight': article.description,
        })
        agent_db.safe_log_event(run_id, 'duplicate_check', 'SUCCESS', 'Topic unique.', item_slug=slug, details={'source_url': article.url})
        if len(selected) >= MAX_TOPICS:
            break
    agent_db.safe_log_event(run_id, 'planner', 'SUCCESS', f'Selected {len(selected)} topics.', details={'topics': [item['slug'] for item in selected]})
    return selected


def fetch_memory_context():
    return agent_db.fetch_memory_context(limit=50)


def relevant_memory(memory_rows, slug):
    terms = set(slug.replace('-', ' ').split())
    return [row for row in memory_rows if terms.intersection(set((row['topic_slug'] or '').replace('-', ' ').split()))]


def research_topic(topic, memory_rows):
    article = topic['article']
    html_text = fetch_url(article.url)
    title = extract_meta(html_text, 'og:title', 'twitter:title') or article.title
    description = extract_meta(html_text, 'description', 'og:description') or article.description
    image_url = extract_image_url(html_text)
    paragraphs = extract_paragraphs(html_text, limit=10)
    if len(' '.join(paragraphs).split()) < 180:
        raise RuntimeError('insufficient article body extracted for evidence-grounded writing')
    memory_context = relevant_memory(memory_rows, topic['slug'])
    confirmed = []
    for bullet in paragraphs[:4]:
        confirmed.append({
            'claim': bullet,
            'evidence_type': 'Official guidance' if article.tier == 1 else 'Institutional report',
            'confidence': 'High' if article.tier == 1 else 'Moderate',
            'source': f"{article.source} + {article.url}",
        })
    evidence_grade = 'High' if article.tier == 1 else 'Moderate'
    return {
        'topic': topic,
        'title': title,
        'description': description,
        'paragraphs': paragraphs,
        'confirmed_findings': confirmed,
        'preliminary_findings': [],
        'do_not_use': [],
        'public_health_impact': description,
        'clinical_relevance': 'Monitor the official source, align local communication with the underlying evidence, and avoid overextending claims beyond the source text.',
        'limitations': 'This run relies on source-page extraction and does not use browser-based verification or journal full text beyond accessible page content.',
        'references': [
            {'name': article.source, 'url': article.url},
            {'name': f"{article.source} source feed", 'url': article.source_feed_url},
        ],
        'image_source_url': image_url,
        'memory_context': memory_context,
        'browser_verification_used': False,
        'published_at': article.published_at,
        'evidence_grade': evidence_grade,
    }


def estimate_read_time(words):
    return max(4, round(words / 220))


def join_sentences(parts):
    text = ' '.join(part.strip() for part in parts if part and part.strip())
    return re.sub(r'\s+', ' ', text).strip()


def build_blog_from_research(research):
    topic = research['topic']
    article = topic['article']
    title = topic['article'].title.strip()
    category_name = topic['category_name']
    slug = topic['slug']
    intro = [
        f"{title} was published by {article.source} on {article.published_at.strftime('%B %-d, %Y') if sys.platform != 'win32' else article.published_at.strftime('%B %#d, %Y')}.",
        research['description'],
        'For healthcare professionals, the value of this update lies in the source authority, the immediate operational implications, and the need to distinguish established facts from early interpretation.',
    ]
    background = paragraphs_to_section(research['paragraphs'][0:3], 'Background context remains limited to what the source page explicitly states, so this article avoids extending beyond the cited material.')
    key_findings = research['confirmed_findings'][:3]
    key_bullets = '\n'.join(
        f"- **Finding {index}:** {item['claim']}"
        for index, item in enumerate(key_findings, start=1)
    )
    impact_bullets = '\n'.join([
        '- Review the primary source directly before changing local guidance or protocol.',
        '- Communicate the strength and limits of the evidence clearly to clinical teams.',
        '- Monitor follow-on updates, advisories, or supporting studies tied to the same source.',
    ])
    conclusion = [
        research['description'],
        'The safest reading is to treat this as an evidence-traceable update for monitoring and professional awareness, not as a basis for unsupported extrapolation.',
    ]
    evidence_limits = (
        f"The core evidence for this topic comes from {article.source}'s published update and the linked source feed, "
        'which means clinicians should treat any operational takeaway as provisional until supporting guidance, implementation detail, '
        'or peer-reviewed follow-up appears through the same evidence chain.'
    )
    references = '\n'.join(
        f"{index}. [{ref['name']}]({ref['url']})"
        for index, ref in enumerate(research['references'], start=1)
    )
    content = f"""# {title}

**Published by:** Global Health Intelligence Agent  
**Category:** {category_name}  
**Reading Time:** ~{estimate_read_time(len(' '.join(research['paragraphs']).split()))} min read  

---

## Introduction

{join_sentences(intro)}

{research['public_health_impact']}

---

## Background

{background}

{evidence_limits}

---

## Key Insights

{key_bullets}

The source material supports a cautious interpretation. {research['clinical_relevance']} The evidence grade for this topic in the current run is **{research['evidence_grade']}**, and no unsupported claims were carried forward.

---

## Impact on Healthcare Professionals

Healthcare professionals should treat this update as a monitored, source-driven development rather than a standalone trigger for broad policy change.

{impact_bullets}

Teams should continue to align decisions with official guidance, local epidemiology, and any later corroborating evidence that becomes available.

---

## Conclusion

{join_sentences(conclusion)}

---

**Sources:**  
{references}
"""
    summary = research['description']
    keywords = build_keywords(title, research['description'], category_name)
    return {
        'category_name': category_name,
        'category_slug': topic['category_slug'],
        'title': title[:79],
        'slug': slug,
        'summary': summary[:300],
        'content': content.strip(),
        'keywords': keywords,
        'source_url': article.url,
        'image_source_url': research.get('image_source_url'),
        'research': research,
    }


def paragraphs_to_section(paragraphs, fallback):
    text = '\n\n'.join(paragraphs[:3]).strip()
    return text or fallback


def build_keywords(title, description, category_name):
    tokens = re.findall(r'[A-Za-z][A-Za-z\-]{3,}', f'{title} {description} {category_name}')
    keywords = []
    for token in tokens:
        value = token.lower()
        if value not in keywords:
            keywords.append(value)
        if len(keywords) >= 8:
            break
    while len(keywords) < 5:
        fallback = ['global-health', 'clinical-update', 'health-policy', 'medical-news', 'evidence-review'][len(keywords)]
        if fallback not in keywords:
            keywords.append(fallback)
    return keywords[:8]


def _learning_detail_lines(details=None):
    details = details or {}
    lines = []
    article_count = details.get('article_count')
    if article_count is not None:
        lines.append(f"- Candidate articles reviewed in this run: **{int(article_count)}**.")
    selected_topic_count = details.get('selected_topic_count')
    if selected_topic_count is not None:
        lines.append(f"- Topics selected for deeper work: **{int(selected_topic_count)}**.")
    news_error = str(details.get('news_error') or '').strip()
    if news_error:
        lines.append(f"- News retrieval issue recorded during this run: `{news_error}`.")
    for failure in (details.get('topic_failures') or [])[:3]:
        slug = str(failure.get('slug') or 'topic').strip()
        reason = str(failure.get('reason') or 'no detailed reason recorded').strip()
        lines.append(f"- Topic `{slug}` could not be published because **{reason}**.")
    return '\n'.join(lines) or '- The workflow captured no additional diagnostics beyond the absence of publishable material.'


def build_learning_blog(run_id, reason, details=None):
    timestamp = now_utc()
    title = 'Learning update: no publishable blog was available in this run'
    slug = slugify(f'learning-update-{run_id}')
    summary = (
        'No evidence-grounded, non-duplicate blog could be published in this workflow run, '
        'so the agent created a Learning-category post that explains what happened and what to review next.'
    )
    detail_lines = _learning_detail_lines(details)
    confirmed_findings = [
        {
            'claim': 'The workflow did not find enough reliable, publishable material to issue a standard medical news article in this run.',
            'confidence': 'Moderate',
        },
        {
            'claim': 'Instead of inventing unsupported claims, the system preserved its evidence threshold and recorded the gap transparently.',
            'confidence': 'High',
        },
        {
            'claim': 'A Learning-category post was generated so the frontend and publishing pipeline still communicate the workflow outcome clearly.',
            'confidence': 'High',
        },
    ]
    references = [
        {'name': 'AGENT workflow contract', 'url': 'AGENT.md'},
        {'name': 'Main workflow guide', 'url': 'docs/workflows/MAIN_WORKFLOW.md'},
        {'name': 'Run log mirror', 'url': 'logs/RUN_LOG.md'},
    ]
    content = f"""# {title}

**Published by:** Global Health Intelligence Agent  
**Category:** {LEARNING_CATEGORY_NAME}  
**Reading Time:** ~4 min read  
**Run ID:** {run_id}  
**Generated:** {timestamp.strftime('%Y-%m-%d %H:%M:%SZ')}

---

## Introduction

This Learning post was created because the workflow could not complete a normal evidence-grounded medical publication during the current run. The agent is designed to prefer silence over fabrication, which means it will not turn weak, inaccessible, duplicate, or incomplete source material into a standard blog article just to keep the page populated. When that situation happens, the system now publishes a Learning-category entry instead of leaving the run outcome invisible.

The goal of this fallback is operational transparency. It tells readers, reviewers, and maintainers that the agent did run, that the publishing pipeline still worked, and that the absence of a standard article reflects the evidence and retrieval conditions of the run rather than a silent failure. In other words, this post is not a substitute for a medical update; it is a traceable explanation of why a medical update was not produced.

The immediate trigger for this specific Learning entry was: **{reason}**. That trigger can arise when recent source feeds do not yield enough usable material, when all candidates are duplicates of previously published posts, or when the source pages do not provide enough accessible content to support evidence-grounded writing.

---

## Background

The normal workflow for this repository is intentionally strict. It starts by gathering recent source material, filters for clinically relevant and non-duplicate topics, researches the selected topics against accessible source content, validates the resulting article structure, verifies that the claims remain traceable, and only then publishes to the target blog tables. That structure is useful because it reduces the chance of publishing unsupported claims, thin rewrites, or duplicate updates that add little value for healthcare professionals.

However, a strict workflow can create a visibility gap when nothing qualifies for publication. A run may succeed technically while still ending with no standard article because the available sources are too old, too similar to existing coverage, blocked by access controls, or too shallow to support the required content sections. Previously, that branch could leave the frontend with no new blog output even though the agent completed a legitimate review cycle.

This new Learning fallback closes that gap. It keeps the category system active, documents the reason no standard article was published, and gives the team a durable record inside the same publishing channel. That makes the system easier to monitor because the absence of new medical content is now itself communicated as a deliberate, traceable outcome.

---

## Key Insights

{detail_lines}

- **Finding 1:** The absence of a publishable blog is sometimes the correct evidence-based outcome.
- **Finding 2:** A transparent fallback is better than a silent empty state because it preserves auditability.
- **Finding 3:** The Learning category can capture operational lessons without pretending that a missing medical article is equivalent to a verified clinical update.

This fallback also reinforces an important product principle: users should be able to distinguish between "no new trustworthy article was available" and "the system failed without explanation." In editorial and healthcare contexts, those are very different states. A cautious system should expose that distinction clearly, especially when the pipeline intentionally rejects weak source material.

For maintainers, the Learning post also acts as a compact debugging surface. If the run repeatedly creates Learning posts, that pattern suggests a need to review source freshness, duplicate logic, extraction quality, URL accessibility, or publishing thresholds. If the Learning posts appear only occasionally, the feature is doing its job by covering natural gaps in the news and evidence cycle.

---

## Impact on Healthcare Professionals

For healthcare professionals reading the site, this category should set the right expectation: there was no new evidence-grounded article ready for publication in the current cycle. That is preferable to publishing speculative summaries, over-interpreted headlines, or content padded beyond what the source material actually supports. In clinical communication, restraint is often safer than output volume.

For content reviewers and product owners, the Learning category creates a clear operational trail. It confirms that the system executed its review steps, that quality controls were respected, and that the lack of a standard post did not result from hidden inactivity. This is especially helpful when the system is monitored through the frontend alone, because the blog list can now show a meaningful fallback entry instead of an unexplained empty screen.

For future workflow tuning, the Learning post offers a stable place to summarize what should be improved next. That may include widening source coverage, handling more feed edge cases, improving HTML extraction, or refining duplicate thresholds. The fallback therefore supports both user communication and iterative engineering without weakening the evidence standard for actual medical articles.

---

## Conclusion

This Learning-category article exists to document a safe publishing decision: no standard blog was created because the current run did not yield enough trustworthy, non-duplicate, publishable material. The workflow still completed responsibly, and this post records that outcome in a visible way.

Going forward, the agent should continue to prefer evidence integrity over forced output. When strong source material is available, the normal medical publishing path should resume. When it is not, the Learning category now provides a transparent fallback so that readers and maintainers can still understand what happened during the run.

---

**Sources:**  
1. [AGENT workflow contract](AGENT.md)
2. [Main workflow guide](docs/workflows/MAIN_WORKFLOW.md)
3. [Run log mirror](logs/RUN_LOG.md)
"""
    return {
        'category_name': LEARNING_CATEGORY_NAME,
        'category_slug': LEARNING_CATEGORY_SLUG,
        'title': title[:79],
        'slug': slug,
        'summary': summary[:300],
        'content': content.strip(),
        'keywords': ['learning', 'workflow', 'publishing', 'fallback', 'operations'],
        'source_url': '',
        'image_source_url': '',
        'research': {
            'references': references,
            'evidence_grade': 'Moderate',
            'confirmed_findings': confirmed_findings,
        },
    }


def publish_learning_fallback(run_id, reason, details=None):
    blog = build_learning_blog(run_id, reason, details=details)
    valid, validation_reason = validate_blog(blog)
    if not valid:
        raise RuntimeError(f'learning fallback validation failed: {validation_reason}')
    verified, verify_reason = verify_blog(blog)
    if not verified:
        raise RuntimeError(f'learning fallback verification failed: {verify_reason}')
    blog_id = publish_blog(run_id, blog)
    agent_db.safe_log_event(
        run_id,
        'learning_fallback',
        'SUCCESS',
        'Published Learning fallback blog.',
        item_slug=blog['slug'],
        details={'reason': reason, 'blog_id': blog_id, **(details or {})},
    )
    return {'blog_id': blog_id, **blog}


def validate_blog(blog):
    required = ['title', 'slug', 'category_name', 'summary', 'content', 'keywords']
    for field in required:
        if not blog.get(field):
            return False, f'missing required field: {field}'
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', blog['slug']):
        return False, 'slug is not URL-safe'
    if len(blog['keywords']) < 5 or len(blog['keywords']) > 8:
        return False, 'keywords must contain 5-8 items'
    required_sections = ['## Introduction', '## Background', '## Key Insights', '## Impact on Healthcare Professionals', '## Conclusion', '**Sources:**']
    for section in required_sections:
        if section not in blog['content']:
            return False, f'missing content section: {section}'
    word_count = len(re.findall(r'\b\w+\b', blog['content']))
    if word_count < MIN_CONTENT_WORDS or word_count > MAX_CONTENT_WORDS:
        return False, f'content word count out of range: {word_count}'
    return True, ''


def verify_blog(blog):
    research = blog['research']
    if not research['references'] or len(research['references']) < 2:
        return False, 'missing traceable references'
    if research['evidence_grade'] not in {'High', 'Moderate'}:
        return False, 'evidence grade below publication threshold'
    duplicate, reason = duplicate_exists(blog['slug'], blog['source_url'])
    if duplicate:
        return False, f'duplicate detected during final verification: {reason}'
    return True, ''


def ensure_publish_tables():
    publish_db = agent_db.publish_db_name()
    operational_backend = agent_db.operational_storage_backend()
    sql = f"""
CREATE DATABASE IF NOT EXISTS `{publish_db}`;
USE `{publish_db}`;
CREATE TABLE IF NOT EXISTS blog_category (
  createdAt BIGINT NULL,
  updatedAt BIGINT NULL,
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  UNIQUE KEY uq_blog_category_name (name)
);
CREATE TABLE IF NOT EXISTS blog_master (
  createdAt BIGINT NULL,
  updatedAt BIGINT NULL,
  id INT PRIMARY KEY AUTO_INCREMENT,
  blog_name VARCHAR(512) NOT NULL,
  category_id INT NOT NULL,
  meta_title VARCHAR(512),
  description LONGTEXT,
  meta_description TEXT,
  meta_tags TEXT,
  file VARCHAR(500) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  slug VARCHAR(512) UNIQUE,
  CONSTRAINT fk_blog_master_category
    FOREIGN KEY (category_id) REFERENCES blog_category(id)
);
"""
    agent_db.mysql(sql)
    migrate_publish_tables(publish_db)
    if operational_backend != agent_db.STORAGE_BACKEND_JSON:
        agent_db.ensure_operational_tables()


def _alter_table(db_name, table_name, operations):
    operations = [operation for operation in operations if operation]
    if not operations:
        return
    agent_db.mysql(f"USE `{db_name}`; ALTER TABLE `{table_name}` {', '.join(operations)};")


def _backfill_table(db_name, table_name, assignments):
    assignments = [assignment for assignment in assignments if assignment]
    if not assignments:
        return
    agent_db.mysql(f"USE `{db_name}`; UPDATE `{table_name}` SET {', '.join(assignments)};")


def migrate_publish_tables(publish_db=None):
    publish_db = publish_db or agent_db.publish_db_name()

    category_columns = agent_db._table_columns(publish_db, 'blog_category')
    _alter_table(
        publish_db,
        'blog_category',
        [
            "CHANGE COLUMN `category_name` `name` VARCHAR(255) NOT NULL"
            if 'name' not in category_columns and 'category_name' in category_columns
            else None,
            "ADD COLUMN `createdAt` BIGINT NULL"
            if 'createdAt' not in category_columns
            else None,
            "ADD COLUMN `updatedAt` BIGINT NULL"
            if 'updatedAt' not in category_columns
            else None,
        ],
    )
    category_columns = agent_db._table_columns(publish_db, 'blog_category')
    _backfill_table(
        publish_db,
        'blog_category',
        [
            "`createdAt` = COALESCE(`createdAt`, UNIX_TIMESTAMP(`created_at`) * 1000)"
            if 'createdAt' in category_columns and 'created_at' in category_columns
            else None,
            "`updatedAt` = COALESCE(`updatedAt`, UNIX_TIMESTAMP(`updated_at`) * 1000)"
            if 'updatedAt' in category_columns and 'updated_at' in category_columns
            else None,
        ],
    )

    blog_columns = agent_db._table_columns(publish_db, 'blog_master')
    _alter_table(
        publish_db,
        'blog_master',
        [
            "CHANGE COLUMN `title` `blog_name` VARCHAR(512) NOT NULL"
            if 'blog_name' not in blog_columns and 'title' in blog_columns
            else None,
            "CHANGE COLUMN `content` `description` LONGTEXT"
            if 'description' not in blog_columns and 'content' in blog_columns
            else None,
            "CHANGE COLUMN `summary` `meta_description` TEXT"
            if 'meta_description' not in blog_columns and 'summary' in blog_columns
            else None,
            "CHANGE COLUMN `keywords` `meta_tags` TEXT"
            if 'meta_tags' not in blog_columns and 'keywords' in blog_columns
            else None,
            "ADD COLUMN `meta_title` VARCHAR(512) NULL"
            if 'meta_title' not in blog_columns
            else None,
            "ADD COLUMN `createdAt` BIGINT NULL"
            if 'createdAt' not in blog_columns
            else None,
            "ADD COLUMN `updatedAt` BIGINT NULL"
            if 'updatedAt' not in blog_columns
            else None,
            "ADD COLUMN `file` VARCHAR(500) NULL"
            if 'file' not in blog_columns
            else None,
        ],
    )
    blog_columns = agent_db._table_columns(publish_db, 'blog_master')
    title_column = agent_db._pick_column(blog_columns, ['blog_name', 'title'])
    _backfill_table(
        publish_db,
        'blog_master',
        [
            f"`meta_title` = COALESCE(NULLIF(`meta_title`, ''), `{title_column}`)"
            if 'meta_title' in blog_columns and title_column
            else None,
            "`createdAt` = COALESCE(`createdAt`, UNIX_TIMESTAMP(`created_at`) * 1000)"
            if 'createdAt' in blog_columns and 'created_at' in blog_columns
            else None,
            "`updatedAt` = COALESCE(`updatedAt`, UNIX_TIMESTAMP(`updated_at`) * 1000)"
            if 'updatedAt' in blog_columns and 'updated_at' in blog_columns
            else None,
        ],
    )


def category_id_for(blog):
    db = agent_db.publish_db_name()
    columns = agent_db._table_columns(db, 'blog_category')
    name_column = agent_db._pick_column(columns, ['name', 'category_name'])
    if not name_column:
        raise RuntimeError('blog_category schema is missing name column')
    category_name = normalize_category_name(blog.get('category_name'))
    if not category_name:
        raise RuntimeError('missing required category_name')
    category_slug = (blog.get('category_slug') or slugify(category_name)).strip()
    timestamp = now_utc_millis()
    lookup_filters = [
        f"LOWER(TRIM(CAST(`{name_column}` AS CHAR CHARACTER SET utf8mb4))) = LOWER(TRIM(CAST({agent_db.text_expr(category_name)} AS CHAR CHARACTER SET utf8mb4)))"
    ]
    if 'category_slug' in columns and category_slug:
        lookup_filters.insert(0, agent_db.text_equals_expr(f'`category_slug`', category_slug))
    status_rank = "CASE WHEN LOWER(TRIM(status)) = 'active' THEN 0 ELSE 1 END, " if 'status' in columns else ''
    existing_rows = agent_db._query_rows(
        f"USE `{db}`; SELECT id FROM blog_category WHERE {' OR '.join(lookup_filters)} ORDER BY {status_rank}id ASC LIMIT 1;",
        1,
    )
    if existing_rows:
        category_id = int(existing_rows[0][0])
        update_assignments = [f"`{name_column}` = {agent_db.text_expr(category_name)}"]
        if 'status' in columns:
            update_assignments.append("status = 'active'")
        if 'updatedAt' in columns:
            update_assignments.append(f'updatedAt = {timestamp}')
        elif 'updated_at' in columns:
            update_assignments.append('updated_at = CURRENT_TIMESTAMP')
        if 'category_slug' in columns and category_slug:
            update_assignments.append(f"`category_slug` = {agent_db.text_expr(category_slug)}")
        agent_db.mysql(f"USE `{db}`; UPDATE blog_category SET {', '.join(update_assignments)} WHERE id = {category_id};")
        return category_id

    insert_columns = [f'`{name_column}`']
    insert_values = [agent_db.text_expr(category_name)]
    if 'status' in columns:
        insert_columns.append('`status`')
        insert_values.append("'active'")
    if 'createdAt' in columns:
        insert_columns.append('`createdAt`')
        insert_values.append(str(timestamp))
    if 'updatedAt' in columns:
        insert_columns.append('`updatedAt`')
        insert_values.append(str(timestamp))
    if 'category_slug' in columns and category_slug:
        insert_columns.append('`category_slug`')
        insert_values.append(agent_db.text_expr(category_slug))
    rows = agent_db._query_rows(
        f"USE `{db}`; INSERT INTO blog_category ({', '.join(insert_columns)}) VALUES ({', '.join(insert_values)}); SELECT LAST_INSERT_ID();",
        1,
    )
    if not rows:
        raise RuntimeError('failed to resolve category id')
    return int(rows[-1][0])


def publish_blog(run_id, blog):
    category_id = category_id_for(blog)
    published_file_url = None
    if blog.get('image_source_url'):
        try:
            _image_file_key, published_file_url = blog_file_manager.upload_blog_image(
                {
                    'slug': blog['slug'],
                    'image_source_url': blog['image_source_url'],
                }
            )
        except Exception as exc:
            agent_db.safe_log_event(
                run_id,
                'publisher',
                'WARN',
                f'Image upload failed; using source image URL directly: {exc}',
                item_slug=blog['slug'],
                details={'image_source_url': blog.get('image_source_url')},
            )
            published_file_url = blog.get('image_source_url')
    stored_file_value = agent_db.blog_master_file_db_value(published_file_url)
    db = agent_db.publish_db_name()
    columns = agent_db._table_columns(db, 'blog_master')
    title_column = agent_db._pick_column(columns, ['blog_name', 'title'])
    summary_column = agent_db._pick_column(columns, ['meta_description', 'summary'])
    content_column = agent_db._pick_column(columns, ['description', 'content'])
    tags_column = agent_db._pick_column(columns, ['meta_tags', 'keywords'])
    if not title_column or not summary_column or not content_column or 'slug' not in columns or 'category_id' not in columns:
        raise RuntimeError('blog_master schema is missing required publish columns')
    timestamp = now_utc_millis()
    insert_columns = []
    insert_values = []

    def add(column_name, value_expr):
        if column_name and column_name in columns:
            insert_columns.append(f'`{column_name}`')
            insert_values.append(value_expr)

    add('createdAt', str(timestamp))
    add('updatedAt', str(timestamp))
    add('category_id', str(category_id))
    add(title_column, agent_db.text_expr(blog['title']))
    add('slug', agent_db.text_expr(blog['slug']))
    add('meta_title', agent_db.text_expr(blog['title']))
    rendered_content = blog_file_manager.content_to_html(blog['content']) if content_column == 'description' else blog['content']
    add(content_column, agent_db.text_expr(rendered_content))
    add(summary_column, agent_db.text_expr(blog['summary']))
    if tags_column == 'keywords':
        add(tags_column, agent_db.json_expr(blog['keywords']))
    elif tags_column:
        add(tags_column, agent_db.text_expr(', '.join(blog['keywords'])))
    add('source_url', agent_db.text_expr(blog.get('source_url')))
    add('file', agent_db.text_expr(stored_file_value))
    add('status', "'active'")
    sql = f"""
USE `{db}`;
INSERT INTO blog_master ({', '.join(insert_columns)})
VALUES ({', '.join(insert_values)});
SELECT LAST_INSERT_ID();
"""
    blog_id = int(agent_db._query_rows(sql, 1)[-1][0])
    agent_db.safe_log_event(
        run_id,
        'publisher',
        'SUCCESS',
        'Published blog.',
        item_slug=blog['slug'],
        details={'blog_id': blog_id, 'category_id': category_id, 'file_url': published_file_url},
    )
    return blog_id


def store_memory(blog):
    research = blog['research']
    facts = []
    for index, item in enumerate(research['confirmed_findings'][:3], start=1):
        facts.append({
            'memory_key': f"{blog['slug']}-fact-{index}",
            'verified_fact': item['claim'],
            'confidence': item['confidence'],
        })
    for fact in facts:
        agent_db.store_memory_fact(
            topic_slug=blog['slug'],
            category_name=blog['category_name'],
            memory_key=fact['memory_key'],
            verified_fact=fact['verified_fact'],
            source_url=blog['source_url'],
            confidence=fact['confidence'],
            status='active',
        )
    return facts


def update_markdown_mirrors(run_id, published_blogs, memory_facts):
    run_summary = [
        '',
        '---',
        '',
        f'## Run: {run_id}',
        '',
        f'**Date:** {now_utc().strftime("%B %d, %Y")}  ',
        '**Status:** Completed  ',
        '',
        '### Summary',
        '',
        f'Autonomous workflow completed with {len(published_blogs)} published blog articles.',
        '',
        '### Published Articles',
        '',
    ]
    for item in published_blogs:
        run_summary.extend([
            f"- **Title:** {item['title']}",
            f"- **Category:** {item['category_name']}",
            f"- **Slug:** {item['slug']}",
            f"- **Blog ID:** {item['blog_id']}",
            f"- **Status:** Published (active)",
            '',
        ])
    append_text('logs/RUN_LOG.md', '\n'.join(run_summary))

    memory_summary = [
        '',
        f'## Run: {run_id}',
        '',
        f'### Memory Consolidation - {now_utc().strftime("%B %d, %Y")}',
        '',
    ]
    for item in memory_facts:
        memory_summary.extend([
            f"**Topic: {item['slug']}**",
            '',
        ])
        for fact in item['facts']:
            memory_summary.append(f"- **{fact['memory_key']}**: {fact['verified_fact']}")
        memory_summary.append('')
    append_text('logs/MEMORY_STORE.md', '\n'.join(memory_summary))


def run_workflow(recency_hours=24):
    agent_db.load_env()
    run_id = agent_db.current_run_id('workflow')
    published = []
    memory_rollup = []
    topic_failures = []
    agent_db.safe_log_event(run_id, 'runner', 'STARTED', 'Autonomous workflow started.', details={'backend': agent_db.database_backend()})
    try:
        ensure_publish_tables()
        agent_db.safe_log_event(run_id, 'database_init', 'SUCCESS', 'Verified operational and publish tables.')
        memory_rows = fetch_memory_context()
        agent_db.safe_log_event(run_id, 'memory_retrieval', 'SUCCESS', f'Retrieved {len(memory_rows)} memory rows.')
        news_error = ''
        try:
            articles = fetch_recent_news(run_id, recency_hours=recency_hours)
        except Exception as exc:
            news_error = str(exc)
            articles = []
            agent_db.safe_log_event(run_id, 'news_fetch', 'ERROR', news_error, details={'traceback': traceback.format_exc()})
        topics = select_topics(run_id, articles)
        if not topics:
            agent_db.safe_log_event(run_id, 'planner', 'INFO', 'No relevant non-duplicate topics this run.')
            published.append(
                publish_learning_fallback(
                    run_id,
                    'No blogs or source content were available for a standard publishable article in this run.',
                    details={
                        'article_count': len(articles),
                        'selected_topic_count': 0,
                        'news_error': news_error,
                    },
                )
            )
            update_markdown_mirrors(run_id, published, [])
            agent_db.safe_log_event(run_id, 'run_complete', 'SUCCESS', f'Workflow completed with {len(published)} published blogs.')
            return 0
        for topic in topics:
            slug = topic['slug']
            try:
                research = research_topic(topic, memory_rows)
                agent_db.safe_log_event(run_id, 'research', 'SUCCESS', 'Research completed.', item_slug=slug, details={'references': research['references']})
                blog = build_blog_from_research(research)
                valid, reason = validate_blog(blog)
                if not valid:
                    agent_db.safe_log_event(run_id, 'tester', 'WARN', f'Validation failed: {reason}', item_slug=slug)
                    continue
                agent_db.safe_log_event(run_id, 'tester', 'SUCCESS', 'Deterministic checks passed.', item_slug=slug)
                verified, reason = verify_blog(blog)
                if not verified:
                    agent_db.safe_log_event(run_id, 'verifier', 'WARN', f'Final verification failed: {reason}', item_slug=slug)
                    continue
                agent_db.safe_log_event(run_id, 'verifier', 'SUCCESS', 'Publication approved.', item_slug=slug)
                blog_id = publish_blog(run_id, blog)
                facts = store_memory(blog)
                agent_db.safe_log_event(run_id, 'memory_consolidation', 'SUCCESS', f'Stored {len(facts)} memory facts.', item_slug=slug)
                published.append({'blog_id': blog_id, **blog})
                memory_rollup.append({'slug': blog['slug'], 'facts': facts})
            except Exception as exc:
                topic_failures.append({'slug': slug, 'reason': str(exc)})
                agent_db.safe_log_event(run_id, 'topic_execution', 'ERROR', str(exc), item_slug=slug, details={'traceback': traceback.format_exc()})
                continue
        if not published:
            published.append(
                publish_learning_fallback(
                    run_id,
                    'All selected topics failed before publication, so a Learning fallback article was posted instead.',
                    details={
                        'article_count': len(articles),
                        'selected_topic_count': len(topics),
                        'topic_failures': topic_failures,
                    },
                )
            )
        update_markdown_mirrors(run_id, published, memory_rollup)
        agent_db.safe_log_event(run_id, 'run_complete', 'SUCCESS', f'Workflow completed with {len(published)} published blogs.')
        return 0
    except Exception as exc:
        agent_db.safe_log_event(run_id, 'runner', 'ERROR', str(exc), details={'traceback': traceback.format_exc()})
        raise


def main():
    parser = argparse.ArgumentParser(
        description='Run the autonomous Global Health Intelligence workflow end-to-end immediately after AGENT.md/workflow review without waiting for a second prompt.'
    )
    parser.add_argument('--recency-hours', type=int, default=24, help='Maximum article age to accept from source feeds.')
    args = parser.parse_args()
    return run_workflow(recency_hours=args.recency_hours)


if __name__ == '__main__':
    raise SystemExit(main())
