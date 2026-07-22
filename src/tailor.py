"""Tailor a MasterProfile to a JobDescription with strict no-fabrication guardrails.

The model never sees a free-form "reproduce the whole resume" task (which used to
truncate and drop everything but the summary). Instead, experience and projects are
sent as INDEXED lists and the model only returns, per index, tailored bullets plus a
summary and a skills regrouping. All facts (company, title, dates, project names,
tech, education, identity) are frozen by the system from the source profile.
"""

from __future__ import annotations

import difflib
import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

from src.nim_client import NimClient, NimClientError
from src.schemas import (
    ExperienceEntry,
    JobDescription,
    MasterProfile,
    ProjectEntry,
    TailoredResume,
    TailoredResumeMeta,
)

_TAILOR_UNAVAILABLE = (
    "NVIDIA NIM is unreachable and tailoring requires an online model. "
    "Use the offline variant library (variant_library.py) or check your API key and network."
)

_SYSTEM_PROMPT = """You are an expert technical resume writer. You tailor a candidate's \
resume to one specific job. You receive the target job and the candidate's master profile. \
The experience and projects are given as INDEXED lists.

Do all of this:
1. SUMMARY: write a sharp 2-3 sentence professional summary aimed at THIS role. Lead with the \
candidate's most relevant real experience and the core theme of the job. Truthful facts only.
2. EXPERIENCE: for each entry (referenced by its integer "index"), rewrite its existing bullets so they
   - start with a strong action verb and emphasise impact / outcome,
   - naturally use the job's keywords ONLY where they are already true for that bullet,
   - stay faithful to the original bullet's meaning. You may rephrase, sharpen and reorder, \
but you must NOT invent new employers, tools, technologies, metrics, or responsibilities.
   Return a similar number of bullets to the source.
3. PROJECTS: same treatment, per "index".
4. SKILLS: regroup the candidate's EXISTING skills so the ones most relevant to this job come first. \
Do NOT add any skill that is not already present in the profile.

STRICT RULES (violations are rejected by an automatic checker):
- NO FABRICATION. Only rephrase content that already exists in the profile.
- Never output a company, title, date, project name, or tech stack change - those are frozen anyway.
- Every experience/project object MUST include the integer "index" it refers to.

Respond with a SINGLE valid JSON object ONLY. No markdown fences, no commentary, no analysis. Shape:
{
  "summary": "string",
  "skills": {"Category": ["existing skill", "..."]},
  "experience": [{"index": 0, "bullets": ["tailored bullet", "..."]}],
  "projects": [{"index": 0, "bullets": ["tailored bullet", "..."]}]
}"""


class TailorError(Exception):
    """Raised when tailoring cannot complete (e.g. NIM offline)."""


def _normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text)


def _bullet_overlap(a: str, b: str) -> float:
    na, nb = _normalize_text(a), _normalize_text(b)
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return 1.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _all_profile_skills(profile: MasterProfile) -> dict[str, str]:
    """Map lowercase skill -> canonical form from profile."""
    mapping: dict[str, str] = {}
    for items in profile.skills.values():
        for skill in items:
            mapping[skill.lower().strip()] = skill.strip()
    return mapping


def _match_keywords(resume_text: str, jd_keywords: list[str]) -> tuple[list[str], list[str]]:
    text_lower = resume_text.lower()
    matched: list[str] = []
    missing: list[str] = []
    for kw in jd_keywords:
        k = kw.lower().strip()
        if not k:
            continue
        compact = re.sub(r"[\s\-_/]+", "", k)
        text_compact = re.sub(r"[\s\-_/]+", "", text_lower)
        if k in text_lower or (compact and compact in text_compact):
            matched.append(kw)
        else:
            missing.append(kw)
    return matched, missing


def _validate_bullets(
    raw_bullets: list[Any],
    source_bullets: list[str],
    keep_rephrase: float = 0.4,
    min_related: float = 0.2,
) -> list[str]:
    """Validate model bullets against this entry's own source bullets only.

    - A model bullet close to a source bullet is kept as-is (a faithful rephrase).
    - A weakly-related bullet is replaced by its closest source bullet (anti-fabrication).
    - An unrelated bullet is dropped.
    Scoping to the entry's own bullets prevents content from one role/project leaking
    into another. Order and de-duplication are preserved.
    """
    candidates = list(source_bullets)

    result: list[str] = []
    for raw in raw_bullets:
        text = str(raw).strip()
        if not text:
            continue
        best_score = 0.0
        best_source = ""
        for src in candidates:
            score = _bullet_overlap(text, src)
            if score > best_score:
                best_score = score
                best_source = src
        if best_score >= keep_rephrase:
            chosen = text
        elif best_score >= min_related and best_source:
            chosen = best_source
        else:
            continue
        if chosen not in result:
            result.append(chosen)
    return result


def _sanitize_skills(
    proposed: dict[str, list[str]],
    profile: MasterProfile,
) -> dict[str, list[str]]:
    allowed = _all_profile_skills(profile)
    if not allowed:
        return {k: list(v) for k, v in profile.skills.items()}

    sanitized: dict[str, list[str]] = {}
    used: set[str] = set()
    for category, items in proposed.items():
        kept: list[str] = []
        for item in items:
            canonical = allowed.get(str(item).lower().strip())
            if canonical and canonical not in used:
                kept.append(canonical)
                used.add(canonical)
        if kept:
            sanitized[str(category)] = kept

    # Append any profile skills not yet included (preserves completeness).
    for category, items in profile.skills.items():
        for skill in items:
            if skill not in used:
                sanitized.setdefault(category, []).append(skill)
                used.add(skill)

    return sanitized


