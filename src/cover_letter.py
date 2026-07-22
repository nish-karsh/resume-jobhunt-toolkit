"""Generate tailored cover letters grounded in profile + JD (no fabrication)."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.nim_client import NimClient, NimClientError
from src.render_latex import compile_tex_to_pdf, escape_latex
from src.schemas import JobDescription, MasterProfile, TailoredResume
from src.settings_loader import load_settings, resolve_path

_SALUTATION_DEFAULT = "Hiring Manager"


def _jinja_env(templates_dir: Path) -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(default=False),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["latex"] = escape_latex
    return env


def _profile_context(profile: MasterProfile, tailored: TailoredResume | None) -> str:
    source = tailored or profile
    payload = {
        "name": source.identity.name,
        "summary": source.summary,
        "skills": source.skills,
        "experience": [
            {
                "company": e.company,
                "title": e.title,
                "bullets": e.bullets[:3],
            }
            for e in source.experience[:4]
        ],
        "education": [
            {"institution": e.institution, "degree": e.degree} for e in source.education[:2]
        ],
        "certifications": source.certifications[:5],
    }
    return json.dumps(payload, indent=2)


def _jd_context(jd: JobDescription) -> str:
    return json.dumps(
        {
            "title": jd.title,
            "company": jd.company,
            "location": jd.location,
            "requirements": jd.requirements[:12],
            "keywords": jd.keywords[:20],
            "raw_excerpt": jd.raw_text[:2500],
        },
        indent=2,
    )


def _parse_cover_letter_response(raw: str) -> dict[str, Any]:
    text = raw.strip()
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
    except json.JSONDecodeError:
        pass

    # Fallback: split paragraphs from plain prose
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return {
        "salutation": _SALUTATION_DEFAULT,
        "paragraphs": paragraphs or [text],
        "subject": "",
    }


def _draft_cover_letter_text(
    profile: MasterProfile,
    jd: JobDescription,
    tailored: TailoredResume | None = None,
    research: dict[str, Any] | None = None,
    client: NimClient | None = None,
) -> dict[str, Any]:
    research_blob = json.dumps(research or {}, indent=2)[:2000]
    system = (
        "You write concise, professional cover letters for job applications. "
        "Use ONLY facts from the candidate profile provided. "
        "Do NOT invent employers, degrees, skills, metrics, or projects. "
        "If the JD asks for something not in the profile, acknowledge transferable "
        "experience without claiming direct experience you cannot verify."
    )
    user = (
        f"Write a cover letter for this role.\n\n"
        f"JOB:\n{_jd_context(jd)}\n\n"
        f"CANDIDATE PROFILE:\n{_profile_context(profile, tailored)}\n\n"
        f"OPTIONAL COMPANY RESEARCH:\n{research_blob}\n\n"
        "Respond with JSON only:\n"
        '{"salutation": "Hiring Manager", "paragraphs": ["...", "...", "..."], '
        '"subject": "Application for <role> at <company>"}'
    )

    try:
        nim = client or NimClient()
        raw = nim.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            max_tokens=1200,
        )
        draft = _parse_cover_letter_response(raw)
    except (NimClientError, ValueError, json.JSONDecodeError):
        name = profile.identity.name
        role = jd.title or "the open position"
        company = jd.company or "your organization"
        draft = {
            "salutation": _SALUTATION_DEFAULT,
            "subject": f"Application for {role} at {company}",
            "paragraphs": [
                (
                    f"I am writing to express my interest in the {role} position at "
                    f"{company}. {profile.summary}"
                ),
                (
                    "My background includes hands-on experience across VLSI design, "
                    "verification, and related tooling, as reflected in my resume. "
                    "I would welcome the opportunity to contribute to your team."
                ),
                (
                    f"Thank you for your time and consideration. I look forward to "
                    f"discussing how my skills align with {company}'s needs."
                ),
            ],
        }
        if name:
            draft["paragraphs"][0] = draft["paragraphs"][0].replace(
                "I am writing", f"I am {name}, and I am writing", 1
            )

    paragraphs = [p.strip() for p in draft.get("paragraphs", []) if p and p.strip()]
    if not paragraphs:
        paragraphs = [profile.summary or "Please see my attached resume for details."]

    salutation = draft.get("salutation") or _SALUTATION_DEFAULT
    subject = draft.get("subject") or (
        f"Application for {jd.title or 'position'}"
        + (f" at {jd.company}" if jd.company else "")
    )

    return {
        "salutation": salutation,
        "paragraphs": paragraphs,
        "subject": subject,
        "body_text": "\n\n".join(paragraphs),
        "body_markdown": "\n\n".join(paragraphs),
    }


def _render_cover_outputs(
    draft: dict[str, Any],
    profile: MasterProfile,
    jd: JobDescription,
    out_dir: Path,
    basename: str,
    settings: dict[str, Any],
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    identity = profile.identity
    today = date.today().strftime("%B %d, %Y")

    txt_path = out_dir / f"{basename}.txt"
    md_path = out_dir / f"{basename}.md"

    header_lines = [
        identity.name,
        identity.email,
        identity.phone,
        today,
        "",
        jd.company or "",
        "",
        f"Dear {draft['salutation']},",
        "",
    ]
    body = draft["body_text"]
    footer = f"\n\nSincerely,\n{identity.name}"

    txt_content = "\n".join(line for line in header_lines if line is not None) + body + footer
    txt_path.write_text(txt_content, encoding="utf-8")
    paths["txt"] = txt_path

    md_lines = [
        f"**{identity.name}**  ",
        f"{identity.email} | {identity.phone}  ",
        f"_{today}_",
        "",
        f"**Re:** {draft['subject']}",
        "",
        f"Dear {draft['salutation']},",
        "",
    ]
    md_lines.extend(draft["paragraphs"])
    md_lines.extend(["", f"Sincerely,  ", identity.name])
    md_path.write_text("\n\n".join(md_lines), encoding="utf-8")
    paths["md"] = md_path

    templates_dir = resolve_path("templates_dir", settings)
    env = _jinja_env(templates_dir)
    template = env.get_template("cover_letter.tex.j2")
    tex_path = out_dir / f"{basename}.tex"
    tex_path.write_text(
        template.render(
            identity=identity,
            date=today,
            recipient="",
            company=jd.company or "",
            salutation=draft["salutation"],
            paragraphs=draft["paragraphs"],
        ),
        encoding="utf-8",
    )
    paths["tex"] = tex_path

    pdf_path, pdf_error = compile_tex_to_pdf(tex_path, out_dir)
    if pdf_path:
        paths["pdf"] = pdf_path
    elif pdf_error:
        note_path = out_dir / f"{basename}.pdf_note.txt"
        note_path.write_text(pdf_error + "\n", encoding="utf-8")
        paths["pdf_note"] = note_path

    return paths


def generate_cover_letter(
    profile: MasterProfile,
    jd: JobDescription,
    tailored: Optional[TailoredResume] = None,
    research: Optional[dict[str, Any]] = None,
    out_dir: Path | str | None = None,
    basename: str | None = None,
    client: NimClient | None = None,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate cover letter prose and render to txt/md/tex/pdf.

    Returns dict with ``content`` (salutation, paragraphs, subject, body_text) and
    ``files`` (format -> Path).
    """
    cfg = settings or load_settings()
    company_slug = re.sub(r"[^\w\-]+", "_", (jd.company or "company").strip())[:40]
    role_slug = re.sub(r"[^\w\-]+", "_", (jd.title or "role").strip())[:40]
    default_basename = f"cover_{company_slug}_{role_slug}".strip("_")
    file_base = basename or default_basename or "cover_letter"

    if out_dir is None:
        out_dir = resolve_path("output_dir", cfg) / file_base
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    draft = _draft_cover_letter_text(profile, jd, tailored, research, client)
    files = _render_cover_outputs(draft, profile, jd, out_path, file_base, cfg)

    return {
        "subject": draft["subject"],
        "salutation": draft["salutation"],
        "paragraphs": draft["paragraphs"],
        "body_text": draft["body_text"],
        "body_markdown": draft["body_markdown"],
        "files": files,
    }
