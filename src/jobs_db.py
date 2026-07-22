"""SQLite-backed job pipeline: dedupe found jobs and track application status.

This is the source of truth for the job hunt. ``applications.xlsx`` is produced as a
read-only export/mirror (see :func:`export_to_xlsx`) so the existing spreadsheet
workflow keeps working.

Status lifecycle: found -> shortlisted -> tailored -> applied -> interview -> closed
(plus ``skipped`` for jobs you dismiss). Only jobs you explicitly act on ever move
past ``found``; nothing is auto-applied.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from openpyxl import Workbook

from src.schemas import JobPosting
from src.settings_loader import load_settings, resolve_path
from src.tracker import TRACKER_COLUMNS

STATUSES = [
    "found",
    "shortlisted",
    "tailored",
    "applied",
    "interview",
    "closed",
    "skipped",
]

_COLUMNS = [
    "uid", "source", "external_id", "title", "company", "location", "remote",
    "url", "description", "posted_at", "salary", "tags", "status", "score",
    "resume_file", "cover_file", "email_file", "notes", "first_seen",
    "updated_at", "applied_at",
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_db_path(settings: Optional[dict[str, Any]] = None) -> Path:
    cfg = settings or load_settings()
    return resolve_path("jobs_db", cfg)


def connect(db_path: Path | str | None = None, settings: Optional[dict[str, Any]] = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else default_db_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    _init(conn)
    return conn


def _init(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            uid TEXT PRIMARY KEY,
            source TEXT, external_id TEXT, title TEXT, company TEXT,
            location TEXT, remote INTEGER, url TEXT, description TEXT,
            posted_at TEXT, salary TEXT, tags TEXT,
            status TEXT DEFAULT 'found', score REAL DEFAULT 0,
            resume_file TEXT DEFAULT '', cover_file TEXT DEFAULT '',
            email_file TEXT DEFAULT '', notes TEXT DEFAULT '',
            first_seen TEXT, updated_at TEXT, applied_at TEXT DEFAULT ''
        )
        """
    )
    conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = {key: row[key] for key in row.keys()}
    try:
        data["tags"] = json.loads(data.get("tags") or "[]")
    except (TypeError, json.JSONDecodeError):
        data["tags"] = []
    data["remote"] = bool(data.get("remote"))
    return data


def upsert_jobs(
    postings: Iterable[JobPosting],
    db_path: Path | str | None = None,
    settings: Optional[dict[str, Any]] = None,
) -> tuple[int, int]:
    """Insert new postings as ``found``; leave already-tracked ones untouched.

    Returns (new_count, total_seen).
    """
    conn = connect(db_path, settings)
    new_count = 0
    seen = 0
    try:
        for posting in postings:
            seen += 1
            exists = conn.execute(
                "SELECT 1 FROM jobs WHERE uid = ?", (posting.uid,)
            ).fetchone()
            if exists:
                # Refresh volatile fields but never clobber status/notes/files.
                conn.execute(
                    "UPDATE jobs SET score = ?, description = COALESCE(NULLIF(description,''), ?), "
                    "updated_at = ? WHERE uid = ?",
                    (posting.score, posting.description, _now(), posting.uid),
                )
                continue
            now = _now()
            conn.execute(
                f"INSERT INTO jobs ({','.join(_COLUMNS)}) VALUES ({','.join(['?'] * len(_COLUMNS))})",
                (
                    posting.uid, posting.source, posting.external_id, posting.title,
                    posting.company, posting.location, int(posting.remote), posting.url,
                    posting.description, posting.posted_at, posting.salary,
                    json.dumps(posting.tags), "found", posting.score,
                    "", "", "", "", now, now, "",
                ),
            )
            new_count += 1
        conn.commit()
    finally:
        conn.close()
    return new_count, seen


def record_manual(
    company: str,
    role: str,
    url: str = "",
    status: str = "shortlisted",
    db_path: Path | str | None = None,
    settings: Optional[dict[str, Any]] = None,
    **fields: Any,
) -> str:
    """Record a job the user found outside search (e.g. pasted a JD). Returns uid."""
    seed = url or f"{company}|{role}"
    uid = f"manual:{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:16]}"
    posting = JobPosting(
        source="manual", external_id=uid.split(":", 1)[1], title=role,
        company=company, url=url,
    )
    upsert_jobs([posting], db_path, settings)
    update_job(uid, db_path=db_path, settings=settings, status=status, **fields)
    return uid


def list_jobs(
    status: Optional[str] = None,
    query: Optional[str] = None,
    db_path: Path | str | None = None,
    settings: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    conn = connect(db_path, settings)
    try:
        sql = "SELECT * FROM jobs"
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if query:
            clauses.append("(LOWER(title) LIKE ? OR LOWER(company) LIKE ?)")
            like = f"%{query.lower()}%"
            params.extend([like, like])
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY (status='found') DESC, score DESC, updated_at DESC"
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_job(
    uid: str,
    db_path: Path | str | None = None,
    settings: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    conn = connect(db_path, settings)
    try:
        row = conn.execute("SELECT * FROM jobs WHERE uid = ?", (uid,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update_job(
    uid: str,
    db_path: Path | str | None = None,
    settings: Optional[dict[str, Any]] = None,
    **fields: Any,
) -> bool:
    """Update mutable fields (status, resume_file, cover_file, email_file, notes)."""
    allowed = {"status", "resume_file", "cover_file", "email_file", "notes", "score"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return False
    if updates.get("status") == "applied":
        updates.setdefault("applied_at", _now())
    conn = connect(db_path, settings)
    try:
        # applied_at is set implicitly above; include it in the column list if present.
        cols = list(updates.keys())
        set_clause = ", ".join(f"{c} = ?" for c in cols) + ", updated_at = ?"
        params = [updates[c] for c in cols] + [_now(), uid]
        cur = conn.execute(f"UPDATE jobs SET {set_clause} WHERE uid = ?", params)
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def mark_applied(
    uid: str,
    resume_file: str = "",
    cover_file: str = "",
    email_file: str = "",
    notes: str = "",
    db_path: Path | str | None = None,
    settings: Optional[dict[str, Any]] = None,
) -> bool:
    return update_job(
        uid, db_path=db_path, settings=settings, status="applied",
        resume_file=resume_file, cover_file=cover_file, email_file=email_file,
        notes=notes,
    )


def stats(
    db_path: Path | str | None = None,
    settings: Optional[dict[str, Any]] = None,
) -> dict[str, int]:
    conn = connect(db_path, settings)
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM jobs GROUP BY status"
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}
    finally:
        conn.close()


def export_to_xlsx(
    xlsx_path: Path | str | None = None,
    db_path: Path | str | None = None,
    settings: Optional[dict[str, Any]] = None,
) -> Path:
    """Mirror the DB into applications.xlsx (full snapshot, columns match tracker)."""
    cfg = settings or load_settings()
    target = Path(xlsx_path) if xlsx_path else resolve_path("tracker_xlsx", cfg)
    target.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Applications"
    ws.append(TRACKER_COLUMNS)  # Date, Company, Role, Job Link, Status, Resume, Cover, Email, Notes
    for job in list_jobs(db_path=db_path, settings=cfg):
        ws.append([
            job.get("applied_at", "") or job.get("first_seen", ""),
            job.get("company", ""),
            job.get("title", ""),
            job.get("url", ""),
            job.get("status", ""),
            job.get("resume_file", ""),
            job.get("cover_file", ""),
            job.get("email_file", ""),
            job.get("notes", ""),
        ])
    wb.save(str(target))
    return target