def _enforce_structure(
    profile: MasterProfile,
    generated: dict[str, Any],
) -> TailoredResume:
    """Apply no-fabrication guardrail: freeze facts by index, validate bullets.

    Every source experience/project entry is always emitted (never dropped); only the
    bullet wording is allowed to change, and only when it stays faithful to the source.
    """
    gen_exp_by_index: dict[int, list[Any]] = {}
    for gen_exp in generated.get("experience", []):
        if not isinstance(gen_exp, dict):
            continue
        try:
            idx = int(gen_exp.get("index"))
        except (TypeError, ValueError):
            continue
        gen_exp_by_index[idx] = list(gen_exp.get("bullets", []))

    experience: list[ExperienceEntry] = []
    for i, source in enumerate(profile.experience):
        validated = _validate_bullets(gen_exp_by_index.get(i, []), source.bullets)
        if not validated:
            validated = list(source.bullets)
        experience.append(
            ExperienceEntry(
                company=source.company,
                title=source.title,
                location=source.location,
                start=source.start,
                end=source.end,
                bullets=validated,
            )
        )

    gen_proj_by_index: dict[int, list[Any]] = {}
    for gen_proj in generated.get("projects", []):
        if not isinstance(gen_proj, dict):
            continue
        try:
            idx = int(gen_proj.get("index"))
        except (TypeError, ValueError):
            continue
        gen_proj_by_index[idx] = list(gen_proj.get("bullets", []))

    projects: list[ProjectEntry] = []
    for i, source in enumerate(profile.projects):
        validated = _validate_bullets(gen_proj_by_index.get(i, []), source.bullets)
        if not validated:
            validated = list(source.bullets)
        projects.append(
            ProjectEntry(
                name=source.name,
                link=source.link,
                tech=list(source.tech),
                bullets=validated,
            )
        )

    skills = _sanitize_skills(
        generated.get("skills", {}) if isinstance(generated.get("skills"), dict) else {},
        profile,
    )
    summary = str(generated.get("summary", "")).strip() or profile.summary

    return TailoredResume(
        identity=profile.identity,
        summary=summary,
        skills=skills,
        experience=experience,
        projects=projects,
        education=list(profile.education),
        certifications=list(profile.certifications),
        achievements=list(profile.achievements),
        bullet_bank=list(profile.bullet_bank),
        meta=TailoredResumeMeta(),
    )


def _build_user_prompt(
    profile: MasterProfile,
    jd: JobDescription,
    research: Optional[dict[str, Any]],
) -> str:
    payload: dict[str, Any] = {
        "target_job": {
            "title": jd.title,
            "company": jd.company,
            "location": jd.location,
            "seniority": jd.seniority,
            "requirements": jd.requirements[:20],
            "keywords": jd.keywords[:40],
        },
        "current_summary": profile.summary,
        "skills": profile.skills,
        "experience": [
            {
                "index": i,
                "company": e.company,
                "title": e.title,
                "bullets": list(e.bullets),
            }
            for i, e in enumerate(profile.experience)
        ],
        "projects": [
            {
                "index": i,
                "name": p.name,
                "tech": list(p.tech),
                "bullets": list(p.bullets),
            }
            for i, p in enumerate(profile.projects)
        ],
        "education": [e.to_dict() for e in profile.education],
        "certifications": profile.certifications,
    }
    if research:
        payload["company_research"] = research
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _tailor_model_chain(client: NimClient) -> list[str]:
    """Preferred tailoring model first (a reliable instruct model), then fallbacks."""
    tailor_model = client.settings.get("models", {}).get("tailor", "")
    chain: list[str] = []
    for model in [tailor_model, *client.model_chain]:
        if model and model not in chain:
            chain.append(model)
    return chain


def _tailor_with_nim(
    profile: MasterProfile,
    jd: JobDescription,
    research: Optional[dict[str, Any]],
    client: NimClient,
) -> tuple[dict[str, Any], str]:
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(profile, jd, research)},
    ]
    last_error: Exception | None = None
    for model in _tailor_model_chain(client):
        try:
            data = client.chat_json(
                messages, model=model, max_tokens=8000, temperature=0.35
            )
            if isinstance(data, dict) and (
                data.get("experience") or data.get("summary")
            ):
                return data, model
            last_error = ValueError("empty tailoring response")
        except (NimClientError, ValueError) as exc:
            last_error = exc
            continue
    raise NimClientError(f"Tailoring failed across models: {last_error}")


def tailor_resume(
    profile: MasterProfile,
    jd: JobDescription,
    research: Optional[dict[str, Any]] = None,
) -> TailoredResume:
    """Select/rephrase profile content for a job; never fabricate facts."""
    try:
        client = NimClient()
        if not client.is_reachable():
            raise TailorError(_TAILOR_UNAVAILABLE)
    except NimClientError as exc:
        raise TailorError(str(exc)) from exc

    try:
        generated, model_used = _tailor_with_nim(profile, jd, research, client)
    except NimClientError as exc:
        raise TailorError(_TAILOR_UNAVAILABLE) from exc

    tailored = _enforce_structure(profile, generated)

    resume_text_parts = [tailored.summary]
    for cat, items in tailored.skills.items():
        resume_text_parts.extend(items)
    for exp in tailored.experience:
        resume_text_parts.extend(exp.bullets)
    for proj in tailored.projects:
        resume_text_parts.extend(proj.bullets)
    resume_text = "\n".join(resume_text_parts)

    matched, missing = _match_keywords(resume_text, jd.keywords)
    tailored.meta = TailoredResumeMeta(
        job_title=jd.title,
        company=jd.company,
        jd_keywords=list(jd.keywords),
        matched_keywords=matched,
        missing_keywords=missing,
        model_used=model_used,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    return tailored

    return tailored
