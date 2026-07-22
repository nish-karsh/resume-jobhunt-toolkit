"""Draft recruiter outreach emails (.eml) with resume attached (review-and-send)."""

from __future__ import annotations

import json
import mimetypes
import re
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.nim_client import NimClient, NimClientError
from src.schemas import JobDescription, MasterProfile, TailoredResume
from src.settings_loader import load_settings, resolve_path

# Live SMTP sending is intentionally not implemented in v1.
# Wire up send_recruiter_email() later behind settings["smtp"]["enabled"].


def _jinja_env(templates_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(enabled_extensions=("j2",)),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _draft_email_prose(
    profile: MasterProfile,
    jd: JobDescription,
    tailored: TailoredResume | None,
    client: NimClient | None = None,
) -> dict[str, str]:
    role = jd.title or "the open role"
    company = jd.company or "your company"
    summary_source = tailored.summary if tailored else profile.summary

    system = (
        "You draft short, professional recruiter outreach emails. "
        "Use only facts from the candidate profile. No fabrication. "
        "Keep the body under 120 words, friendly and direct."
    )
    user = (
        f"Role: {role}\nCompany: {company}\n"
        f"Candidate summary: {summary_source}\n"
        f"Candidate name: {profile.identity.name}\n"
        "Respond with JSON only: "
        '{"subject": "...", "body": "..."}'
    )

    try:
        nim = client or NimClient()
        raw = nim.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            max_tokens=512,
        )
        start = raw.find("{")
        end = raw.rfind("}")
        parsed = json.loads(raw[start : end + 1])
        subject = str(parsed.get("subject", "")).strip()
        body = str(parsed.get("body", "")).strip()
        if subject and body:
            return {"subject": subject, "body": body}
    except (NimClientError, ValueError, json.JSONDecodeError, TypeError):
        pass

    subject = f"Application: {role}" + (f" at {company}" if company else "")
    body = (
        f"I am reaching out regarding the {role} position"
        f"{f' at {company}' if company else ''}. "
        f"{summary_source} "
        "I have attached my tailored resume and would appreciate the chance to connect."
    )
    return {"subject": subject, "body": body}


def build_recruiter_email(
    profile: MasterProfile,
    jd: JobDescription,
    resume_path: Path | str,
    tailored: Optional[TailoredResume] = None,
    out_dir: Path | str | None = None,
    basename: str | None = None,
    client: NimClient | None = None,
    settings: dict[str, Any] | None = None,
) -> Path:
    """Write a review-and-send .eml with tailored subject/body and resume PDF attached."""
    cfg = settings or load_settings()
    resume_file = Path(resume_path)
    if not resume_file.exists():
        raise FileNotFoundError(f"Resume file not found: {resume_file}")

    company_slug = re.sub(r"[^\w\-]+", "_", (jd.company or "company").strip())[:40]
    role_slug = re.sub(r"[^\w\-]+", "_", (jd.title or "role").strip())[:40]
    default_basename = f"email_{company_slug}_{role_slug}".strip("_")
    file_base = basename or default_basename or "recruiter_email"

    if out_dir is None:
        out_dir = resolve_path("output_dir", cfg) / file_base
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    prose = _draft_email_prose(profile, jd, tailored, client)

    templates_dir = resolve_path("templates_dir", cfg)
    env = _jinja_env(templates_dir)
    template = env.get_template("email_recruiter.j2")
    body_text = template.render(
        recipient_name="",
        body=prose["body"],
        sender_name=profile.identity.name,
        sender_email=profile.identity.email,
        sender_phone=profile.identity.phone,
    )

    msg = EmailMessage()
    from_email = profile.identity.email or "candidate@example.com"
    msg["From"] = from_email
    msg["To"] = ""
    msg["Subject"] = prose["subject"]
    msg.set_content(body_text)

    mime_type, _ = mimetypes.guess_type(str(resume_file))
    maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
    msg.add_attachment(
        resume_file.read_bytes(),
        maintype=maintype,
        subtype=subtype,
        filename=resume_file.name,
    )

    eml_path = out_path / f"{file_base}.eml"
    eml_path.write_bytes(msg.as_bytes())
    return eml_path


def send_recruiter_email(eml_path: Path, settings: dict[str, Any] | None = None) -> None:
    """Placeholder for optional future SMTP send (disabled in v1)."""
    cfg = settings or load_settings()
    smtp_cfg = cfg.get("smtp", {})
    if not smtp_cfg.get("enabled"):
        raise NotImplementedError(
            "Live SMTP sending is disabled. Open the .eml in your mail client to review and send."
        )
    raise NotImplementedError("SMTP send is not implemented yet.")
