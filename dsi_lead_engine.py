#!/usr/bin/env python3
"""
DSI Global Remote Lead Engine
Free stack: Python + GitHub Actions + Google Sheets + optional Supabase.

Goal:
Find engineering companies with current global remote hiring signals.
Only keep jobs that are useful for DSI staff augmentation from Bangladesh.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse, urljoin

import feedparser
import requests
from dateutil import parser as dateparser

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:  # pragma: no cover
    gspread = None
    Credentials = None

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(ROOT_DIR, "config")
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = [
    "Date Added",
    "Company Name",
    "Company Website",
    "Job Title",
    "Job URL",
    "Remote Type",
    "Location Tag",
    "Tech Tags",
    "Date Posted",
    "Source",
    "HQ Region",
    "Lead Status",
    "Priority",
    "LinkedIn URL",
    "Contact Name",
    "Contact Email",
    "Eligibility",
    "Eligibility Confidence",
    "Eligibility Evidence",
    "Notes",
]


REVIEW_HEADERS = HEADERS + [
    "Review Action",
    "Why Not Auto Accepted",
]

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (compatible; DSI-Global-Remote-Lead-Engine/1.2; +https://www.dsinnovators.com/)"
    }
)

REQUEST_TIMEOUT = 25
MAX_PER_SOURCE = int(os.getenv("MAX_PER_SOURCE", "150"))
MAX_HTML_LINKS_PER_SOURCE = int(os.getenv("MAX_HTML_LINKS_PER_SOURCE", "80"))
MAX_HTML_SOURCES_PER_RUN = int(os.getenv("MAX_HTML_SOURCES_PER_RUN", "35"))
MAX_COMPANIES_PER_RUN = int(os.getenv("MAX_COMPANIES_PER_RUN", "80"))
MAX_REVIEW_ROWS = int(os.getenv("MAX_REVIEW_ROWS", "500"))
WRITE_REVIEW_QUEUE = os.getenv("WRITE_REVIEW_QUEUE", "true").lower().strip() == "true"
VALIDATE_JOB_LINKS = os.getenv("VALIDATE_JOB_LINKS", "false").lower().strip() == "true"
RUN_MODE = os.getenv("RUN_MODE", "strict").lower().strip()

TECH_SIGNALS = [
    "engineer",
    "developer",
    "software",
    "frontend",
    "front end",
    "front-end",
    "backend",
    "back end",
    "back-end",
    "fullstack",
    "full stack",
    "full-stack",
    "react",
    "node",
    "python",
    "java",
    "javascript",
    "typescript",
    "php",
    "laravel",
    "ruby",
    "rails",
    "golang",
    "go engineer",
    "rust",
    "kotlin",
    "swift",
    "ios",
    "android",
    "mobile",
    "devops",
    "sre",
    "site reliability",
    "cloud",
    "aws",
    "azure",
    "gcp",
    "kubernetes",
    "terraform",
    "platform engineer",
    "security engineer",
    "qa engineer",
    "automation engineer",
    "data engineer",
    "data scientist",
    "ml engineer",
    "machine learning engineer",
    "ai engineer",
    "architect",
    "tech lead",
    "technical lead",
    "staff engineer",
    "principal engineer",
    "wordpress",
    "shopify",
    "magento",
    "flutter",
    "react native",
]

NON_TECH_BLOCKERS = [
    "sales",
    "account executive",
    "business development",
    "customer support",
    "customer success",
    "recruiter",
    "talent acquisition",
    "human resources",
    "hr",
    "finance",
    "accountant",
    "marketing",
    "copywriter",
    "designer",
    "content",
    "operations",
    "legal",
]

STRICT_GLOBAL_SIGNALS = [
    "worldwide",
    "anywhere",
    "work from anywhere",
    "remote worldwide",
    "remote globally",
    "global remote",
    "globally remote",
    "open globally",
    "open worldwide",
    "all countries",
    "any country",
    "no location requirement",
    "location independent",
    "distributed team",
    "globally distributed",
    "international candidates",
    "international applicants",
    "open to all locations",
    "open to all countries",
    "we hire globally",
    "hire globally",
    "remote first company",
    "remote-first company",
    "work from wherever",
    "work from wherever you are",
    "work remotely from anywhere",
    "work anywhere",
    "anywhere in the world",
    "as long as you can overlap",
    "remote across the globe",
    "global team",
    "global timezone friendly",
    "location agnostic",
    "location-agnostic",
    "independently verified",
    "contractor worldwide",
    "contractors worldwide",
    "work from any country",
]

BANGLADESH_OK_SIGNALS = [
    "bangladesh",
    "south asia",
    "asia",
    "worldwide",
    "anywhere",
    "global",
    "all countries",
    "international candidates",
]

HARD_RESTRICTED_SIGNALS = [
    "united states only",
    "us only",
    "usa only",
    "u.s. only",
    "must be in the us",
    "must be based in the us",
    "authorized to work in the us",
    "eligible to work in the us",
    "us residents only",
    "uk only",
    "united kingdom only",
    "must be based in the uk",
    "eligible to work in the uk",
    "uk residents only",
    "canada only",
    "australia only",
    "new zealand only",
    "eu only",
    "europe only",
    "european union only",
    "latam only",
    "latin america only",
    "north america only",
    "emea only",
    "apac only",
    "must reside in",
    "must be located in",
    "must be based in",
    "local candidates only",
    "right to work in",
    "citizenship required",
    "no visa sponsorship",
    "security clearance",
    "clearance required",
    "must hold a passport",
    "must be a citizen",
    "hybrid",
    "onsite",
    "on-site",
    "relocation",
]

COUNTRY_LOCK_REGEX = re.compile(
    r"\b(remote\s*(in|from)?\s*)?\(?\b("
    r"us|usa|u\.s\.|united states|uk|united kingdom|canada|australia|new zealand|"
    r"germany|france|spain|ireland|netherlands|poland|portugal|sweden|finland|"
    r"norway|denmark|switzerland|austria|italy|belgium|latam|latin america|"
    r"north america|europe|eu|emea|apac"
    r")\b\)?\s*(only|required|based|residents|citizens)?\b",
    re.IGNORECASE,
)

UTM_KEYS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref", "source"}


@dataclass
class Job:
    company: str = ""
    company_website: str = ""
    title: str = ""
    job_url: str = ""
    location: str = ""
    tags: str = ""
    posted: str = ""
    source: str = ""
    desc: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)
    eligibility: str = ""
    eligibility_confidence: int = 0
    eligibility_evidence: str = ""

    def fingerprint(self) -> str:
        base = "|".join([
            normalize_company(self.company),
            normalize_text(self.title),
            normalize_url(self.job_url),
        ])
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_text(value: Any) -> str:
    value = html.unescape(str(value or "")).lower()
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[^a-z0-9+.#\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def strip_html(value: Any) -> str:
    value = html.unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_company(value: str) -> str:
    value = normalize_text(value)
    for suffix in [" inc", " llc", " ltd", " limited", " gmbh", " corp", " corporation", " co"]:
        if value.endswith(suffix):
            value = value[: -len(suffix)].strip()
    return value


def normalize_url(url: str) -> str:
    url = str(url or "").strip()
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in UTM_KEYS]
        clean = parsed._replace(fragment="", query=urlencode(query))
        out = urlunparse(clean)
        return out.rstrip("/")
    except Exception:
        return url.rstrip("/")


def safe_date(value: Any) -> str:
    if not value:
        return ""
    try:
        return dateparser.parse(str(value)).date().isoformat()
    except Exception:
        return str(value)[:20]


def http_get(url: str, params: Optional[Dict[str, Any]] = None) -> Optional[requests.Response]:
    try:
        res = SESSION.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if res.status_code >= 400:
            return None
        return res
    except Exception:
        return None


def fetch_json(url: str, params: Optional[Dict[str, Any]] = None) -> Any:
    res = http_get(url, params=params)
    if not res:
        return None
    try:
        return res.json()
    except Exception:
        return None




def domain_to_company(domain: str) -> str:
    domain = re.sub(r"^https?://", "", str(domain or "").strip().lower()).split("/")[0]
    domain = domain.replace("www.", "")
    base = domain.split(".")[0]
    return base.replace("-", " ").replace("_", " ").title()


def stable_daily_slice(items: List[Dict[str, Any]], limit: int, salt: str) -> List[Dict[str, Any]]:
    """Rotate huge source lists across days so the free runner stays healthy."""
    if limit <= 0 or len(items) <= limit:
        return items
    today = datetime.now(timezone.utc).date().toordinal()
    start = (today * (17 + len(salt))) % len(items)
    doubled = items + items
    return doubled[start:start + limit]


def source_is_trusted_global(name: str, url: str = "", why: str = "") -> bool:
    text = normalize_text(" ".join([name, url, why]))
    trusted_terms = [
        "real work from anywhere",
        "work from anywhere",
        "wearedistributed",
        "we are distributed",
        "worldwide",
        "anywhere",
        "remote in tech worldwide",
        "companies hiring worldwide",
    ]
    return any(term in text for term in trusted_terms)


def get_soup(url: str) -> Optional[Any]:
    if BeautifulSoup is None:
        return None
    res = http_get(url)
    if not res or not res.text:
        return None
    return BeautifulSoup(res.text, "html.parser")


def anchor_text(a: Any) -> str:
    try:
        return re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
    except Exception:
        return ""


def looks_like_job_link(text: str, href: str) -> bool:
    t = normalize_text(text)
    h = (href or "").lower()
    if len(t) < 5 or len(t) > 180:
        return False
    if any(x in h for x in ["/jobs/", "/job/", "/careers/", "/career/", "/positions/", "/position/", "/openings/", "/opening/", "/postings/"]):
        return True
    if any(sig in t for sig in TECH_SIGNALS):
        return True
    return False


def split_title_company(title: str, fallback_company: str = "") -> Tuple[str, str]:
    title = re.sub(r"\s+", " ", str(title or "")).strip()
    company = fallback_company
    job_title = title
    if " at " in title.lower():
        parts = re.split(r"\s+at\s+", title, flags=re.IGNORECASE)
        if len(parts) >= 2:
            job_title = " at ".join(parts[:-1]).strip()
            company = parts[-1].strip() or company
    elif ": " in title:
        left, right = title.split(": ", 1)
        # Most job feeds use "Company: Role".
        if any(sig in normalize_text(right) for sig in TECH_SIGNALS):
            company = left.strip() or company
            job_title = right.strip()
    return job_title, company


def generic_html_jobs(name: str, url: str, trusted_global: bool = False, role_focus: str = "", why: str = "") -> List[Job]:
    """Best-effort free HTML parser for public job/category pages.

    It will not work on every dynamic site. That is normal. Source Health will show failures/zeroes.
    """
    soup = get_soup(url)
    if not soup:
        return []
    fallback_company = domain_to_company(urlparse(url).netloc)
    global_source = trusted_global or source_is_trusted_global(name, url, why)
    out: List[Job] = []
    seen_links = set()

    for a in soup.find_all("a", href=True):
        text = anchor_text(a)
        href = urljoin(url, a.get("href", ""))
        href = normalize_url(href)
        if not href or href in seen_links:
            continue
        if not looks_like_job_link(text, href):
            continue
        seen_links.add(href)

        job_title, company = split_title_company(text, fallback_company="")
        if not company and "company" in normalize_text(name):
            company = fallback_company
        desc = text
        parent = a.find_parent()
        if parent:
            desc = strip_html(parent.get_text(" ", strip=True))[:3000]
        if global_source:
            desc = ("DSI trusted global source: source is curated for worldwide/work-from-anywhere hiring. " + desc)[:3000]
        out.append(
            Job(
                company=company or fallback_company,
                company_website=f"https://{urlparse(url).netloc}" if urlparse(url).netloc else "",
                title=job_title,
                job_url=href,
                location="worldwide" if global_source else "unknown",
                tags=role_focus,
                posted="",
                source=f"HTML {name}",
                desc=desc,
                raw={"source_page": url, "trusted_global_source": global_source},
            )
        )
        if len(out) >= MAX_HTML_LINKS_PER_SOURCE:
            break
    return out


def rss_hub_jobs(name: str, url: str) -> List[Job]:
    """Find RSS/Atom links on a hub page, then parse the discovered feeds."""
    soup = get_soup(url)
    if not soup:
        return generic_rss_jobs(name, url)
    feed_urls = []
    for tag in soup.find_all(["a", "link"], href=True):
        href = tag.get("href", "")
        text = normalize_text(anchor_text(tag) or tag.get("title", "") or tag.get("type", ""))
        if any(x in href.lower() for x in ["rss", "feed", "atom", ".xml"]) or any(x in text for x in ["rss", "feed", "atom"]):
            full = normalize_url(urljoin(url, href))
            if full and full not in feed_urls:
                feed_urls.append(full)
    out: List[Job] = []
    for feed_url in feed_urls[:12]:
        out.extend(generic_rss_jobs(f"{name} feed", feed_url))
        time.sleep(0.2)
    return out


def extract_ats_links(html_text: str, base_url: str = "") -> Dict[str, set]:
    links = {"greenhouse": set(), "lever": set(), "ashby": set(), "workable": set(), "smartrecruiters": set()}
    if not html_text:
        return links
    soup = BeautifulSoup(html_text, "html.parser") if BeautifulSoup else None
    hrefs = []
    if soup:
        hrefs = [urljoin(base_url, a.get("href", "")) for a in soup.find_all("a", href=True)]
    hrefs.append(base_url)
    hrefs.extend(re.findall(r"https?://[^\s'\"<>]+", html_text))
    for href in hrefs:
        h = href.strip().rstrip(".,)")
        parsed = urlparse(h)
        host = parsed.netloc.lower()
        parts = [p for p in parsed.path.split("/") if p]
        if not parts:
            continue
        if "greenhouse.io" in host:
            token = parts[0]
            if token and token not in {"jobs", "boards", "v1"}:
                links["greenhouse"].add(token)
        elif "lever.co" in host:
            token = parts[0]
            if token:
                links["lever"].add(token)
        elif "ashbyhq.com" in host:
            token = parts[0]
            if token and token not in {"posting-api", "job-board"}:
                links["ashby"].add(token)
        elif "apply.workable.com" in host:
            token = parts[0]
            if token:
                links["workable"].add(token)
        elif "jobs.smartrecruiters.com" in host:
            token = parts[0]
            if token:
                links["smartrecruiters"].add(token)
    return links


def fetch_company_pages(domain: str) -> List[Tuple[str, str]]:
    domain = str(domain or "").strip().strip("/")
    if not domain:
        return []
    if not domain.startswith("http"):
        root = "https://" + domain
    else:
        root = domain
    paths = ["/", "/careers", "/jobs", "/careers/jobs", "/company/careers", "/join-us", "/work-with-us", "/about/careers"]
    pages: List[Tuple[str, str]] = []
    for path in paths:
        url = root.rstrip("/") + path
        res = http_get(url)
        if res and res.text:
            pages.append((url, res.text[:400000]))
        time.sleep(0.15)
    return pages


def workable_html_jobs(company: str, slug: str) -> List[Job]:
    url = f"https://apply.workable.com/{slug}/"
    return generic_html_jobs(f"Workable {company or slug}", url, trusted_global=False, role_focus="Engineering / Developer / IT")


def smartrecruiters_jobs(company: str, slug: str) -> List[Job]:
    data = fetch_json(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings", {"limit": 100})
    out: List[Job] = []
    for item in (data or {}).get("content", []) or []:
        loc = ""
        if isinstance(item.get("location"), dict):
            loc = item.get("location", {}).get("fullLocation", "")
        out.append(
            Job(
                company=company or slug,
                title=item.get("name", ""),
                job_url=item.get("ref", "") or item.get("url", ""),
                location=loc,
                tags=item.get("department", {}).get("label", "") if isinstance(item.get("department"), dict) else "",
                posted=item.get("releasedDate", ""),
                source=f"SmartRecruiters {company or slug}",
                desc=strip_html(item.get("jobAd", {}).get("sections", {}).get("jobDescription", ""))[:3000] if isinstance(item.get("jobAd"), dict) else "",
                raw=item,
            )
        )
    return out


def company_ats_discovery_jobs(company: str, domain: str) -> List[Job]:
    """Use the 500+ source company watchlist without scraping Google.

    It visits the company's own careers pages and extracts public ATS links.
    This is free and safer than scraping Google results directly.
    """
    out: List[Job] = []
    found = {"greenhouse": set(), "lever": set(), "ashby": set(), "workable": set(), "smartrecruiters": set()}
    for page_url, html_text in fetch_company_pages(domain):
        links = extract_ats_links(html_text, page_url)
        for k, vals in links.items():
            found[k].update(vals)
    for board in sorted(found["greenhouse"]):
        out.extend(greenhouse_jobs(board))
        time.sleep(0.2)
    for slug in sorted(found["lever"]):
        out.extend(lever_jobs(slug))
        time.sleep(0.2)
    for board in sorted(found["ashby"]):
        out.extend(ashby_jobs(board))
        time.sleep(0.2)
    for slug in sorted(found["workable"]):
        out.extend(workable_html_jobs(company, slug))
        time.sleep(0.2)
    for slug in sorted(found["smartrecruiters"]):
        out.extend(smartrecruiters_jobs(company, slug))
        time.sleep(0.2)
    # If no ATS was discovered, try the company careers page itself as a very light fallback.
    if not out:
        for path in ["careers", "jobs"]:
            out.extend(generic_html_jobs(f"Company Careers {company}", f"https://{domain.rstrip('/')}/{path}", trusted_global=False, role_focus="Engineering / Developer / IT")[:25])
            if out:
                break
    for job in out:
        if not job.company or normalize_company(job.company) == normalize_company(urlparse(job.company_website).netloc):
            job.company = company
        if not job.company_website:
            job.company_website = f"https://{domain.strip('/')}"
    return out


def link_is_live(url: str) -> bool:
    try:
        res = SESSION.head(url, allow_redirects=True, timeout=12)
        if res.status_code < 400:
            return True
        # Some sites block HEAD but allow GET.
        res = SESSION.get(url, allow_redirects=True, timeout=12, stream=True)
        return res.status_code < 400
    except Exception:
        return False

def is_tech_job(job: Job) -> Tuple[bool, str]:
    title = normalize_text(job.title)
    text = normalize_text(" ".join([job.title, job.tags, job.desc]))

    for blocker in NON_TECH_BLOCKERS:
        if blocker in title and not any(signal in text for signal in TECH_SIGNALS):
            return False, "blocked non-tech title"

    for signal in TECH_SIGNALS:
        if signal in text:
            return True, signal

    return False, "no engineering signal"


def find_signal(text: str, signals: Iterable[str]) -> str:
    for signal in signals:
        if signal in text:
            return signal
    return ""


def classify_remote_eligibility(job: Job) -> Tuple[str, int, str]:
    loc = normalize_text(job.location)
    text = normalize_text(" ".join([job.location, job.title, job.tags, job.desc]))

    restricted = find_signal(text, HARD_RESTRICTED_SIGNALS)
    if restricted:
        return "COUNTRY_RESTRICTED", 95, restricted

    if COUNTRY_LOCK_REGEX.search(text):
        return "COUNTRY_RESTRICTED", 85, "country or region restriction detected"

    if "bangladesh" in text:
        return "BANGLADESH_OK", 100, "bangladesh"

    global_signal = find_signal(text, STRICT_GLOBAL_SIGNALS)
    if global_signal:
        return "GLOBAL_OK", 90, global_signal

    # Some sources from the uploaded 500+ source catalog are specifically curated for
    # worldwide/work-from-anywhere roles. We still reject them above if any country lock exists.
    if "dsi trusted global source" in text:
        return "GLOBAL_OK", 75, "trusted worldwide/work-from-anywhere source; verify before outreach"

    if loc in {"", "remote", "fully remote", "unknown", "work from home"}:
        return "NEEDS_VERIFICATION", 40, "remote is not enough proof of global hiring"

    return "NEEDS_VERIFICATION", 50, "no clear global hiring proof"


def source_log(source: str, count: int, status: str, message: str, duration_ms: int) -> Dict[str, Any]:
    return {
        "run_time": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "jobs_returned": count,
        "status": status,
        "message": message,
        "duration_ms": duration_ms,
    }


def run_source(name: str, fn) -> Tuple[List[Job], Dict[str, Any]]:
    start = time.time()
    try:
        jobs = fn()
        if not isinstance(jobs, list):
            jobs = []
        jobs = jobs[:MAX_PER_SOURCE]
        return jobs, source_log(name, len(jobs), "OK", "", int((time.time() - start) * 1000))
    except Exception as exc:
        return [], source_log(name, 0, "FAILED", str(exc), int((time.time() - start) * 1000))


def remotive_jobs(category: str) -> List[Job]:
    data = fetch_json("https://remotive.com/api/remote-jobs", {"category": category, "limit": 100})
    out: List[Job] = []
    for item in (data or {}).get("jobs", []):
        out.append(
            Job(
                company=item.get("company_name", ""),
                company_website=item.get("company_url", ""),
                title=item.get("title", ""),
                job_url=item.get("url", ""),
                location=item.get("candidate_required_location", ""),
                tags=", ".join(item.get("tags", []) or []),
                posted=item.get("publication_date", ""),
                source=f"Remotive {category}",
                desc=strip_html(item.get("description", ""))[:3000],
                raw=item,
            )
        )
    return out


def remoteok_api() -> List[Job]:
    data = fetch_json("https://remoteok.com/api")
    if not isinstance(data, list):
        return []
    out: List[Job] = []
    for item in data[1:]:
        if not isinstance(item, dict):
            continue
        out.append(
            Job(
                company=item.get("company", ""),
                company_website=f"https://remoteok.com/l/{item.get('slug') or item.get('id') or ''}",
                title=item.get("position") or item.get("title") or "",
                job_url=item.get("url") or f"https://remoteok.com/l/{item.get('slug') or item.get('id') or ''}",
                location=item.get("location", ""),
                tags=", ".join(item.get("tags", []) or []) if isinstance(item.get("tags"), list) else str(item.get("tags", "")),
                posted=item.get("date", ""),
                source="RemoteOK API",
                desc=strip_html(item.get("description", ""))[:3000],
                raw=item,
            )
        )
    return out


def remoteok_rss(tag: str) -> List[Job]:
    url = f"https://remoteok.com/remote-{tag}-jobs.rss"
    feed = feedparser.parse(url)
    out: List[Job] = []
    for entry in feed.entries:
        title = entry.get("title", "")
        company = ""
        job_title = title
        if " at " in title:
            parts = title.split(" at ")
            company = parts[-1].strip()
            job_title = " at ".join(parts[:-1]).strip()
        out.append(
            Job(
                company=company,
                title=job_title,
                job_url=entry.get("link", ""),
                location="unknown",
                tags=tag,
                posted=entry.get("published", ""),
                source=f"RemoteOK RSS {tag}",
                desc=strip_html(entry.get("summary", ""))[:3000],
                raw=dict(entry),
            )
        )
    return out


def jobicy_jobs(industry: str) -> List[Job]:
    variants = [
        {"count": 100, "geo": "worldwide", "industry": industry},
        {"count": 100, "geo": "worldwide", "tag": "software-developer"},
        {"count": 100, "geo": "worldwide", "tag": "senior-engineer"},
    ]
    out: List[Job] = []
    for params in variants:
        data = fetch_json("https://jobicy.com/api/v2/remote-jobs", params)
        for item in (data or {}).get("jobs", []):
            out.append(
                Job(
                    company=item.get("companyName", ""),
                    company_website=item.get("companyUrl", ""),
                    title=item.get("jobTitle", ""),
                    job_url=item.get("url", ""),
                    location=item.get("jobGeo", ""),
                    tags=", ".join(item.get("jobIndustry", []) or []) if isinstance(item.get("jobIndustry"), list) else str(item.get("jobIndustry", "")),
                    posted=item.get("pubDate", ""),
                    source=f"Jobicy {industry}",
                    desc=strip_html(item.get("jobExcerpt", ""))[:3000],
                    raw=item,
                )
            )
        time.sleep(0.3)
    return out


def arbeitnow_jobs(page: int) -> List[Job]:
    data = fetch_json("https://arbeitnow.com/api/job-board-api", {"remote": "true", "page": page})
    out: List[Job] = []
    for item in (data or {}).get("data", []):
        out.append(
            Job(
                company=item.get("company_name", ""),
                company_website=item.get("url", ""),
                title=item.get("title", ""),
                job_url=item.get("url", ""),
                location=item.get("location", ""),
                tags=", ".join(item.get("tags", []) or []) if isinstance(item.get("tags"), list) else "",
                posted=datetime.fromtimestamp(item.get("created_at", 0), timezone.utc).isoformat() if item.get("created_at") else "",
                source=f"Arbeitnow page {page}",
                desc=strip_html(item.get("description", ""))[:3000],
                raw=item,
            )
        )
    return out


def wwr_rss(category: str) -> List[Job]:
    url = f"https://weworkremotely.com/categories/{category}.rss"
    feed = feedparser.parse(url)
    out: List[Job] = []
    for entry in feed.entries:
        title = entry.get("title", "")
        company = ""
        job_title = title
        if ": " in title:
            company, job_title = title.split(": ", 1)
        loc = entry.get("region") or entry.get("location") or "unknown"
        out.append(
            Job(
                company=company,
                title=job_title,
                job_url=entry.get("link", ""),
                location=loc,
                tags=category,
                posted=entry.get("published", ""),
                source=f"WWR {category}",
                desc=strip_html(entry.get("summary", ""))[:3000],
                raw=dict(entry),
            )
        )
    return out


def generic_rss_jobs(name: str, url: str) -> List[Job]:
    feed = feedparser.parse(url)
    out: List[Job] = []
    for entry in feed.entries:
        title = entry.get("title", "")
        company = ""
        job_title = title
        if " at " in title:
            parts = title.split(" at ")
            company = parts[-1].strip()
            job_title = " at ".join(parts[:-1]).strip()
        elif ": " in title:
            company, job_title = title.split(": ", 1)
        out.append(
            Job(
                company=company,
                title=job_title,
                job_url=entry.get("link", ""),
                location="unknown",
                tags="",
                posted=entry.get("published", ""),
                source=name,
                desc=strip_html(entry.get("summary", ""))[:3000],
                raw=dict(entry),
            )
        )
    return out


def generic_rss_jobs_with_trust(name: str, url: str, trusted_global: bool = False) -> List[Job]:
    jobs = generic_rss_jobs(name, url)
    if trusted_global:
        for job in jobs:
            job.location = job.location if job.location and normalize_text(job.location) != "unknown" else "worldwide"
            job.desc = ("DSI trusted global source: source is curated for worldwide/work-from-anywhere hiring. " + (job.desc or ""))[:3000]
    return jobs


def himalayas_search_jobs(query: str, pages: int = 3) -> List[Job]:
    """Himalayas official free API. Uses worldwide=true so Bangladesh/global fit is stronger."""
    out: List[Job] = []
    for page in range(1, pages + 1):
        data = fetch_json(
            "https://himalayas.app/jobs/api/search",
            {"q": query, "worldwide": "true", "sort": "recent", "page": page},
        )
        for item in (data or {}).get("jobs", []) or []:
            company_obj = item.get("company") or {}
            if not isinstance(company_obj, dict):
                company_obj = {}
            categories = item.get("categories") or item.get("tags") or []
            if isinstance(categories, list):
                tags = ", ".join([str(x.get("name") if isinstance(x, dict) else x) for x in categories])
            else:
                tags = str(categories or "")
            loc_parts = []
            for key in ["location", "locationName", "locations", "country", "timezone"]:
                val = item.get(key)
                if isinstance(val, list):
                    loc_parts.extend([str(v.get("name") if isinstance(v, dict) else v) for v in val])
                elif val:
                    loc_parts.append(str(val))
            location = ", ".join([x for x in loc_parts if x]) or "worldwide"
            desc = item.get("description") or item.get("descriptionHtml") or item.get("excerpt") or ""
            out.append(
                Job(
                    company=company_obj.get("name", "") or item.get("companyName", ""),
                    company_website=company_obj.get("website", "") or company_obj.get("url", ""),
                    title=item.get("title", ""),
                    job_url=item.get("applicationLink") or item.get("applyUrl") or item.get("url") or item.get("jobUrl") or "",
                    location=location,
                    tags=tags or query,
                    posted=item.get("publishedAt") or item.get("createdAt") or item.get("postedAt") or "",
                    source=f"Himalayas API worldwide {query}",
                    desc=("worldwide=true. " + strip_html(desc))[:3000],
                    raw=item,
                )
            )
        time.sleep(0.25)
    return out


def jobscollider_jobs(category: str) -> List[Job]:
    """JobsCollider public search API. Keep attribution in source and filter hard."""
    data = fetch_json("https://jobscollider.com/api/search-jobs", {"category": category})
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("jobs") or data.get("data") or data.get("results") or data.get("items") or []
    else:
        items = []
    out: List[Job] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        company = item.get("company") or item.get("company_name") or item.get("companyName") or ""
        if isinstance(company, dict):
            company = company.get("name", "")
        loc = item.get("location") or item.get("jobGeo") or item.get("candidate_required_location") or ""
        desc = item.get("description") or item.get("summary") or item.get("excerpt") or ""
        out.append(
            Job(
                company=str(company or ""),
                company_website=item.get("company_url") or item.get("companyUrl") or "",
                title=item.get("title") or item.get("job_title") or item.get("jobTitle") or "",
                job_url=item.get("url") or item.get("job_url") or item.get("jobUrl") or item.get("apply_url") or "",
                location=str(loc or ""),
                tags=category,
                posted=item.get("date") or item.get("published") or item.get("published_at") or item.get("pubDate") or "",
                source=f"JobsCollider API {category}",
                desc=strip_html(desc)[:3000],
                raw=item,
            )
        )
    return out


def greenhouse_jobs(board: str) -> List[Job]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
    data = fetch_json(url, {"content": "true"})
    out: List[Job] = []
    for item in (data or {}).get("jobs", []):
        location = ""
        if isinstance(item.get("location"), dict):
            location = item.get("location", {}).get("name", "")
        out.append(
            Job(
                company=board,
                title=item.get("title", ""),
                job_url=item.get("absolute_url", ""),
                location=location,
                tags=", ".join([d.get("name", "") for d in item.get("departments", []) if isinstance(d, dict)]),
                posted=item.get("updated_at", ""),
                source=f"Greenhouse {board}",
                desc=strip_html(item.get("content", ""))[:3000],
                raw=item,
            )
        )
    return out


def lever_jobs(company: str) -> List[Job]:
    url = f"https://api.lever.co/v0/postings/{company}"
    data = fetch_json(url, {"mode": "json"})
    out: List[Job] = []
    if not isinstance(data, list):
        return out
    for item in data:
        categories = item.get("categories") or {}
        location = categories.get("location", "") if isinstance(categories, dict) else ""
        tags = categories.get("team", "") if isinstance(categories, dict) else ""
        out.append(
            Job(
                company=company,
                title=item.get("text", ""),
                job_url=item.get("hostedUrl", ""),
                location=location,
                tags=tags,
                posted=item.get("createdAt", ""),
                source=f"Lever {company}",
                desc=strip_html(item.get("descriptionPlain", "") or item.get("description", ""))[:3000],
                raw=item,
            )
        )
    return out


def ashby_jobs(board: str) -> List[Job]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{board}"
    try:
        res = SESSION.post(url, json={"includeCompensation": False}, timeout=REQUEST_TIMEOUT)
        if res.status_code >= 400:
            return []
        data = res.json()
    except Exception:
        return []
    out: List[Job] = []
    for item in (data or {}).get("jobs", []):
        loc = item.get("locationName") or item.get("location", "")
        out.append(
            Job(
                company=board,
                title=item.get("title", ""),
                job_url=item.get("jobUrl") or item.get("applyUrl") or "",
                location=loc,
                tags=", ".join(item.get("departmentHierarchy", []) or []) if isinstance(item.get("departmentHierarchy"), list) else "",
                posted=item.get("publishedAt", ""),
                source=f"Ashby {board}",
                desc=strip_html(item.get("descriptionHtml", "") or item.get("description", ""))[:3000],
                raw=item,
            )
        )
    return out


def build_sources() -> List[Tuple[str, Any]]:
    sources_cfg = load_json(os.path.join(CONFIG_DIR, "sources.json"))
    ats_cfg = load_json(os.path.join(CONFIG_DIR, "ats_companies.json"))
    expanded_path = os.path.join(CONFIG_DIR, "expanded_sources.json")
    expanded_cfg = load_json(expanded_path) if os.path.exists(expanded_path) else {}
    sources = []

    # 1. Strong direct APIs and RSS feeds.
    for cat in sources_cfg.get("remotive_categories", []):
        sources.append((f"Remotive {cat}", lambda cat=cat: remotive_jobs(cat)))

    sources.append(("RemoteOK API", remoteok_api))

    for tag in sources_cfg.get("remoteok_tags", []):
        sources.append((f"RemoteOK RSS {tag}", lambda tag=tag: remoteok_rss(tag)))

    for industry in sources_cfg.get("jobicy_industries", []):
        sources.append((f"Jobicy {industry}", lambda industry=industry: jobicy_jobs(industry)))

    for query in sources_cfg.get("himalayas_queries", []):
        sources.append((f"Himalayas API worldwide {query}", lambda query=query: himalayas_search_jobs(query)))

    for category in sources_cfg.get("jobscollider_categories", []):
        sources.append((f"JobsCollider API {category}", lambda category=category: jobscollider_jobs(category)))

    for page in range(1, 6):
        sources.append((f"Arbeitnow page {page}", lambda page=page: arbeitnow_jobs(page)))

    for category in sources_cfg.get("wwr_categories", []):
        sources.append((f"WWR {category}", lambda category=category: wwr_rss(category)))

    for item in sources_cfg.get("generic_rss", []):
        sources.append((item["name"], lambda item=item: generic_rss_jobs_with_trust(item["name"], item["url"], bool(item.get("trusted_global_source")))))

    for item in sources_cfg.get("always_html", []):
        sources.append((
            f"Always HTML {item['name']}",
            lambda item=item: generic_html_jobs(
                item["name"],
                item["url"],
                trusted_global=bool(item.get("trusted_global_source")),
                role_focus=item.get("role_focus", "Engineering / Developer / IT"),
            ),
        ))

    # 2. Extra RSS feeds and RSS hub pages from the uploaded 500+ source catalog.
    for item in expanded_cfg.get("rss_feeds_from_catalog", []):
        sources.append((f"Catalog RSS {item['name']}", lambda item=item: generic_rss_jobs(item["name"], item["url"])))

    for item in expanded_cfg.get("rss_hubs_from_catalog", []):
        sources.append((f"Catalog RSS Hub {item['name']}", lambda item=item: rss_hub_jobs(item["name"], item["url"])))

    # 3. Public HTML job/category pages from the source catalog.
    html_pages = stable_daily_slice(expanded_cfg.get("html_pages_from_catalog", []), MAX_HTML_SOURCES_PER_RUN, "html")
    for item in html_pages:
        sources.append((
            f"Catalog HTML {item['name']}",
            lambda item=item: generic_html_jobs(
                item["name"],
                item["url"],
                trusted_global=bool(item.get("trusted_global_source")),
                role_focus=item.get("role_focus", ""),
                why=item.get("why_strong", ""),
            ),
        ))

    # 4. Direct ATS company watchlist.
    for board in ats_cfg.get("greenhouse_boards", []):
        sources.append((f"Greenhouse {board}", lambda board=board: greenhouse_jobs(board)))

    for company in ats_cfg.get("lever_companies", []):
        sources.append((f"Lever {company}", lambda company=company: lever_jobs(company)))

    for board in ats_cfg.get("ashby_boards", []):
        sources.append((f"Ashby {board}", lambda board=board: ashby_jobs(board)))

    # 5. Company seed list from your uploaded 500+ source sheet.
    # The engine rotates through this list every day to stay free and stable.
    company_watchlist = stable_daily_slice(expanded_cfg.get("company_watchlist", []), MAX_COMPANIES_PER_RUN, "company")
    for item in company_watchlist:
        company = item.get("company", "")
        domain = item.get("domain", "")
        sources.append((f"Company ATS Discovery {company}", lambda company=company, domain=domain: company_ats_discovery_jobs(company, domain)))

    return sources


def qualify_jobs(jobs: List[Job]) -> Tuple[List[Job], Dict[str, int], List[Job]]:
    stats = {
        "raw": len(jobs),
        "tech": 0,
        "global_ok": 0,
        "bangladesh_ok": 0,
        "needs_verification": 0,
        "country_restricted": 0,
        "not_tech": 0,
        "deduped": 0,
        "broken_link": 0,
    }
    qualified: List[Job] = []
    review_candidates: List[Job] = []
    seen = set()

    for job in jobs:
        job.job_url = normalize_url(job.job_url)
        if not job.job_url:
            continue

        is_tech, tech_evidence = is_tech_job(job)
        if not is_tech:
            stats["not_tech"] += 1
            continue
        stats["tech"] += 1

        status, confidence, evidence = classify_remote_eligibility(job)
        job.eligibility = status
        job.eligibility_confidence = confidence
        job.eligibility_evidence = evidence

        if status == "GLOBAL_OK":
            stats["global_ok"] += 1
        elif status == "BANGLADESH_OK":
            stats["bangladesh_ok"] += 1
        elif status == "NEEDS_VERIFICATION":
            stats["needs_verification"] += 1
        elif status == "COUNTRY_RESTRICTED":
            stats["country_restricted"] += 1

        if RUN_MODE == "strict" and status not in {"GLOBAL_OK", "BANGLADESH_OK"}:
            if WRITE_REVIEW_QUEUE and status == "NEEDS_VERIFICATION" and len(review_candidates) < MAX_REVIEW_ROWS:
                review_candidates.append(job)
            continue
        if RUN_MODE == "review" and status == "COUNTRY_RESTRICTED":
            continue

        if VALIDATE_JOB_LINKS and not link_is_live(job.job_url):
            stats["broken_link"] += 1
            continue

        url_key = normalize_url(job.job_url) or job.fingerprint()
        company_title_key = hashlib.sha256((normalize_company(job.company) + "|" + normalize_text(job.title)).encode("utf-8")).hexdigest()[:24]
        if url_key in seen or company_title_key in seen:
            stats["deduped"] += 1
            continue
        seen.add(url_key)
        seen.add(company_title_key)
        qualified.append(job)

    stats["review_queue"] = len(review_candidates)
    return qualified, stats, review_candidates


def guess_region(job: Job) -> str:
    text = normalize_text(" ".join([job.company_website, job.job_url, job.source, job.location]))
    if "uk" in text or ".co.uk" in text:
        return "UK"
    if "australia" in text or ".com.au" in text:
        return "Australia"
    if "new zealand" in text or ".co.nz" in text:
        return "New Zealand"
    if "ireland" in text or ".ie" in text:
        return "Ireland"
    if "netherlands" in text or ".nl" in text:
        return "Netherlands"
    if "europe" in text or "greenhouse" in text or "lever" in text:
        return "US or Global"
    return "US or Global"


def priority(job: Job) -> str:
    score = 0
    title = normalize_text(job.title)
    loc = normalize_text(job.location)
    source = normalize_text(job.source)
    if job.eligibility in {"GLOBAL_OK", "BANGLADESH_OK"}:
        score += 2
    if "worldwide" in loc or "anywhere" in loc or "global" in loc:
        score += 2
    if any(x in title for x in ["senior", "lead", "staff", "principal", "architect"]):
        score += 2
    if any(x in title for x in ["engineering manager", "cto", "vp engineering", "head of engineering"]):
        score += 3
    if any(x in source for x in ["greenhouse", "lever", "ashby"]):
        score += 1
    if score >= 6:
        return "High"
    if score >= 3:
        return "Medium"
    return "Normal"


def job_to_row(job: Job) -> List[Any]:
    today = datetime.now().date().isoformat()
    return [
        today,
        job.company or "Unknown",
        job.company_website,
        job.title,
        job.job_url,
        "Global Remote" if job.eligibility in {"GLOBAL_OK", "BANGLADESH_OK"} else "Remote Review",
        job.location or "Unknown",
        (job.tags or "")[:220],
        safe_date(job.posted),
        job.source,
        guess_region(job),
        "New Lead",
        priority(job),
        "",
        "",
        "",
        job.eligibility,
        job.eligibility_confidence,
        job.eligibility_evidence,
        "Proof required before outreach. Do not contact if country restricted.",
    ]


def review_to_row(job: Job) -> List[Any]:
    return job_to_row(job) + [
        "Manually open job URL and check if Bangladesh or worldwide candidates are accepted",
        job.eligibility_evidence or "Needs proof of global hiring",
    ]


def write_csv(jobs: List[Job], review_jobs: List[Job], source_runs: List[Dict[str, Any]], stats: Dict[str, int]) -> Tuple[str, str, str, str]:
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    leads_path = os.path.join(OUTPUT_DIR, f"qualified_leads_{stamp}.csv")
    review_path = os.path.join(OUTPUT_DIR, f"review_queue_{stamp}.csv")
    runs_path = os.path.join(OUTPUT_DIR, f"source_runs_{stamp}.csv")
    stats_path = os.path.join(OUTPUT_DIR, f"stats_{stamp}.json")

    with open(leads_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        for job in jobs:
            writer.writerow(job_to_row(job))

    with open(review_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(REVIEW_HEADERS)
        for job in review_jobs:
            writer.writerow(review_to_row(job))

    with open(runs_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["run_time", "source", "jobs_returned", "status", "message", "duration_ms"])
        writer.writeheader()
        writer.writerows(source_runs)

    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    return leads_path, review_path, runs_path, stats_path


def connect_gsheet():
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
    service_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not sheet_id or not service_json or not gspread or not Credentials:
        return None

    info = json.loads(service_json)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id)


def ensure_worksheet(spreadsheet, name: str, headers: List[str]):
    try:
        ws = spreadsheet.worksheet(name)
    except Exception:
        ws = spreadsheet.add_worksheet(title=name, rows=1000, cols=len(headers) + 5)
        ws.append_row(headers)
    values = ws.row_values(1)
    if values[: len(headers)] != headers:
        ws.clear()
        ws.append_row(headers)
    return ws


def existing_sheet_urls(ws) -> set:
    try:
        values = ws.col_values(5)
        return {normalize_url(v) for v in values[1:] if v}
    except Exception:
        return set()


def write_google_sheet(jobs: List[Job], review_jobs: List[Job], source_runs: List[Dict[str, Any]], stats: Dict[str, int]) -> int:
    spreadsheet = connect_gsheet()
    if not spreadsheet:
        return 0

    leads_ws = ensure_worksheet(spreadsheet, "Global Leads", HEADERS)
    review_ws = ensure_worksheet(spreadsheet, "Review Queue", REVIEW_HEADERS)
    runs_ws = ensure_worksheet(
        spreadsheet,
        "Source Health",
        ["Run Time", "Source", "Jobs Returned", "Status", "Message", "Duration MS"],
    )
    stats_ws = ensure_worksheet(
        spreadsheet,
        "Run Stats",
        ["Run Time", "Raw", "Tech", "Global OK", "Bangladesh OK", "Needs Verification", "Country Restricted", "Not Tech", "Deduped", "Broken Link", "Review Queue", "Final Added"],
    )

    existing = existing_sheet_urls(leads_ws)
    rows = []
    for job in jobs:
        if normalize_url(job.job_url) in existing:
            continue
        rows.append(job_to_row(job))
        existing.add(normalize_url(job.job_url))

    if rows:
        leads_ws.append_rows(rows, value_input_option="USER_ENTERED")

    if WRITE_REVIEW_QUEUE and review_jobs:
        review_existing = existing_sheet_urls(review_ws)
        review_rows = []
        for job in review_jobs:
            key = normalize_url(job.job_url)
            if key in review_existing or key in existing:
                continue
            review_rows.append(review_to_row(job))
            review_existing.add(key)
        if review_rows:
            review_ws.append_rows(review_rows, value_input_option="USER_ENTERED")

    run_rows = [
        [r["run_time"], r["source"], r["jobs_returned"], r["status"], r["message"], r["duration_ms"]]
        for r in source_runs
    ]
    if run_rows:
        runs_ws.append_rows(run_rows, value_input_option="USER_ENTERED")

    stats_ws.append_row(
        [
            datetime.now(timezone.utc).isoformat(),
            stats.get("raw", 0),
            stats.get("tech", 0),
            stats.get("global_ok", 0),
            stats.get("bangladesh_ok", 0),
            stats.get("needs_verification", 0),
            stats.get("country_restricted", 0),
            stats.get("not_tech", 0),
            stats.get("deduped", 0),
            stats.get("broken_link", 0),
            stats.get("review_queue", 0),
            len(rows),
        ],
        value_input_option="USER_ENTERED",
    )
    return len(rows)


def supabase_headers() -> Optional[Dict[str, str]]:
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not key:
        return None
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }


def upsert_supabase(jobs: List[Job], source_runs: List[Dict[str, Any]]) -> None:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    headers = supabase_headers()
    if not url or not headers:
        return

    rows = []
    for job in jobs:
        rows.append(
            {
                "job_url": normalize_url(job.job_url),
                "company_name": job.company or "Unknown",
                "company_website": job.company_website,
                "job_title": job.title,
                "remote_type": "Global Remote" if job.eligibility in {"GLOBAL_OK", "BANGLADESH_OK"} else "Remote Review",
                "location_tag": job.location or "Unknown",
                "tech_tags": (job.tags or "")[:220],
                "date_posted": safe_date(job.posted),
                "source": job.source,
                "hq_region": guess_region(job),
                "lead_status": "New Lead",
                "priority": priority(job),
                "eligibility": job.eligibility,
                "eligibility_confidence": job.eligibility_confidence,
                "eligibility_evidence": job.eligibility_evidence,
                "notes": "Proof required before outreach. Do not contact if country restricted.",
                "raw_json": job.raw,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    if rows:
        requests.post(
            f"{url}/rest/v1/leads?on_conflict=job_url",
            headers=headers,
            data=json.dumps(rows),
            timeout=REQUEST_TIMEOUT,
        )

    if source_runs:
        requests.post(
            f"{url}/rest/v1/source_runs",
            headers={**headers, "Prefer": "return=minimal"},
            data=json.dumps(source_runs),
            timeout=REQUEST_TIMEOUT,
        )


def main() -> int:
    all_jobs: List[Job] = []
    source_runs: List[Dict[str, Any]] = []

    print("Starting DSI Global Remote Lead Engine")
    print(f"Mode: {RUN_MODE}")

    for source_name, fn in build_sources():
        jobs, log = run_source(source_name, fn)
        source_runs.append(log)
        all_jobs.extend(jobs)
        print(f"{log['status']:6} {source_name:40} {log['jobs_returned']:4} jobs")
        time.sleep(0.4)

    qualified, stats, review_jobs = qualify_jobs(all_jobs)
    leads_path, review_path, runs_path, stats_path = write_csv(qualified, review_jobs, source_runs, stats)

    sheet_added = 0
    try:
        sheet_added = write_google_sheet(qualified, review_jobs, source_runs, stats)
    except Exception as exc:
        print(f"Google Sheet write failed: {exc}", file=sys.stderr)

    try:
        upsert_supabase(qualified, source_runs)
    except Exception as exc:
        print(f"Supabase write failed: {exc}", file=sys.stderr)

    print("\nRun complete")
    print(json.dumps(stats, indent=2))
    print(f"Qualified rows in CSV: {len(qualified)}")
    print(f"Review queue rows in CSV: {len(review_jobs)}")
    print(f"New rows added to Google Sheet: {sheet_added}")
    print(f"CSV: {leads_path}")
    print(f"Review queue: {review_path}")
    print(f"Source logs: {runs_path}")
    print(f"Stats: {stats_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
