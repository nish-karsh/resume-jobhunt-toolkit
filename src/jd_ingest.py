"""Ingest job descriptions from pasted text or URLs."""

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
_FETCH_TIMEOUT = 20

_STOPWORDS = frozenset(
    """
    a an the and or but in on at to for of with by from as is are was were be been
    being have has had do does did will would shall should may might must can could
    this that these those it its we you they he she i our your their not no nor
    all any each every both few more most other some such than too very just also
    about into over after before between through during while when where who whom
    which what how why if then than so up out off down only own same both own
    job role work team company experience years year required preferred plus ability
    responsibilities qualifications skills including using used use well strong good
    excellent great looking seek seeking join opportunity position candidate candidates
    apply application applications description details role-based role-based
    """.split()
)

_VLSI_KEYWORDS = frozenset(
    """
    uvm systemverilog verilog vcs questa modelsim cocotb python perl tcl c++ c
    rtl dv design verification asic fpga soc emulation zebu palladium veloce
    sta static timing synthesis physical design dft atpg scan coverage assertion
    formal ovm sv dpi vip transactor testbench regression lint cdc rdc low power
    arm axi amba apb ahb pcie ddr usb uart spi i2c jtag synopsys cadence mentor
    xilinx vivado quartus matlab simulink embedded firmware rtos stm32 esp32
    """.split()
)

_SENIORITY_PATTERNS = [
    (re.compile(r"\b(intern|internship)\b", re.I), "Intern"),
    (re.compile(r"\b(entry[\s-]?level|fresher|graduate)\b", re.I), "Entry"),
    (re.compile(r"\b(junior|jr\.?)\b", re.I), "Junior"),
    (re.compile(r"\b(senior|sr\.?|lead|principal|staff|architect)\b", re.I), "Senior"),
]

_REQUIREMENT_LINE_RE = re.compile(
    r"^[\s\u2022\u25cf\u25cb\u25aa\-\*●•\d]+[\.\)]\s*(.+)$", re.M
)


class JdIngestError(Exception):
    """Raised when JD cannot be obtained (e.g. blocked URL scrape)."""


def _fetch_url_text(url: str) -> str:
    """Best-effort fetch of visible page text from a job posting URL."""
    try:
        response = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
            timeout=_FETCH_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise JdIngestError(
            f"Could not fetch job URL ({url}): {exc}. "
            "Many sites (LinkedIn, Naukri, etc.) block automated access. "
            "Please copy the full job description text and paste it instead."
        ) from exc

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript", "svg"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    text = "\n".join(lines)

    if len(text) < 80:
        raise JdIngestError(
            "Fetched page contained very little text (likely login wall or bot block). "
            "Please paste the full job description text instead."
        )
    return text


def _guess_seniority(text: str) -> str:
    for pattern, label in _SENIORITY_PATTERNS:
        if pattern.search(text):
            return label
    return ""


def _guess_title(text: str) -> str:
    for line in text.splitlines()[:8]:
        line = line.strip()
        if 5 < len(line) < 120 and not line.lower().startswith(("http", "www.")):
            if re.search(r"(engineer|developer|designer|architect|analyst|manager|intern|verification|dv|rtl)", line, re.I):
                return line
    return ""


def _guess_company(text: str) -> str:
    for pattern in (
        r"(?:company|employer|organization)\s*[:\-]\s*(.+)",
        r"(?:at|@)\s+([A-Z][A-Za-z0-9&.\- ]{2,60})",
    ):
        match = re.search(pattern, text[:2000], re.I)
        if match:
            return match.group(1).strip().rstrip(".")
    return ""


def _guess_location(text: str) -> str:
    match = re.search(
        r"(?:location|based in|work location)\s*[:\-]\s*(.+)",
        text[:3000],
        re.I,
    )
    if match:
        return match.group(1).strip().split("\n")[0][:120]
    return ""


def _extract_requirements_heuristic(text: str) -> list[str]:
    reqs: list[str] = []
    in_section = False
    section_headers = (
        "requirements",
        "qualifications",
        "what you need",
        "what we're looking",
        "must have",
        "skills required",
        "key responsibilities",
        "responsibilities",
    )
    for line in text.splitlines():
        lower = line.lower().strip()
        if any(h in lower for h in section_headers) and len(lower) < 80:
            in_section = True
            continue
        if in_section and lower and (
            lower.startswith(("about", "benefits", "perks", "how to apply", "equal opportunity"))
            and len(lower) < 60
        ):
            break
        bullet_match = _REQUIREMENT_LINE_RE.match(line.strip())
        if bullet_match:
            reqs.append(bullet_match.group(1).strip())
        elif in_section and 20 < len(line.strip()) < 300:
            reqs.append(line.strip())
    return reqs[:25]


