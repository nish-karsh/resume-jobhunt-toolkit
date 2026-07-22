"""Job Search page: find open roles -> track -> select -> tailor -> apply (opt-in)."""

from __future__ import annotations

import traceback
from pathlib import Path

import streamlit as st

from src import apply_assist, job_search, jobs_db
from src import ui_common as ui
from src.jd_ingest import ingest_jd
from src.render_latex import render_resume
from src.schemas import JobDescription
from src.settings_loader import resolve_path

ui.bootstrap("Job Search")
ui.sidebar()


def _posting_to_jd(job: dict) -> JobDescription:
    text = job.get("description") or job.get("title") or ""
    jd, _ = ui.safe_run("Ingest", ingest_jd, text=text or None, url=None)
    if jd is None:
        jd = JobDescription()
    jd.title = job.get("title", "")
    jd.company = job.get("company", "")
    jd.location = job.get("location", "")
    jd.source_url = job.get("url", "")
    return jd


def _label(job: dict) -> str:
    tag = f" [{job['status']}]" if job.get("status") and job["status"] != "found" else ""
    return f"{job.get('title','?')} - {job.get('company','?')} ({job.get('source','')}){tag}"


def _page() -> None:
    st.title("Job Search")
    st.caption("Free, legal sources only (Adzuna, Remotive, Greenhouse, Lever). "
               "Nothing is applied unless you pick it.")

    if not ui.feature("job_search"):
        st.info("Job search is disabled (`features.job_search` in settings).")
        return
    if st.session_state.profile is None:
        st.error(getattr(st.session_state, "profile_error", "Could not load profile."))
        return

    settings = st.session_state.settings
    js_cfg = settings.get("job_search", {})

    # --- Search form ------------------------------------------------------
    st.subheader("1. Search")
    with st.form("search_form"):
        c1, c2 = st.columns([2, 1])
        query = c1.text_input("Search terms", placeholder="e.g. Design Verification Engineer")
        location = c2.text_input("Location", value=js_cfg.get("default_location", ""))
        sources = st.multiselect(
            "Sources",
            ["adzuna", "remotive", "greenhouse", "lever"],
            default=js_cfg.get("enabled_sources", ["adzuna", "remotive"]),
        )
        submitted = st.form_submit_button("Search jobs", type="primary")

    if submitted:
        result, err = ui.safe_run(
            "Job search", job_search.search_jobs,
            query=query.strip() or None, location=location.strip() or None,
            settings=settings, sources=sources, profile=st.session_state.profile,
        )
        if err:
            st.error(err)
        else:
            postings, warnings = result
            new_count, seen = jobs_db.upsert_jobs(postings, settings=settings)
            st.session_state.search_warnings = warnings
            st.success(f"Found {seen} results ({new_count} new). Tracked below.")
            if warnings:
                with st.expander("Source warnings"):
                    for w in warnings:
                        st.caption(w)

    if any("ADZUNA" in w for w in st.session_state.get("search_warnings", [])):
        st.info("Adzuna needs free keys: set ADZUNA_APP_ID and ADZUNA_APP_KEY in your .env "
                "or host secrets (developer.adzuna.com).")

    # --- Tracked jobs -----------------------------------------------------
    st.divider()
    st.subheader("2. Tracked jobs")

    # Backup/restore: free cloud hosts (e.g. Streamlit Community Cloud) reset local
    # storage on reboot. Shown before the "no jobs" guard so restore works on a fresh boot.
    with st.expander("Backup / restore tracker (cloud disks reset on reboot)"):
        db_path = Path(resolve_path("jobs_db", settings))
        st.caption("Download a backup now; re-upload it later to restore your tracked jobs.")
        if db_path.exists():
            st.download_button("Download jobhunt.db", db_path.read_bytes(),
                               file_name="jobhunt.db", mime="application/octet-stream")
        restore = st.file_uploader("Restore from backup (.db)", type=["db"])
        if restore is not None and st.button("Restore now"):
            db_path.parent.mkdir(parents=True, exist_ok=True)
            db_path.write_bytes(restore.getvalue())
            st.success("Tracker restored.")
            ui.rerun()

    status_filter = st.selectbox(
        "Filter by status", ["(all)"] + jobs_db.STATUSES, index=0
    )
    jobs = jobs_db.list_jobs(
        status=None if status_filter == "(all)" else status_filter, settings=settings
    )
    if not jobs:
        st.caption("No jobs yet - run a search above.")
        return

    st.dataframe(
        [
            {
                "Score": round(j.get("score", 0), 0),
                "Title": j["title"],
                "Company": j["company"],
                "Location": j["location"],
                "Source": j["source"],
                "Status": j["status"],
                "Posted": j["posted_at"],
            }
            for j in jobs
        ],
        use_container_width=True,
        hide_index=True,
    )

    # --- Shortlist --------------------------------------------------------
    labels = {_label(j): j["uid"] for j in jobs}
    shortlisted = st.multiselect("Shortlist jobs (mark as shortlisted)", list(labels.keys()))
    if st.button("Shortlist selected") and shortlisted:
        for lbl in shortlisted:
            jobs_db.update_job(labels[lbl], settings=settings, status="shortlisted")
        jobs_db.export_to_xlsx(settings=settings)
        st.success(f"Shortlisted {len(shortlisted)} job(s).")
        ui.rerun()

    # --- Work on one job --------------------------------------------------
    st.divider()
    st.subheader("3. Work on a job")
    choice = st.selectbox("Choose a job", ["(none)"] + list(labels.keys()))
    if choice == "(none)":
        return

    uid = labels[choice]
    job = jobs_db.get_job(uid, settings=settings)
    if not job:
        return

    st.markdown(f"**{job['title']}** - {job['company']}  \n{job.get('location','')}  ")
    if job.get("url"):
        st.write(job["url"])
    if job.get("description"):
        with st.expander("Description"):
            st.write(job["description"][:4000])

    profile = st.session_state.profile
    colA, colB, colC = st.columns(3)

    # Tailor + render for this job
    with colA:
        if st.button("Tailor & render resume"):
            jd = _posting_to_jd(job)
            st.session_state.jd = jd
            ui.tailor_with_fallback(profile, jd, None)
            if st.session_state.tailored:
                out_dir = ui.job_output_dir(jd)
                files, err = ui.safe_run("Render", render_resume, st.session_state.tailored,
                                         out_dir, "resume_tailored", formats=["pdf", "txt"],
                                         settings=settings)
                if err:
                    st.error(err)
                else:
                    st.session_state.resume_files = files
                    jobs_db.update_job(uid, settings=settings, status="tailored",
                                       resume_file=str(files.get("pdf") or files.get("txt") or ""))
                    jobs_db.export_to_xlsx(settings=settings)
                    st.success("Tailored + rendered. Status -> tailored.")
                    if files.get("pdf_note"):
                        st.info(files["pdf_note"].read_text(encoding="utf-8").strip())

    # Apply
    with colB:
        if job.get("url"):
            st.link_button("Open apply link", job["url"])
        if ui.feature("apply_autofill"):
            if st.button("Auto-fill (local)"):
                applicant = apply_assist.Applicant.from_profile(profile)
                resume = (st.session_state.resume_files or {}).get("pdf") \
                    or (st.session_state.resume_files or {}).get("txt")
                res = apply_assist.launch_autofill(job["url"], resume, applicant, settings)
                (st.success if res["started"] else st.warning)(res["message"])
        else:
            st.caption("Auto-fill is local-only (open the link to apply).")

    # Status update
    with colC:
        new_status = st.selectbox("Set status", jobs_db.STATUSES,
                                  index=jobs_db.STATUSES.index(job["status"])
                                  if job["status"] in jobs_db.STATUSES else 0)
        if st.button("Update status"):
            jobs_db.update_job(uid, settings=settings, status=new_status)
            jobs_db.export_to_xlsx(settings=settings)
            st.success(f"Status -> {new_status}")

    if st.session_state.get("resume_files"):
        ui.download_button("Download resume .pdf",
                           st.session_state.resume_files.get("pdf"), "application/pdf")
        ui.download_button("Download resume .txt",
                           st.session_state.resume_files.get("txt"), "text/plain")


try:
    _page()
except Exception as exc:  # noqa: BLE001
    st.error(f"Unexpected error: {exc}")
    with st.expander("Details"):
        st.code(traceback.format_exc())
