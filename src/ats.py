"""ATS keyword-gap scoring and formatting heuristics."""

from __future__ import annotations

import re
from typing import Union

from src.schemas import AtsReport, JobDescription, TailoredResume

_ACTION_VERBS = frozenset(
    """
    developed designed implemented built created led managed optimized improved
    automated engineered delivered architected analyzed reduced increased
    collaborated coordinated deployed maintained tested debugged validated verified
    authored wrote established streamlined enhanced accelerated
    """.split()
)

_PROBLEMATIC_CHARS_RE = re.compile(r"[\u200b\u200c\u200d\ufeff\u00a0]|🔗|→|←|★|●|■")
_SECTION_HEADERS = (
    "experience",
    "education",
    "skills",
    "projects",
    "summary",
    "certifications",
)


def _resume_text(tailored_or_text: Union[TailoredResume, str]) -> str:
    if isinstance(tailored_or_text, str):
        return tailored_or_text

    parts: list[str] = []
    tr = tailored_or_text
    ident = tr.identity
    if ident.name:
        parts.append(ident.name)
    if ident.email:
        parts.append(ident.email)
    if ident.phone:
        parts.append(ident.phone)
    if tr.summary:
        parts.append(tr.summary)
    for category, items in tr.skills.items():
        parts.append(category)
        parts.extend(items)
    for exp in tr.experience:
        parts.extend([exp.company, exp.title, exp.start, exp.end, *exp.bullets])
    for proj in tr.projects:
        parts.extend([proj.name, *proj.tech, *proj.bullets])
    for edu in tr.education:
        parts.extend([edu.institution, edu.degree, edu.field])
    parts.extend(tr.certifications)
    parts.extend(tr.achievements)
    return "\n".join(p for p in parts if p)


def _keyword_in_text(keyword: str, text_lower: str) -> bool:
    kw = keyword.lower().strip()
    if not kw:
        return False
    if kw in text_lower:
        return True
    # Allow minor spacing variants (e.g. "system verilog" vs "systemverilog")
    compact = re.sub(r"[\s\-_/]+", "", kw)
    text_compact = re.sub(r"[\s\-_/]+", "", text_lower)
    if compact and compact in text_compact:
        return True
    # Multi-word: all tokens present
    tokens = [t for t in re.split(r"[\s\-_/]+", kw) if len(t) > 2]
    if len(tokens) > 1 and all(t in text_lower for t in tokens):
        return True
    return False


def _classify_keywords(jd: JobDescription) -> tuple[list[str], list[str]]:
    """Split JD keywords into must-have (higher weight) and nice-to-have."""
    must_have: list[str] = []
    nice: list[str] = list(jd.keywords)

    must_patterns = re.compile(
        r"\b(must|required|mandatory|essential|need(?:s)? to have)\b", re.I
    )
    for req in jd.requirements:
        if must_patterns.search(req):
            tokens = re.findall(r"[a-z0-9+#./-]{3,}", req.lower())
            for tok in tokens:
                if tok not in must_have:
                    must_have.append(tok)

    # Promote VLSI-critical terms found in requirements to must-have
    critical = {
        "uvm", "systemverilog", "verilog", "vcs", "dv", "verification",
        "emulation", "zebu", "sta", "rtl", "fpga", "asic", "soc",
    }
    for kw in jd.keywords:
        if kw.lower() in critical and kw.lower() not in must_have:
            must_have.append(kw.lower())

    must_set = {k.lower() for k in must_have}
    nice = [k for k in nice if k.lower() not in must_set]
    return must_have, nice


