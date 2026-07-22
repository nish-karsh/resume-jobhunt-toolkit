"""Parse resume PDFs into a structured MasterProfile + bullet bank."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

import pdfplumber
import yaml

from src.schemas import (
    BulletBankEntry,
    EducationEntry,
    ExperienceEntry,
    Identity,
    MasterProfile,
    ProjectEntry,
)
from src.settings_loader import load_settings, project_root, resolve_path

# Known identity defaults (user-provided; merged on save).
KNOWN_IDENTITY = {
    "name": "Nishkarsh Jain",
    "github": "https://github.com/nish-karsh",
    "linkedin": "http://www.linkedin.com/in/nishkarsh-jain-481327102",
}

TARGET_DOMAIN_DEFAULTS = {
    "primary": "VLSI/ASIC Design Verification (UVM/SystemVerilog)",
    "secondary": [
        "RTL Design",
        "PD/STA",
        "Emulation",
        "Embedded Systems",
        "RF/DSP/SDR",
    ],
    "locations": ["India", "Remote"],
}

PROFILE_EXTRA_DEFAULTS = {
    "current_city": "TODO",
    "target_titles": "TODO",
    "notice_period": "TODO",
    "from_email": "TODO",
}

SECTION_ALIASES: dict[str, str] = {
    "summary": "summary",
    "objective": "summary",
    "profile": "summary",
    "professional summary": "summary",
    "skills": "skills",
    "skills & interests": "skills",
    "technical skills": "skills",
    "core competencies": "skills",
    "experience": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "employment": "experience",
    "projects": "projects",
    "academic projects": "projects",
    "personal projects": "projects",
    "education": "education",
    "certifications": "certifications",
    "certificates": "certifications",
    "achievements": "achievements",
    "awards": "achievements",
    "honors": "achievements",
}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4,6}"
)
URL_RE = re.compile(r"https?://[^\s)]+|www\.[^\s)]+|github\.com/[^\s)]+", re.I)
BULLET_RE = re.compile(r"^[\u2022\u25cf\u25cb\u25aa\-\*●•]\s*")
DATE_RANGE_RE = re.compile(
    r"("
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{4}\s*[-–—]\s*(?:"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{4}|Ongoing|Present|Current|here)"
    r"|\d{4}\s*[-–—]\s*(?:\d{4}|Ongoing|Present|Current)"
    r")",
    re.I,
)
METRIC_RE = re.compile(
    r"\d+\s*%|\d+\s*x|\b\d{1,3}(?:,\d{3})+\b|\b\d+(?:\.\d+)?\b",
    re.I,
)

TECH_KEYWORDS = {
    "verilog",
    "systemverilog",
    "uvm",
    "c++",
    "c/c++",
    "python",
    "perl",
    "sta",
    "fpga",
    "asic",
    "emulation",
    "zebu",
    "uart",
    "vcs",
    "vivado",
    "matlab",
    "simulink",
    "pcb",
    "iot",
    "sdr",
    "5g",
    "rtl",
    "timing",
    "synthesis",
    "embedded",
    "arduino",
    "esp-32",
    "stm32",
}


# PDF hyperlinks often extract as the literal text "(here)"; emoji/link glyphs
# (e.g. the U+1F517 link symbol) also leak in. Strip both from parsed fields.
_HERE_ARTIFACT_RE = re.compile(r"\(\s*here\s*\)", re.IGNORECASE)
_ARTIFACT_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E0-\U0001F1FF"
    "\U0000FE00-\U0000FE0F"
    "\U0000200D"
    "]+",
    flags=re.UNICODE,
)
_TRAILING_DATE_RE = re.compile(
    r"\s*[-–—,]?\s*"
    r"(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+)?"
    r"\d{4}(?:\s*[-–—]\s*(?:\d{4}|present|ongoing|current))?\s*$",
    re.IGNORECASE,
)

_CITY_TOKENS = {
    "noida", "bangalore", "bengaluru", "pune", "patiala", "shamli",
    "gurgaon", "gurugram", "hyderabad", "chennai", "mumbai", "delhi",
    "new delhi", "kolkata", "ahmedabad", "jaipur",
}

_DEGREE_PREFIX_RE = re.compile(
    r"^(B\.?E\.?|B\.?Tech\.?|M\.?Tech\.?|B\.?Sc\.?|M\.?Sc\.?|Ph\.?D\.?|"
    r"Bachelors?|Masters?|Diploma)\b[.\s]*(?:in|of)?\s*(.*)$",
    re.IGNORECASE,
)


def _strip_artifacts(text: str) -> str:
    """Remove PDF link artifacts and emoji, and collapse whitespace."""
    if not text:
        return ""
    text = _HERE_ARTIFACT_RE.sub(" ", text)
    text = _ARTIFACT_EMOJI_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _split_degree_field(text: str) -> tuple[str, str]:
    """Split a degree line into (degree, field of study)."""
    text = text.strip()
    if not text:
        return "", ""
    if "," in text:
        left, right = text.split(",", 1)
        return left.strip(" ,"), right.strip(" ,")
    match = _DEGREE_PREFIX_RE.match(text)
    if match and match.group(2).strip():
        return match.group(1).strip(" ,"), match.group(2).strip(" ,")
    return text, ""


def _normalize_header(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().lower())


def _is_section_header(line: str) -> Optional[str]:
    norm = _normalize_header(line)
    if norm in SECTION_ALIASES:
        return SECTION_ALIASES[norm]
    if len(line.strip()) < 60 and line.strip().isupper() and len(line.split()) <= 5:
        return SECTION_ALIASES.get(norm)
    return None


def _extract_text(pdf_path: Path) -> str:
    pages: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _split_sections(text: str) -> dict[str, list[str]]:
    lines = [ln.rstrip() for ln in text.splitlines()]
    sections: dict[str, list[str]] = {}
    current = "header"
    sections[current] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        section = _is_section_header(stripped)
        if section:
            current = section
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(stripped)

    return sections


def _extract_contact(header_lines: list[str]) -> Identity:
    blob = " ".join(header_lines)
    identity = Identity()

    emails = EMAIL_RE.findall(blob)
    if emails:
        identity.email = emails[0]

    phones = PHONE_RE.findall(blob)
    for phone in phones:
        digits = re.sub(r"\D", "", phone)
        if 10 <= len(digits) <= 13:
            identity.phone = phone.strip()
            break

    urls = URL_RE.findall(blob)
    for url in urls:
        low = url.lower()
        if "linkedin" in low and not identity.linkedin:
            identity.linkedin = url if url.startswith("http") else f"https://{url}"
        elif "github" in low and not identity.github:
            identity.github = url if url.startswith("http") else f"https://{url}"
        elif url not in identity.portfolio_links:
            identity.portfolio_links.append(url)

    if header_lines:
        name_candidate = header_lines[0].strip()
        if name_candidate and "@" not in name_candidate and not BULLET_RE.match(
            name_candidate
        ):
            identity.name = name_candidate

    return identity


def _parse_date_range(text: str) -> tuple[str, str, str]:
    match = DATE_RANGE_RE.search(text)
    if not match:
        return text.strip(), "", ""
    remainder = text[: match.start()].strip(" ,-|")
    span = match.group(0)
    parts = re.split(r"\s*[-–—]\s*", span, maxsplit=1)
    start = parts[0].strip()
    end = parts[1].strip() if len(parts) > 1 else ""
    return remainder, start, end


def _parse_experience(lines: list[str]) -> list[ExperienceEntry]:
    """Parse experience blocks: company line, title+dates line, then bullets."""
    entries: list[ExperienceEntry] = []
    current: ExperienceEntry | None = None
    pending_company_line: str | None = None
    idx = 0

    while idx < len(lines):
        line = lines[idx]

        if BULLET_RE.match(line):
            bullet = _strip_artifacts(BULLET_RE.sub("", line))
            if current and bullet:
                current.bullets.append(bullet)
                while idx + 1 < len(lines):
                    nxt = lines[idx + 1]
                    if (
                        BULLET_RE.match(nxt)
                        or _parse_date_range(nxt)[1]
                        or _looks_like_company_line(nxt)
                    ):
                        break
                    idx += 1
                    current.bullets[-1] = _strip_artifacts(f"{current.bullets[-1]} {nxt}")
            idx += 1
            continue

        remainder, start, end = _parse_date_range(line)
        if start:
            title = _strip_artifacts(remainder)
            company, location = _split_company_location(pending_company_line or "")
            if current and (current.company or current.bullets):
                entries.append(current)
            current = ExperienceEntry(
                company=company,
                title=title,
                location=location,
                start=start,
                end=end,
            )
            pending_company_line = None
            idx += 1
            continue

        if current and current.bullets:
            entries.append(current)
            current = None
        pending_company_line = line
        idx += 1

    if current:
        entries.append(current)
    return entries


def _looks_like_company_line(line: str) -> bool:
    if BULLET_RE.match(line) or _parse_date_range(line)[1]:
        return False
    return bool(
        re.search(r"\b(Pvt\.?|Ltd\.?|Limited|Inc\.?|Corporation|Company)\b", line, re.I)
    )


def _split_company_location(text: str) -> tuple[str, str]:
    text = _strip_artifacts(text)
    if not text:
        return "", ""
    location = ""
    if "," in text:
        left, right = text.rsplit(",", 1)
        location = right.strip()
        text = left.strip()
    else:
        match = re.search(
            r"^(.*?)\s+"
            r"(Patiala|Punjab|Karnataka|Maharashtra|Uttar Pradesh|Tamil Nadu|"
            r"Telangana|Gujarat|Haryana|Delhi|Noida|Bangalore|Bengaluru|Pune|India)$",
            text,
            re.I,
        )
        if match:
            text, location = match.group(1).strip(), match.group(2).strip()
    # A city often trails the company name (e.g. "... Pvt. Ltd. Noida"); move it
    # into the location so the company stays clean.
    words = text.split()
    for n in (2, 1):
        if len(words) >= n:
            tail = " ".join(words[-n:])
            if tail.lower() in _CITY_TOKENS:
                text = " ".join(words[:-n]).strip()
                location = f"{tail}, {location}".strip(", ") if location else tail
                break
    return text.strip(" ,"), location.strip(" ,")


def _parse_projects(lines: list[str]) -> list[ProjectEntry]:
    entries: list[ProjectEntry] = []
    current: ProjectEntry | None = None

    for line in lines:
        if BULLET_RE.match(line):
            bullet = _strip_artifacts(BULLET_RE.sub("", line))
            if current and bullet:
                current.bullets.append(bullet)
            continue

        remainder, start, end = _parse_date_range(line)
        title_line = remainder if start else line
        link = ""
        link_match = re.search(r"(https?://\S+)", title_line)
        if link_match:
            link = link_match.group(1).strip()
            title_line = title_line.replace(link_match.group(0), "").strip()

        title_line = _strip_artifacts(title_line)
        title_line = _TRAILING_DATE_RE.sub("", title_line).strip()
        if current:
            entries.append(current)
        current = ProjectEntry(
            name=title_line,
            link=link,
            tech=_extract_tech_from_text(title_line),
        )

    if current:
        entries.append(current)
    return entries


def _parse_education(lines: list[str]) -> tuple[list[EducationEntry], list[str]]:
    """Return (education entries, stray notes) - parenthetical honours become notes."""
    entries: list[EducationEntry] = []
    notes: list[str] = []
    pending_institution: str | None = None

    for raw in lines:
        line = _strip_artifacts(raw)
        if not line:
            continue
        if line.startswith("(") and line.endswith(")"):
            note = line.strip("() ").strip()
            if note:
                notes.append(note)
            continue

        remainder, start, end = _parse_date_range(line)
        if start:
            institution, location = _split_company_location(pending_institution or "")
            degree_text = remainder.strip()
            gpa = ""
            gpa_match = re.search(r"(?:CGPA|GPA)[-:\s]*([\d.]+)", degree_text, re.I)
            if gpa_match:
                gpa = gpa_match.group(1)
                degree_text = (
                    degree_text[: gpa_match.start()] + " " + degree_text[gpa_match.end() :]
                ).strip(" .,-")
            degree, field = _split_degree_field(degree_text)
            entries.append(
                EducationEntry(
                    institution=institution,
                    degree=degree,
                    field=field,
                    start=start,
                    end=end,
                    gpa=gpa,
                    location=location,
                )
            )
            pending_institution = None
            continue

        pending_institution = line

    return entries, notes


def _parse_skills(lines: list[str]) -> dict[str, list[str]]:
    skills: dict[str, list[str]] = {}
    for line in lines:
        if ":" in line:
            category, raw = line.split(":", 1)
            items = [s.strip() for s in re.split(r",|;|\|", raw) if s.strip()]
            skills[category.strip()] = items
        else:
            items = [s.strip() for s in re.split(r",|;|\|", line) if s.strip()]
            skills.setdefault("General", []).extend(items)
    return skills


def _parse_list_section(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        if BULLET_RE.match(line):
            items.append(_strip_artifacts(BULLET_RE.sub("", line)))
        else:
            items.append(_strip_artifacts(line))
    return [i for i in items if i]


def _extract_tech_from_text(text: str) -> list[str]:
    found: list[str] = []
    lower = text.lower()
    for kw in TECH_KEYWORDS:
        if kw in lower:
            found.append(kw)
    return found


def _tag_bullet(text: str) -> list[str]:
    tags: list[str] = []
    lower = text.lower()
    for kw in TECH_KEYWORDS:
        if kw in lower:
            tags.append(kw)
    for token in re.findall(r"\b[A-Z][A-Za-z0-9+#/]{1,20}\b", text):
        if token.lower() not in tags and len(token) > 2:
            tags.append(token)
    return tags[:12]


def _has_metric(text: str) -> bool:
    return bool(METRIC_RE.search(text))


def _build_bullet_bank(
    experience: list[ExperienceEntry], projects: list[ProjectEntry]
) -> list[BulletBankEntry]:
    bank: list[BulletBankEntry] = []
    counter = 1
    for exp in experience:
        for bullet in exp.bullets:
            bank.append(
                BulletBankEntry(
                    id=f"exp-{counter:03d}",
                    text=bullet,
                    tags=_tag_bullet(bullet),
                    source="experience",
                    has_metric=_has_metric(bullet),
                )
            )
            counter += 1
    counter = 1
    for proj in projects:
        for bullet in proj.bullets:
            bank.append(
                BulletBankEntry(
                    id=f"proj-{counter:03d}",
                    text=bullet,
                    tags=_tag_bullet(bullet),
                    source="project",
                    has_metric=_has_metric(bullet),
                )
            )
            counter += 1
    return bank


def parse_resume(pdf_path: Path | str) -> MasterProfile:
    """Parse a resume PDF into a MasterProfile."""
    path = Path(pdf_path)
    text = _extract_text(path)
    sections = _split_sections(text)

    identity = _extract_contact(sections.get("header", []))
    summary = " ".join(sections.get("summary", [])).strip()
    skills = _parse_skills(sections.get("skills", []))
    experience = _parse_experience(sections.get("experience", []))
    projects = _parse_projects(sections.get("projects", []))
    education, edu_notes = _parse_education(sections.get("education", []))
    certifications = _parse_list_section(sections.get("certifications", []))
    achievements = _parse_list_section(sections.get("achievements", []))
    achievements.extend(note for note in edu_notes if note not in achievements)
    bullet_bank = _build_bullet_bank(experience, projects)

    return MasterProfile(
        identity=identity,
        summary=summary,
        skills=skills,
        experience=experience,
        projects=projects,
        education=education,
        certifications=certifications,
        achievements=achievements,
        bullet_bank=bullet_bank,
    )


def _merge_identity(profile: MasterProfile) -> MasterProfile:
    for key, value in KNOWN_IDENTITY.items():
        current = getattr(profile.identity, key, "")
        if not current or current == "TODO":
            setattr(profile.identity, key, value)
    return profile


def _placeholder(value: str) -> str:
    return value if value and value.strip() and value.strip().upper() != "TODO" else "TODO"


def profile_to_yaml_dict(profile: MasterProfile) -> dict[str, Any]:
    """Convert MasterProfile to profile.yaml structure with extra user fields."""
    data = profile.to_dict()
    identity = data["identity"]
    identity["email"] = _placeholder(identity.get("email", ""))
    identity["phone"] = _placeholder(identity.get("phone", ""))
    identity["location"] = _placeholder(identity.get("location", ""))

    return {
        "identity": identity,
        "summary": data["summary"] or "TODO",
        "skills": data["skills"],
        "experience": data["experience"],
        "projects": data["projects"],
        "education": data["education"],
        "certifications": data["certifications"],
        "achievements": data["achievements"],
        "bullet_bank": data["bullet_bank"],
        "target_domain": TARGET_DOMAIN_DEFAULTS,
        **PROFILE_EXTRA_DEFAULTS,
        "from_email": _placeholder(identity.get("email", ""))
        if identity.get("email", "") != "TODO"
        else "TODO",
    }


def save_profile(profile: MasterProfile, profile_yaml_path: Path | str) -> None:
    """Write profile to YAML, merging known identity defaults."""
    profile = _merge_identity(profile)
    path = Path(profile_yaml_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = profile_to_yaml_dict(profile)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False, allow_unicode=True)


def load_profile(profile_yaml_path: Path | str) -> MasterProfile:
    """Load MasterProfile fields from profile.yaml (ignores extra keys)."""
    path = Path(profile_yaml_path)
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return MasterProfile.from_dict(data)


def ensure_profile(
    settings: dict[str, Any] | None = None,
) -> MasterProfile:
    """Load profile.yaml or generate it from the seed resume."""
    cfg = settings or load_settings()
    profile_path = resolve_path("profile_yaml", cfg)
    seed_path = resolve_path("seed_resume", cfg)

    if profile_path.exists():
        return load_profile(profile_path)

    if not seed_path.exists():
        raise FileNotFoundError(f"Seed resume not found: {seed_path}")

    profile = parse_resume(seed_path)
    profile = _merge_identity(profile)
    save_profile(profile, profile_path)
    cache_path = resolve_path("profile_cache_json", cfg)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as fh:
        json.dump(profile.to_dict(), fh, indent=2, ensure_ascii=False)
    return profile


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Parse seed resume into profile.yaml")
    parser.add_argument(
        "--pdf",
        type=Path,
        default=None,
        help="Resume PDF path (default: settings paths.seed_resume)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing profile.yaml",
    )
    args = parser.parse_args()

    settings = load_settings()
    profile_path = resolve_path("profile_yaml", settings)
    pdf_path = args.pdf or resolve_path("seed_resume", settings)
    cache_path = resolve_path("profile_cache_json", settings)

    if profile_path.exists() and not args.force:
        profile = load_profile(profile_path)
        print(f"Loaded existing profile: {profile_path}")
    else:
        if not pdf_path.exists():
            print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
            return 1
        profile = parse_resume(pdf_path)
        profile = _merge_identity(profile)
        save_profile(profile, profile_path)
        print(f"Wrote profile: {profile_path}")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as fh:
        json.dump(profile.to_dict(), fh, indent=2, ensure_ascii=False)
    print(f"Wrote cache: {cache_path}")

    skill_count = sum(len(v) for v in profile.skills.values())
    print(f"name: {profile.identity.name}")
    print(f"email: {profile.identity.email}")
    print(f"skills: {skill_count} across {len(profile.skills)} categories")
    print(f"experience: {len(profile.experience)} entries")
    print(f"projects: {len(profile.projects)} entries")
    print(f"bullet_bank: {len(profile.bullet_bank)} bullets")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
