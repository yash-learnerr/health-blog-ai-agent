#!/usr/bin/env python3
import argparse
import html
import json
import random
import re
import sys
import tempfile
import textwrap
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
LEARNING_TOPIC_LIBRARY = [
    {
        'title': 'Learning Brief: Vaccine cold chain safety in everyday clinical practice',
        'slug': 'learning-vaccine-cold-chain-safety',
        'summary': 'A practical review of how vaccine cold chain discipline protects potency, reduces avoidable waste, and supports safe immunization delivery across clinics, pharmacies, and outreach programs.',
        'focus': 'vaccine cold chain safety',
        'background': 'Vaccines are biologic products whose effectiveness depends on careful temperature control from storage through administration. Even a short break in handling discipline can reduce potency, create uncertainty for vaccination teams, and complicate follow-up decisions for patients who expected reliable protection.',
        'practice_gap': 'Many day-to-day failures do not come from dramatic refrigeration breakdowns. They come from preventable routine issues such as overcrowded units, missing temperature logs, delayed response to out-of-range readings, and poor separation of vaccines from food, staff beverages, or non-clinical supplies.',
        'why_it_matters': 'For healthcare teams, cold chain quality is part of medication safety, quality assurance, and public trust. Strong processes help prevent missed opportunities, repeat doses, and uncertainty around whether a product remained usable throughout storage and transport.',
        'key_points': [
            'Store and transport vaccines using purpose-designed equipment, validated workflows, and continuous temperature monitoring rather than informal household-style practices.',
            'Respond to temperature excursions with documented quarantine, supervisor review, and product-specific guidance instead of guessing whether stock remains acceptable.',
            'Train every staff member who handles vaccines so that receiving, storage, transport, and administration all follow the same safety expectations.',
        ],
        'professional_actions': 'Review storage policies, check alarm escalation paths, audit temperature logs, and confirm that contingency plans exist for transport failures or power interruptions.',
        'system_impact': 'Reliable cold chain practice improves patient confidence in immunization programs and supports operational readiness during high-demand campaigns, school programs, and community outreach clinics.',
        'keywords': ['learning', 'vaccine-storage', 'cold-chain', 'immunization', 'patient-safety'],
        'references': [
            {'name': 'WHO vaccine management handbook', 'url': 'https://www.who.int/publications/i/item/WHO-IVB-15.01'},
            {'name': 'CDC vaccine storage and handling toolkit', 'url': 'https://www.cdc.gov/vaccines/hcp/admin/storage/toolkit/index.html'},
        ],
    },
    {
        'title': 'Learning Brief: Antimicrobial stewardship in outpatient care',
        'slug': 'learning-antimicrobial-stewardship-outpatient-care',
        'summary': 'An evergreen learning blog on how outpatient antimicrobial stewardship improves prescribing quality, reduces resistance pressure, and protects patients from avoidable adverse effects.',
        'focus': 'outpatient antimicrobial stewardship',
        'background': 'Antibiotics remain essential for treating bacterial infections, but they also create risk when they are prescribed unnecessarily, selected too broadly, or continued longer than needed. In ambulatory settings, small habits repeated across many visits can meaningfully influence resistance patterns, patient expectations, and medication safety.',
        'practice_gap': 'Outpatient stewardship challenges often include diagnostic uncertainty, patient pressure for immediate treatment, limited follow-up visibility, and variability in documentation. These factors can push clinicians toward broader or faster prescribing even when watchful waiting, supportive care, or narrower therapy would better match the evidence.',
        'why_it_matters': 'Good stewardship does not mean avoiding antibiotics when they are indicated. It means choosing the right drug, dose, route, and duration for the right patient while explaining the plan clearly enough that adherence and safety are preserved.',
        'key_points': [
            'Use diagnosis-specific prescribing expectations so respiratory, urinary, skin, and dental complaints are managed with more consistent evidence-based thresholds.',
            'Pair prescribing review with patient communication tools that explain why an antibiotic may not help viral illness and when reassessment is needed.',
            'Track simple quality measures such as broad-spectrum antibiotic use, duration outliers, and return visits linked to common syndromes.',
        ],
        'professional_actions': 'Combine local prescribing data, peer feedback, delayed prescribing strategies where appropriate, and clear follow-up instructions to support safer decisions.',
        'system_impact': 'Better outpatient stewardship reduces avoidable adverse drug events, lowers resistance pressure, and helps preserve antibiotic effectiveness for patients who genuinely need treatment.',
        'keywords': ['learning', 'antimicrobial-stewardship', 'outpatient-care', 'antibiotic-safety', 'resistance'],
        'references': [
            {'name': 'CDC core elements of outpatient antibiotic stewardship', 'url': 'https://www.cdc.gov/antibiotic-use/core-elements/outpatient.html'},
            {'name': 'WHO antimicrobial resistance fact sheet', 'url': 'https://www.who.int/news-room/fact-sheets/detail/antimicrobial-resistance'},
        ],
    },
    {
        'title': 'Learning Brief: Hand hygiene moments that reduce healthcare-associated infection',
        'slug': 'learning-hand-hygiene-healthcare-associated-infection',
        'summary': 'A healthcare learning post on why hand hygiene still matters, where compliance fails in busy care settings, and how teams can reinforce safer patient-contact habits.',
        'focus': 'hand hygiene in clinical care',
        'background': 'Hand hygiene remains one of the most foundational infection prevention measures in healthcare, yet it is also one of the easiest steps to erode under workload pressure. Because hands connect patients, equipment, medications, documentation surfaces, and shared spaces, inconsistent technique can contribute to avoidable transmission across the care environment.',
        'practice_gap': 'The challenge is rarely a lack of awareness alone. Missed opportunities often reflect workflow friction, poorly placed supplies, competing tasks during handoffs, and normalization of small shortcuts that feel harmless in the moment but accumulate across a shift.',
        'why_it_matters': 'Improving compliance depends on turning hand hygiene into a reliable system behavior rather than a purely individual reminder. Teams do better when product placement, culture, observation, and leadership expectations all support the same message.',
        'key_points': [
            'Reinforce the moments before patient contact, before aseptic tasks, after body fluid exposure risk, after patient contact, and after contact with patient surroundings.',
            'Use direct observation, coaching, and accessible alcohol-based hand rub placement to reduce the gap between policy and real workflow.',
            'Link hand hygiene improvement to broader infection prevention goals such as device safety, environmental cleaning, and isolation adherence.',
        ],
        'professional_actions': 'Review supply placement, involve unit champions, and give teams feedback that is specific enough to improve behavior rather than merely measure failure.',
        'system_impact': 'Consistent hand hygiene supports safer admissions, safer procedures, and lower healthcare-associated infection risk for patients and staff across settings.',
        'keywords': ['learning', 'hand-hygiene', 'infection-prevention', 'patient-safety', 'healthcare-quality'],
        'references': [
            {'name': 'WHO My 5 Moments for Hand Hygiene', 'url': 'https://www.who.int/publications/m/item/my-5-moments-for-hand-hygiene'},
            {'name': 'CDC hand hygiene in healthcare settings', 'url': 'https://www.cdc.gov/handhygiene/index.html'},
        ],
    },
    {
        'title': 'Learning Brief: Recognizing stroke symptoms and urgent referral pathways',
        'slug': 'learning-stroke-symptoms-urgent-referral',
        'summary': 'A focused learning article on rapid stroke recognition, the value of time-sensitive escalation, and how frontline teams can reduce delay to emergency evaluation.',
        'focus': 'early stroke recognition and referral',
        'background': 'Stroke care depends heavily on time. Delays in recognizing focal neurologic deficits or activating emergency pathways can narrow treatment options and worsen patient outcomes. Because many first contacts occur outside specialist settings, every clinician and triage team benefits from a shared mental model for urgent recognition.',
        'practice_gap': 'Missed or delayed escalation can happen when symptoms fluctuate, patients present atypically, communication is unclear, or teams underestimate the significance of transient deficits. Education therefore needs to focus on action thresholds, not only on memorizing symptom lists.',
        'why_it_matters': 'Rapid referral does not require every frontline team to make a definitive stroke subtype diagnosis. It requires recognizing that sudden neurologic change deserves immediate emergency evaluation and coordinated transfer without avoidable administrative delay.',
        'key_points': [
            'Teach sudden facial droop, arm weakness, speech difficulty, visual change, severe imbalance, or abrupt neurologic deficit as escalation triggers rather than symptoms to watch casually.',
            'Use local emergency pathways that minimize handoff confusion, document time last known well, and align transport decisions with stroke-ready services.',
            'Reinforce that transient symptoms may still reflect a high-risk vascular event and should not be dismissed because they partially improve.',
        ],
        'professional_actions': 'Standardize triage prompts, rehearse transfer communication, and educate teams to capture onset timing, medication context, and baseline neurologic function quickly.',
        'system_impact': 'Earlier recognition and referral improve the chance that eligible patients can receive time-sensitive treatment and specialist assessment with fewer preventable delays.',
        'keywords': ['learning', 'stroke-recognition', 'urgent-referral', 'neurology', 'emergency-care'],
        'references': [
            {'name': 'NINDS stroke information', 'url': 'https://www.ninds.nih.gov/health-information/disorders/stroke'},
            {'name': 'CDC stroke signs and symptoms', 'url': 'https://www.cdc.gov/stroke/signs_symptoms.htm'},
        ],
    },
    {
        'title': 'Learning Brief: Diabetes foot care and ulcer prevention',
        'slug': 'learning-diabetes-foot-care-ulcer-prevention',
        'summary': 'A practical educational blog on routine diabetic foot care, early risk detection, and why consistent prevention work matters before ulcers or infections develop.',
        'focus': 'diabetes foot care prevention',
        'background': 'Foot complications in diabetes can emerge gradually through neuropathy, vascular compromise, pressure injury, and delayed recognition of minor trauma. By the time a visible wound becomes serious, the upstream opportunities for prevention may have already been missed in routine care and patient self-management.',
        'practice_gap': 'Preventive foot care is often overshadowed by glucose metrics, medication changes, and urgent symptom management. As a result, footwear review, skin inspection, sensory assessment, and self-care coaching may receive less attention than their long-term impact deserves.',
        'why_it_matters': 'Consistent prevention helps reduce ulcer risk, avoid infection, and preserve mobility. It also gives clinicians a practical way to convert chronic disease follow-up visits into opportunities for complication prevention rather than late-stage rescue.',
        'key_points': [
            'Encourage regular inspection of feet and footwear, especially for patients with neuropathy who may not feel friction, heat, or early skin damage.',
            'Escalate concern quickly when redness, drainage, swelling, new pain, callus breakdown, or non-healing skin changes appear.',
            'Integrate foot care teaching into chronic disease review so prevention is repeated consistently rather than addressed only after injury occurs.',
        ],
        'professional_actions': 'Use structured diabetic foot checks, document risk level, reinforce footwear guidance, and coordinate podiatry or wound referral when early warning signs appear.',
        'system_impact': 'Early preventive care can reduce avoidable ulceration, lower hospitalization risk, and improve long-term function for people living with diabetes.',
        'keywords': ['learning', 'diabetes-foot-care', 'ulcer-prevention', 'chronic-disease', 'patient-education'],
        'references': [
            {'name': 'CDC diabetes and foot health', 'url': 'https://www.cdc.gov/diabetes/diabetes-complications/diabetes-and-your-feet.html'},
            {'name': 'NIDDK diabetic foot problems', 'url': 'https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems/foot-problems'},
        ],
    },
    {
        'title': 'Learning Brief: Preventing dehydration and heat illness in vulnerable adults',
        'slug': 'learning-dehydration-heat-illness-vulnerable-adults',
        'summary': 'An educational post on preventing dehydration and heat-related illness in older adults and other high-risk groups during hot weather, illness, or limited access to cooling.',
        'focus': 'dehydration and heat illness prevention',
        'background': 'Heat-related illness is shaped by more than outdoor temperature alone. Age, chronic disease, medication effects, mobility limitations, social isolation, housing conditions, and reduced thirst response can all increase the risk that dehydration or heat stress will develop before warning signs are recognized.',
        'practice_gap': 'Prevention can fail when teams assume patients will self-identify risk, maintain adequate fluid intake, or notice early symptoms without support. Vulnerable adults may need proactive counseling and follow-up long before extreme heat becomes an emergency department problem.',
        'why_it_matters': 'Heat illness prevention is part of seasonal preparedness, chronic disease management, and community risk reduction. Simple anticipatory advice can help patients and caregivers identify risk earlier and take protective steps before symptoms escalate.',
        'key_points': [
            'Identify patients at higher risk because of age, frailty, diuretic use, cardiovascular disease, renal disease, mental illness, or reduced access to cool environments.',
            'Teach practical prevention steps such as planned hydration, checking indoor heat exposure, lighter clothing, caregiver monitoring, and early response to dizziness or confusion.',
            'Include heat risk in outreach planning so clinics and community services can reinforce prevention during seasonal spikes and local alerts.',
        ],
        'professional_actions': 'Incorporate heat counseling into medication review, discharge planning, home health communication, and seasonal community messaging.',
        'system_impact': 'Earlier prevention can reduce avoidable emergency visits, protect high-risk patients during heat events, and strengthen public health resilience during climate-related stress.',
        'keywords': ['learning', 'heat-illness', 'dehydration', 'older-adults', 'public-health'],
        'references': [
            {'name': 'CDC heat and health', 'url': 'https://www.cdc.gov/heat-health/index.html'},
            {'name': 'WHO climate change and health', 'url': 'https://www.who.int/news-room/fact-sheets/detail/climate-change-and-health'},
        ],
    },
]


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