def _format_checks(text: str, tailored_or_text: Union[TailoredResume, str]) -> tuple[list[str], list[str], int]:
    """Return (warnings, suggestions, bonus_points 0-20)."""
    warnings: list[str] = []
    suggestions: list[str] = []
    bonus = 0
    text_lower = text.lower()

    has_email = bool(re.search(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", text, re.I))
    has_phone = bool(re.search(r"\+?\d[\d\s().-]{7,}\d", text))
    if not has_email:
        warnings.append("Missing email address in resume text.")
        suggestions.append("Add a professional email in the contact header.")
    else:
        bonus += 3
    if not has_phone:
        warnings.append("Missing phone number in resume text.")
    else:
        bonus += 2

    present_sections = sum(1 for h in _SECTION_HEADERS if h in text_lower)
    if present_sections < 3:
        warnings.append("Few standard resume sections detected.")
        suggestions.append(
            "Use clear section headers: Summary, Skills, Experience, Education."
        )
    else:
        bonus += min(5, present_sections)

    action_count = sum(
        1 for verb in _ACTION_VERBS if re.search(rf"\b{verb}\b", text_lower)
    )
    if action_count < 3:
        suggestions.append("Start more bullets with strong action verbs (developed, led, optimized).")
    else:
        bonus += min(4, action_count)

    has_metrics = bool(re.search(r"\d+\s*%|\d+\s*x|\b\d{2,}\b", text))
    if not has_metrics:
        suggestions.append("Add quantified outcomes where possible (%, x speedup, team size).")
    else:
        bonus += 3

    word_count = len(text.split())
    if word_count < 150:
        warnings.append("Resume may be too short for ATS parsing.")
    elif word_count > 1200:
        warnings.append("Resume may be too long; consider trimming to one page.")
    else:
        bonus += 3

    if _PROBLEMATIC_CHARS_RE.search(text):
        warnings.append("Contains symbols or invisible characters that may confuse ATS parsers.")
        suggestions.append("Remove emoji, special bullets, and zero-width characters.")

    if isinstance(tailored_or_text, TailoredResume):
        if tailored_or_text.meta.missing_keywords:
            top_missing = tailored_or_text.meta.missing_keywords[:5]
            suggestions.append(
                f"Tailoring gap: consider echoing JD terms where truthful — {', '.join(top_missing)}."
            )

    return warnings, suggestions, min(20, bonus)


def ats_report(
    tailored_or_text: Union[TailoredResume, str],
    jd: JobDescription,
) -> AtsReport:
    """Score resume against JD keywords plus formatting heuristics."""
    text = _resume_text(tailored_or_text)
    text_lower = text.lower()

    must_have, nice_to_have = _classify_keywords(jd)
    all_keywords = must_have + nice_to_have
    if not all_keywords:
        all_keywords = _classify_keywords(
            JobDescription(
                raw_text=jd.raw_text,
                keywords=_extract_fallback_keywords(jd.raw_text),
            )
        )[0]
        must_have, nice_to_have = all_keywords[:10], all_keywords[10:]

    matched: list[str] = []
    missing: list[str] = []

    for kw in must_have:
        if _keyword_in_text(kw, text_lower):
            matched.append(kw)
        else:
            missing.append(kw)

    for kw in nice_to_have:
        if _keyword_in_text(kw, text_lower):
            if kw not in matched:
                matched.append(kw)
        else:
            if kw not in missing:
                missing.append(kw)

    must_matched = sum(1 for kw in must_have if _keyword_in_text(kw, text_lower))
    nice_matched = sum(1 for kw in nice_to_have if _keyword_in_text(kw, text_lower))

    must_total = max(len(must_have), 1)
    nice_total = max(len(nice_to_have), 1)
    keyword_score = (
        (must_matched / must_total) * 70.0 + (nice_matched / nice_total) * 30.0
    )

    format_warnings, suggestions, format_bonus = _format_checks(text, tailored_or_text)
    score = int(round(min(100.0, keyword_score * 0.80 + format_bonus)))

    if missing[:8]:
        suggestions.append(
            "Missing JD keywords to weave in (only if truthful): "
            + ", ".join(missing[:8])
        )

    return AtsReport(
        score=max(0, min(100, score)),
        matched=matched,
        missing=missing,
        format_warnings=format_warnings,
        suggestions=suggestions,
    )


def _extract_fallback_keywords(text: str) -> list[str]:
    tokens = re.findall(r"[a-z][a-z0-9+#./-]{2,}", text.lower())
    stop = {"the", "and", "for", "with", "you", "our", "will", "have", "this"}
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        if t not in stop and t not in seen:
            seen.add(t)
            out.append(t)
    return out[:30]
