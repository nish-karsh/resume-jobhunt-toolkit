"""Best-effort company/role research to inform resume tailoring."""

from __future__ import annotations

import re
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup

from src.nim_client import NimClient, NimClientError
from src.schemas import JobDescription

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_FETCH_TIMEOUT = 12

_EMPTY_RESULT: dict[str, Any] = {
    "company_summary": "",
    "tech_stack": [],
    "values_keywords": [],
    "notes": "",
}


def _quick_web_snippet(company: str) -> str:
    """Fetch a short public snippet about the company (best-effort)."""
    if not company.strip():
        return ""
    query = re.sub(r"\s+", "+", company.strip())
    url = f"https://duckduckgo.com/html/?q={query}+semiconductor+company"
    try:
        response = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=_FETCH_TIMEOUT,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        snippets: list[str] = []
        for result in soup.select(".result__snippet")[:3]:
            text = result.get_text(separator=" ", strip=True)
            if text:
                snippets.append(text)
        return " ".join(snippets)[:1500]
    except Exception:
        return ""


def _research_with_nim(
    company: str,
    role: str,
    jd_text: str,
    web_snippet: str,
    client: NimClient,
) -> dict[str, Any]:
    schema = (
        '{"company_summary":"1-2 sentences","tech_stack":["..."],'
        '"values_keywords":["..."], "notes":"brief tailoring hints"}'
    )
    context_parts = [f"Company: {company}", f"Role: {role}"]
    if jd_text:
        context_parts.append(f"Job description excerpt:\n{jd_text[:4000]}")
    if web_snippet:
        context_parts.append(f"Web snippet:\n{web_snippet}")

    messages = [
        {
            "role": "system",
            "content": (
                "Summarize what the company likely does and its probable tech stack "
                "for a job applicant. Keep answers short and factual; say unknown "
                "rather than inventing specifics."
            ),
        },
        {"role": "user", "content": "\n\n".join(context_parts)},
    ]
    utility = client.settings.get("models", {}).get("utility", "")
    data = client.chat_json(
        messages,
        schema_hint=schema,
        model=utility or None,
        max_tokens=1024,
    )
    return {
        "company_summary": str(data.get("company_summary", "")).strip(),
        "tech_stack": [
            str(t).strip() for t in data.get("tech_stack", []) if str(t).strip()
        ],
        "values_keywords": [
            str(v).strip()
            for v in data.get("values_keywords", [])
            if str(v).strip()
        ],
        "notes": str(data.get("notes", "")).strip(),
    }


def research(
    company: str,
    role: str = "",
    jd: Optional[JobDescription] = None,
) -> dict[str, Any]:
    """Return short company/role notes for tailoring, or empty dict when offline."""
    company = (company or "").strip()
    role = (role or "").strip()
    jd_text = ""
    if jd is not None:
        if not company:
            company = jd.company
        if not role:
            role = jd.title
        jd_text = jd.raw_text

    if not company and not role:
        return dict(_EMPTY_RESULT)

    try:
        client = NimClient()
        if not client.is_reachable():
            return dict(_EMPTY_RESULT)
    except NimClientError:
        return dict(_EMPTY_RESULT)

    web_snippet = _quick_web_snippet(company) if company else ""
    try:
        return _research_with_nim(company, role, jd_text, web_snippet, client)
    except (NimClientError, ValueError, KeyError):
        return dict(_EMPTY_RESULT)