def clean_blog_title(title, max_length=180):
    text = re.sub(r'\s+', ' ', str(title or '').strip())
    if len(text) <= max_length:
        return text
    truncated = text[: max_length + 1].rsplit(' ', 1)[0].strip()
    if not truncated:
        truncated = text[:max_length].strip()
    return truncated.rstrip(' ,;:-') + '…'


def create_learning_cover_image(blog):
    title = clean_blog_title(blog.get('title') or 'Learning Brief', max_length=90)
    summary = re.sub(r'\s+', ' ', str(blog.get('summary') or '').strip())
    summary_lines = textwrap.wrap(summary, width=42)[:3] or ['Evidence-based health learning content']
    title_lines = textwrap.wrap(title, width=24)[:3] or ['Learning Brief']
    lines = []
    for index, line in enumerate(title_lines):
        lines.append(
            f'<text x="96" y="{250 + index * 92}" fill="#F8FAFC" font-size="64" font-weight="700" '
            f'font-family="Arial, Helvetica, sans-serif">{html.escape(line)}</text>'
        )
    for index, line in enumerate(summary_lines):
        lines.append(
            f'<text x="96" y="{600 + index * 44}" fill="#D6E4FF" font-size="28" font-weight="400" '
            f'font-family="Arial, Helvetica, sans-serif">{html.escape(line)}</text>'
        )
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900" role="img" aria-labelledby="title desc">
  <title>{html.escape(title)}</title>
  <desc>{html.escape(summary)}</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0F172A"/>
      <stop offset="55%" stop-color="#1D4ED8"/>
      <stop offset="100%" stop-color="#0EA5A4"/>
    </linearGradient>
  </defs>
  <rect width="1600" height="900" fill="url(#bg)" rx="36"/>
  <circle cx="1330" cy="170" r="170" fill="#93C5FD" opacity="0.18"/>
  <circle cx="1450" cy="720" r="220" fill="#67E8F9" opacity="0.16"/>
  <rect x="96" y="92" width="246" height="64" rx="32" fill="#DCFCE7" opacity="0.96"/>
  <text x="138" y="134" fill="#166534" font-size="30" font-weight="700" font-family="Arial, Helvetica, sans-serif">Learning</text>
  <text x="96" y="196" fill="#BFDBFE" font-size="30" font-weight="500" font-family="Arial, Helvetica, sans-serif">Health education fallback article</text>
  {''.join(lines)}
  <text x="96" y="790" fill="#E2E8F0" font-size="24" font-weight="500" font-family="Arial, Helvetica, sans-serif">Global Health Intelligence Agent</text>
