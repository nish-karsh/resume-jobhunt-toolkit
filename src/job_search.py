"""Search open jobs from free, legal sources and normalise them to JobPosting.

Sources (no LinkedIn/Naukri scraping - that violates their ToS):
- Adzuna     free API key (ADZUNA_APP_ID / ADZUNA_APP_KEY), country-specific (India: 'in').
- Remotive   keyless public API for remote jobs (attribution required by their ToS).
- Greenhouse public company job boards (boards-api.greenhouse.io) - no auth.
- Lever      public company postings (api.lever.co) - no auth.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from src.schemas import JobPosting, MasterProfile
from src.settings_loader import load_settings

_TIMEOUT = 15
_HEADERS = {"User-Agent": "Resume-Automate/1.0 (personal job search)"}
_TAG_RE = re.compile(r"<[^>]+>")


class JobSearchError(Exception):
    """Raised when a source is misconfigured (e.g. missing Adzuna keys)."""


def _get_json(url: str, params: Optional[dict[str, Any]] = None) -> Any:
    resp = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text or "").replace("&amp;", "&").strip()


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#]+", (text or "").lower()))


def _ms_to_date(value: Any) -> str:
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return ""


def _adzuna_salary(record: dict[str, Any]) -> str:
    lo, hi = record.get("salary_min"), record.get("salary_max")
    if lo and hi:
        return f"{int(lo):,} - {int(hi):,}"
    if lo:
        return f"{int(lo):,}+"
    return ""


# ---------------------------------------------------------------------------
# Source adapters
# ---------------------------------------------------------------------------


def search_adzuna(
    query: str, location: str, settings: dict[str, Any], limit: int = 25
) -> list[JobPosting]:
    app_id = os.environ.get("ADZUNA_APP_ID", "")
    app_key = os.environ.get("ADZUNA_APP_KEY", "")
    if not (app_id and app_key):
        raise JobSearchError(
            "Adzuna needs ADZUNA_APP_ID and ADZUNA_APP_KEY (free at developer.adzuna.com)."
        )
    js = settings.get("job_search", {})
    country = js.get("adzuna_country", "in")
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    params: dict[str, Any] = {
        "app_id": app_id,
        "app_key": app_key,
        "what": query,
        "results_per_page": min(limit, 50),
        "content-type": "application/json",
    }
    if location:
        params["where"] = location
    if js.get("max_days_old"):
        params["max_days_old"] = js["max_days_old"]

    data = _get_json(url, params)
    postings: list[JobPosting] = []
    for record in data.get("results", []):
        postings.append(
            JobPosting(
                source="adzuna",
                external_id=str(record.get("id", "")),
                title=record.get("title", ""),
                company=(record.get("company") or {}).get("display_name", ""),
                location=(record.get("location") or {}).get("display_name", ""),
                url=record.get("redirect_url", ""),
                description=_strip_html(record.get("description", "")),
                posted_at=(record.get("created", "") or "")[:10],
                salary=_adzuna_salary(record),
            )
        )
    return postings


def search_remotive(query: str, limit: int = 25) -> list[JobPosting]:
    data = _get_json(
        "https://remotive.com/api/remote-jobs", {"search": query, "limit": limit}
    )
    postings: list[JobPosting] = []
    for record in data.get("jobs", []):
        postings.append(
            JobPosting(
                source="remotive",
                external_id=str(record.get("id", "")),
                title=record.get("title", ""),
                company=record.get("company_name", ""),
                location=record.get("candidate_required_location", "Remote"),
                remote=True,
                url=record.get("url", ""),
                description=_strip_html(record.get("description", ""))[:4000],
                posted_at=(record.get("publication_date", "") or "")[:10],
                salary=record.get("salary", "") or "",
                tags=list(record.get("tags", [])),
            )
        )
    return postings


def fetch_greenhouse(board_token: str, limit: int = 0) -> list[JobPosting]:
    data = _get_json(
        f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
    )
    postings: list[JobPosting] = []
    for record in data.get("jobs", []):
        postings.append(
            JobPosting(
                source="greenhouse",
                external_id=str(record.get("id", "")),
                title=record.get("title", ""),
                company=board_token,
                location=(record.get("location") or {}).get("name", ""),
                url=record.get("absolute_url", ""),
                posted_at=(record.get("updated_at", "") or "")[:10],
            )
        )
    return postings


def fetch_lever(company: str, limit: int = 0) -> list[JobPosting]:
    data = _get_json(f"https://api.lever.co/v0/postings/{company}", {"mode": "json"})
    postings: list[JobPosting] = []
    for record in data if isinstance(data, list) else []:
        categories = record.get("categories") or {}
        tags = [categories.get("team", ""), categories.get("commitment", "")]
        postings.append(
            JobPosting(
                source="lever",
                external_id=str(record.get("id", "")),
                title=record.get("text", ""),
                company=company,
                location=categories.get("location", ""),
                url=record.get("hostedUrl", ""),
                description=_strip_html(
                    record.get("descriptionPlain") or record.get("description", "")
                )[:4000],
                posted_at=_ms_to_date(record.get("createdAt")),
                tags=[t for t in tags if t],
            )
        )
    return postings


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _relevance(posting: JobPosting, terms: set[str]) -> float:
    if not terms:
        return 0.0
    title = _tokenize(posting.title)
    tags = _tokenize(" ".join(posting.tags))
    desc = _tokenize(posting.description)
    score = 0.0
    for term in terms:
        if term in title:
            score += 3.0
        elif term in tags:
            score += 2.0
        elif term in desc:
            score += 1.0
    return score


def search_jobs(
    query: Optional[str] = None,
    location: Optional[str] = None,
    settings: Optional[dict[str, Any]] = None,
    sources: Optional[list[str]] = None,
    profile: Optional[MasterProfile] = None,
) -> tuple[list[JobPosting], list[str]]:
    """Search enabled sources, dedupe, score, and sort. Returns (postings, warnings)."""
    cfg = settings or load_settings()
    js = cfg.get("job_search", {})
    enabled = sources if sources is not None else js.get("enabled_sources", ["adzuna", "remotive"])
    limit = int(js.get("results_per_source", 25))
    if location is None:
        location = js.get("default_location", "")

    queries = [query] if query else list(js.get("default_queries", []))
    queries = [q for q in queries if q] or [""]

    terms: set[str] = set()
    for q in queries:
        terms |= _tokenize(q)
    if profile:
        for items in profile.skills.values():
            for skill in items:
                terms |= _tokenize(skill)

    warnings: list[str] = []
    postings: list[JobPosting] = []

    def run(label: str, fn, *args, **kwargs) -> list[JobPosting]:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - one bad source shouldn't kill the search
            warnings.append(f"{label}: {exc}")
            return []

    for q in queries:
        if "adzuna" in enabled:
            postings += run("adzuna", search_adzuna, q, location, cfg, limit)
        if "remotive" in enabled:
            postings += run("remotive", search_remotive, q, limit)

    boards = js.get("company_boards", {}) or {}
    if "greenhouse" in enabled:
        for token in boards.get("greenhouse", []) or []:
            postings += run(f"greenhouse:{token}", fetch_greenhouse, token)
    if "lever" in enabled:
        for company in boards.get("lever", []) or []:
            postings += run(f"lever:{company}", fetch_lever, company)

    deduped: dict[str, JobPosting] = {}
    for posting in postings:
        if posting.title and posting.url:
            deduped.setdefault(posting.uid, posting)

    results: list[JobPosting] = []
    for posting in deduped.values():
        posting.score = _relevance(posting, terms)
        # Company boards list every role; keep only ones matching the search terms.
        if posting.source in ("greenhouse", "lever") and terms and posting.score == 0:
            continue
        results.append(posting)

    results.sort(key=lambda p: p.score, reverse=True)
    return results, warnings
