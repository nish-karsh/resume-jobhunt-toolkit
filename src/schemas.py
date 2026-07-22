"""Shared data contracts for the Resume Job-Hunt Toolkit pipeline.

Pipeline overview
-----------------
1. **Parse** — ``resume_parser.parse_resume`` reads a PDF and produces a
   ``MasterProfile`` with a reusable ``bullet_bank`` (no fabrication).
2. **Ingest** — ``jd_ingest`` (later phase) builds a ``JobDescription`` from
   pasted text or a URL.
3. **Tailor** — ``tailor`` (later phase) selects/rephrases bullets from
   ``bullet_bank`` only and emits a ``TailoredResume``.
4. **ATS** — ``ats`` (later phase) compares JD keywords vs resume text and
   returns an ``AtsReport``.
5. **Render / outreach** — LaTeX PDF, cover letter, email draft, tracker row.

All modules exchange plain dicts via ``to_dict`` / ``from_dict`` so parallel
agents can rely on stable field names documented below.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional


# ---------------------------------------------------------------------------
# MasterProfile
# ---------------------------------------------------------------------------


@dataclass
class Identity:
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio_links: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Identity:
        return cls(
            name=data.get("name", ""),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            location=data.get("location", ""),
            linkedin=data.get("linkedin", ""),
            github=data.get("github", ""),
            portfolio_links=list(data.get("portfolio_links", [])),
        )


@dataclass
class ExperienceEntry:
    company: str = ""
    title: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    bullets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperienceEntry:
        return cls(
            company=data.get("company", ""),
            title=data.get("title", ""),
            location=data.get("location", ""),
            start=data.get("start", ""),
            end=data.get("end", ""),
            bullets=list(data.get("bullets", [])),
        )


@dataclass
class ProjectEntry:
    name: str = ""
    link: str = ""
    tech: list[str] = field(default_factory=list)
    bullets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectEntry:
        return cls(
            name=data.get("name", ""),
            link=data.get("link", ""),
            tech=list(data.get("tech", [])),
            bullets=list(data.get("bullets", [])),
        )


@dataclass
class EducationEntry:
    institution: str = ""
    degree: str = ""
    field: str = ""
    start: str = ""
    end: str = ""
    gpa: str = ""
    location: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EducationEntry:
        return cls(
            institution=data.get("institution", ""),
            degree=data.get("degree", ""),
            field=data.get("field", ""),
            start=data.get("start", ""),
            end=data.get("end", ""),
            gpa=data.get("gpa", ""),
            location=data.get("location", ""),
        )


BulletSource = Literal["experience", "project"]


@dataclass
class BulletBankEntry:
    id: str = ""
    text: str = ""
    tags: list[str] = field(default_factory=list)
    source: BulletSource = "experience"
    has_metric: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BulletBankEntry:
        source = data.get("source", "experience")
        if source not in ("experience", "project"):
            source = "experience"
        return cls(
            id=data.get("id", ""),
            text=data.get("text", ""),
            tags=list(data.get("tags", [])),
            source=source,
            has_metric=bool(data.get("has_metric", False)),
        )


@dataclass
class MasterProfile:
    """Structured resume + reusable bullet bank (source of truth)."""

    identity: Identity = field(default_factory=Identity)
    summary: str = ""
    skills: dict[str, list[str]] = field(default_factory=dict)
    experience: list[ExperienceEntry] = field(default_factory=list)
    projects: list[ProjectEntry] = field(default_factory=list)
    education: list[EducationEntry] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    achievements: list[str] = field(default_factory=list)
    bullet_bank: list[BulletBankEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "summary": self.summary,
            "skills": {k: list(v) for k, v in self.skills.items()},
            "experience": [e.to_dict() for e in self.experience],
            "projects": [p.to_dict() for p in self.projects],
            "education": [e.to_dict() for e in self.education],
            "certifications": list(self.certifications),
            "achievements": list(self.achievements),
            "bullet_bank": [b.to_dict() for b in self.bullet_bank],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MasterProfile:
        return cls(
            identity=Identity.from_dict(data.get("identity", {})),
            summary=data.get("summary", ""),
            skills={k: list(v) for k, v in data.get("skills", {}).items()},
            experience=[
                ExperienceEntry.from_dict(e) for e in data.get("experience", [])
            ],
            projects=[ProjectEntry.from_dict(p) for p in data.get("projects", [])],
            education=[
                EducationEntry.from_dict(e) for e in data.get("education", [])
            ],
            certifications=list(data.get("certifications", [])),
            achievements=list(data.get("achievements", [])),
            bullet_bank=[
                BulletBankEntry.from_dict(b) for b in data.get("bullet_bank", [])
            ],
        )


# ---------------------------------------------------------------------------
# JobDescription
# ---------------------------------------------------------------------------


@dataclass
class JobDescription:
    raw_text: str = ""
    source_url: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    seniority: str = ""
    requirements: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobDescription:
        return cls(
            raw_text=data.get("raw_text", ""),
            source_url=data.get("source_url", ""),
            title=data.get("title", ""),
            company=data.get("company", ""),
            location=data.get("location", ""),
            seniority=data.get("seniority", ""),
            requirements=list(data.get("requirements", [])),
            keywords=list(data.get("keywords", [])),
        )


# ---------------------------------------------------------------------------
# TailoredResume
# ---------------------------------------------------------------------------


@dataclass
class TailoredResumeMeta:
    job_title: str = ""
    company: str = ""
    jd_keywords: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    model_used: str = ""
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TailoredResumeMeta:
        return cls(
            job_title=data.get("job_title", ""),
            company=data.get("company", ""),
            jd_keywords=list(data.get("jd_keywords", [])),
            matched_keywords=list(data.get("matched_keywords", [])),
            missing_keywords=list(data.get("missing_keywords", [])),
            model_used=data.get("model_used", ""),
            generated_at=data.get("generated_at", ""),
        )


@dataclass
class TailoredResume:
    """MasterProfile fields tailored for a job, plus tailoring metadata."""

    identity: Identity = field(default_factory=Identity)
    summary: str = ""
    skills: dict[str, list[str]] = field(default_factory=dict)
    experience: list[ExperienceEntry] = field(default_factory=list)
    projects: list[ProjectEntry] = field(default_factory=list)
    education: list[EducationEntry] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    achievements: list[str] = field(default_factory=list)
    bullet_bank: list[BulletBankEntry] = field(default_factory=list)
    meta: TailoredResumeMeta = field(default_factory=TailoredResumeMeta)

    def to_dict(self) -> dict[str, Any]:
        base = MasterProfile(
            identity=self.identity,
            summary=self.summary,
            skills=self.skills,
            experience=self.experience,
            projects=self.projects,
            education=self.education,
            certifications=self.certifications,
            achievements=self.achievements,
            bullet_bank=self.bullet_bank,
        ).to_dict()
        base["meta"] = self.meta.to_dict()
        return base

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TailoredResume:
        meta_data = data.pop("meta", {}) if "meta" in data else {}
        profile = MasterProfile.from_dict(data)
        return cls(
            identity=profile.identity,
            summary=profile.summary,
            skills=profile.skills,
            experience=profile.experience,
            projects=profile.projects,
            education=profile.education,
            certifications=profile.certifications,
            achievements=profile.achievements,
            bullet_bank=profile.bullet_bank,
            meta=TailoredResumeMeta.from_dict(meta_data),
        )


# ---------------------------------------------------------------------------
# JobPosting (job search)
# ---------------------------------------------------------------------------


@dataclass
class JobPosting:
    """A normalized open job from any search source (Adzuna, Remotive, ATS boards)."""

    source: str = ""          # adzuna | remotive | greenhouse | lever
    external_id: str = ""     # provider's id for the posting
    title: str = ""
    company: str = ""
    location: str = ""
    remote: bool = False
    url: str = ""             # apply / detail URL
    description: str = ""
    posted_at: str = ""       # ISO date (YYYY-MM-DD) if known
    salary: str = ""
    tags: list[str] = field(default_factory=list)
    score: float = 0.0        # relevance score (filled by search)

    @property
    def uid(self) -> str:
        """Stable de-duplication key."""
        if self.external_id:
            return f"{self.source}:{self.external_id}"
        return f"url:{self.url.strip().rstrip('/').lower()}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["uid"] = self.uid
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobPosting:
        return cls(
            source=data.get("source", ""),
            external_id=str(data.get("external_id", "")),
            title=data.get("title", ""),
            company=data.get("company", ""),
            location=data.get("location", ""),
            remote=bool(data.get("remote", False)),
            url=data.get("url", ""),
            description=data.get("description", ""),
            posted_at=data.get("posted_at", ""),
            salary=data.get("salary", ""),
            tags=list(data.get("tags", [])),
            score=float(data.get("score", 0.0) or 0.0),
        )


# ---------------------------------------------------------------------------
# AtsReport
# ---------------------------------------------------------------------------


@dataclass
class AtsReport:
    score: int = 0
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    format_warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AtsReport:
        score = int(data.get("score", 0))
        score = max(0, min(100, score))
        return cls(
            score=score,
            matched=list(data.get("matched", [])),
            missing=list(data.get("missing", [])),
            format_warnings=list(data.get("format_warnings", [])),
            suggestions=list(data.get("suggestions", [])),
        )