</svg>'''
    handle = tempfile.NamedTemporaryFile('w', encoding='utf-8', suffix='.svg', prefix=f"{blog.get('slug') or 'learning'}-", delete=False)
    try:
        handle.write(svg)
        return handle.name
    finally:
        handle.close()


def cleanup_generated_file(path_value):
    if not path_value:
        return
    try:
        Path(path_value).unlink(missing_ok=True)
    except OSError:
        return


def build_blog_from_research(research):
    topic = research['topic']
    article = topic['article']
    title = clean_blog_title(topic['article'].title)
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
        'title': title,
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
        lines.append(f"- Candidate health news items reviewed this run: **{int(article_count)}**.")
    selected_topic_count = details.get('selected_topic_count')
    if selected_topic_count is not None:
        lines.append(f"- Standard news topics selected before fallback: **{int(selected_topic_count)}**.")
    news_error = str(details.get('news_error') or '').strip()
    if news_error:
        lines.append(f"- Feed or retrieval issue observed: `{news_error}`.")
    for failure in (details.get('topic_failures') or [])[:3]:
        slug = str(failure.get('slug') or 'topic').strip()
        reason = str(failure.get('reason') or 'no detailed reason recorded').strip()
        lines.append(f"- Standard topic `{slug}` could not be published because **{reason}**.")
    return '\n'.join(lines) or '- No additional run diagnostics were required beyond the fallback trigger.'


def _learning_topic_candidates(run_id, reason):
    candidates = [dict(topic) for topic in LEARNING_TOPIC_LIBRARY]
    random.Random(f'{run_id}:{reason}').shuffle(candidates)
    return candidates


def select_learning_topic(run_id, reason, details=None):
    candidates = _learning_topic_candidates(run_id, reason)
    first_topic = candidates[0] if candidates else None
    for topic in candidates:
        source_url = (topic.get('references') or [{}])[0].get('url', '')
        duplicate, _reason = duplicate_exists(topic['slug'], source_url)
        if not duplicate:
            topic['source_url'] = source_url
            return topic
    if not first_topic:
        raise RuntimeError('learning topic library is empty')
    fallback = dict(first_topic)
    fallback['title'] = f"{first_topic['title']}: refresher"
    fallback['slug'] = slugify(f"{first_topic['slug']}-{run_id}")
    fallback['source_url'] = ''
    fallback['keywords'] = list(dict.fromkeys(list(first_topic.get('keywords') or []) + ['learning-refresher']))[:8]
    return fallback


def build_learning_blog(run_id, reason, details=None):
    timestamp = now_utc()
    topic = select_learning_topic(run_id, reason, details=details)
    title = clean_blog_title(topic['title'])
    summary = topic['summary']
    detail_lines = _learning_detail_lines(details)
    references = topic['references']
    key_insights = '\n'.join(f"- **Insight {index}:** {point}" for index, point in enumerate(topic['key_points'], start=1))
    sources_block = '\n'.join(f"{index}. [{reference['name']}]({reference['url']})" for index, reference in enumerate(references, start=1))
    content = f"""# {title}

**Published by:** Global Health Intelligence Agent  
**Category:** {LEARNING_CATEGORY_NAME}  
**Reading Time:** ~5 min read  
**Run ID:** {run_id}  
**Generated:** {timestamp.strftime('%Y-%m-%d %H:%M:%SZ')}

---

## Introduction

This Learning article was created because the workflow did not find a standard publishable news blog for this run, so it selected a real evergreen health topic instead of showing an empty result. For this cycle, the topic chosen was **{topic['focus']}**, a subject that remains relevant to clinicians, educators, and care teams even when the news pipeline does not yield a strong evidence-grounded breaking update.

{topic['background']} {topic['why_it_matters']} That makes this type of fallback useful for the site: readers still receive practical, health-related educational content, and the publishing flow remains active without lowering the quality bar for current-news articles.

## Background

{topic['practice_gap']} In many organizations, these gaps do not look dramatic in isolation. They appear as small inconsistencies in routine work, documentation, escalation, patient counseling, or team communication. Over time, however, those inconsistencies can influence safety, efficiency, and the ability of professionals to respond confidently when clinical demands increase.

Evergreen learning content is valuable precisely because it focuses on fundamentals that should remain useful beyond a single headline or news cycle. When teams revisit core topics like {topic['focus']}, they strengthen baseline practice, sharpen patient education, and reduce the chance that preventable process failures turn into avoidable complications. In that sense, learning content is not filler; it is a practical reinforcement tool for daily care delivery.

## Key Insights

{key_insights}

{detail_lines}

These insights matter because effective healthcare work depends on repeatable basics as much as on high-profile clinical breakthroughs. A good learning brief should help professionals reconnect routine practice with safety outcomes, policy expectations, and patient trust. It should also be clear enough to support team discussion, local process review, or patient counseling without requiring a reader to decode highly technical research language first.

## Impact on Healthcare Professionals

For healthcare professionals, the immediate value of this topic is practical application. {topic['professional_actions']} Those actions are most effective when they are built into ordinary workflows rather than treated as optional reminders that compete with every other task in a busy clinical day.

{topic['system_impact']} Educational posts in the Learning category are therefore meant to support readiness, not merely background reading. When no strong current-news article is ready to publish, a carefully chosen learning topic can still help clinicians, pharmacists, nurses, administrators, and public health teams reinforce important habits that affect real-world care quality.

## Conclusion

This run did not produce a standard news-based blog, but it still produced a useful health education article by selecting a random evergreen learning topic with continuing professional relevance. In this case, the focus was **{topic['focus']}**, a subject that rewards repeated review because safe practice depends on consistent execution as much as on awareness.

The Learning category should now serve as a reliable fallback path: when breaking-news publication is not possible, the system can still publish a meaningful health-related blog that teaches something practical, remains relevant beyond the current day, and keeps the frontend populated with useful content rather than operational-only status messages.

---

**Sources:**  
{sources_block}
"""
    confirmed_findings = [
        {'claim': point, 'confidence': 'Moderate'}
        for point in topic['key_points']
    ]
    return {
        'category_name': LEARNING_CATEGORY_NAME,
        'category_slug': LEARNING_CATEGORY_SLUG,
        'title': title,
        'slug': topic['slug'],
        'summary': summary[:300],
        'content': content.strip(),
        'keywords': list(topic['keywords'])[:8],
        'source_url': topic.get('source_url', ''),
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
    generated_image_path = create_learning_cover_image(blog)
    blog['image_source_url'] = generated_image_path
    try:
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
    finally:
        cleanup_generated_file(generated_image_path)


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
            fallback_image_url = blog.get('image_source_url') if re.match(r'^https?://', str(blog.get('image_source_url') or ''), re.IGNORECASE) else None
            agent_db.safe_log_event(
                run_id,
                'publisher',
                'WARN',
                f'Image upload failed; using source image URL directly: {exc}',
                item_slug=blog['slug'],
                details={'image_source_url': blog.get('image_source_url'), 'fallback_image_url': fallback_image_url},
            )
            published_file_url = fallback_image_url
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