def _extract_keywords_heuristic(text: str, requirements: list[str]) -> list[str]:
    combined = (text + "\n" + "\n".join(requirements)).lower()
    tokens = re.findall(r"[a-z][a-z0-9+#./-]{1,30}", combined)
    seen: set[str] = set()
    keywords: list[str] = []

    for token in tokens:
        if token in _STOPWORDS or len(token) < 2:
            continue
        if token in _VLSI_KEYWORDS and token not in seen:
            seen.add(token)
            keywords.append(token)

    for token in tokens:
        if token in _STOPWORDS or len(token) < 3:
            continue
        if token not in seen and token.isalpha() and len(token) >= 4:
            seen.add(token)
            keywords.append(token)

    return keywords[:40]


def _extract_with_nim(text: str, client: NimClient) -> dict[str, Any]:
    settings = client.settings
    utility = settings.get("models", {}).get("utility", "")
    schema = (
        '{"title":"","company":"","location":"","seniority":"",'
        '"requirements":["..."],"keywords":["..."]}'
    )
    messages = [
        {
            "role": "system",
            "content": (
                "Extract structured fields from a job description. "
                "requirements: concrete must-have and nice-to-have items. "
                "keywords: ATS-relevant technical terms, tools, and skills (lowercase)."
            ),
        },
        {"role": "user", "content": text[:12000]},
    ]
    return client.chat_json(messages, schema_hint=schema, model=utility or None)


def _heuristic_extract(text: str) -> dict[str, Any]:
    requirements = _extract_requirements_heuristic(text)
    return {
        "title": _guess_title(text),
        "company": _guess_company(text),
        "location": _guess_location(text),
        "seniority": _guess_seniority(text),
        "requirements": requirements,
        "keywords": _extract_keywords_heuristic(text, requirements),
    }


def _normalize_extracted(data: dict[str, Any]) -> dict[str, Any]:
    def _str_list(key: str) -> list[str]:
        raw = data.get(key, [])
        if not isinstance(raw, list):
            return []
        return [str(item).strip() for item in raw if str(item).strip()]

    keywords = [k.lower() for k in _str_list("keywords")]
    # Deduplicate preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            deduped.append(kw)

    return {
        "title": str(data.get("title", "")).strip(),
        "company": str(data.get("company", "")).strip(),
        "location": str(data.get("location", "")).strip(),
        "seniority": str(data.get("seniority", "")).strip(),
        "requirements": _str_list("requirements"),
        "keywords": deduped[:50],
    }


def ingest_jd(
    text: Optional[str] = None,
    url: Optional[str] = None,
) -> JobDescription:
    """Build a JobDescription from pasted text and/or a job posting URL."""
    if not text and not url:
        raise ValueError("Provide either text or url (or both).")

    source_url = url or ""
    raw_text = (text or "").strip()

    if url:
        fetched = _fetch_url_text(url)
        raw_text = f"{raw_text}\n\n{fetched}".strip() if raw_text else fetched

    if not raw_text:
        raise ValueError("No job description text available after ingest.")

    extracted: dict[str, Any]
    try:
        client = NimClient()
        if client.is_reachable():
            try:
                extracted = _extract_with_nim(raw_text, client)
            except (NimClientError, ValueError, KeyError):
                extracted = _heuristic_extract(raw_text)
        else:
            extracted = _heuristic_extract(raw_text)
    except NimClientError:
        extracted = _heuristic_extract(raw_text)

    fields = _normalize_extracted(extracted)
    if not fields["keywords"]:
        fields["keywords"] = _extract_keywords_heuristic(
            raw_text, fields["requirements"]
        )

    return JobDescription(
        raw_text=raw_text,
        source_url=source_url,
        title=fields["title"],
        company=fields["company"],
        location=fields["location"],
        seniority=fields["seniority"],
        requirements=fields["requirements"],
        keywords=fields["keywords"],
    )
