"""Tailor Resume page: JD -> tailor -> ATS -> cover letter -> recruiter email -> track."""

from __future__ import annotations

import traceback

import streamlit as st

from src import jobs_db
from src import ui_common as ui
from src.ats import ats_report
from src.company_research import research as company_research
from src.cover_letter import generate_cover_letter
from src.email_draft import build_recruiter_email
from src.jd_ingest import ingest_jd
from src.render_latex import render_resume
from src.schemas import JobDescription, TailoredResume

ui.bootstrap("Tailor Resume")
ui.sidebar()


def _page() -> None:
    st.title("Tailor Resume")
    st.caption("Tailor resume -> ATS check -> cover letter -> recruiter email -> tracker")

    if st.session_state.profile is None:
        st.error(getattr(st.session_state, "profile_error", "Could not load profile."))
        return

    profile = st.session_state.profile

    # --- Step 1: Ingest JD ------------------------------------------------
    st.subheader("1. Job description")
    col1, col2 = st.columns(2)
    with col1:
        jd_text = st.text_area("Paste JD text (primary)", height=200,
                               placeholder="Paste the full job description here...")
    with col2:
        jd_url = st.text_input("Or JD URL (best-effort)", placeholder="https://...")
        st.caption("Many sites block automated fetch (LinkedIn, Naukri). If URL ingest "
                   "fails, paste the JD text instead.")

    if st.button("Ingest JD", type="primary"):
        if not jd_text.strip() and not jd_url.strip():
            st.error("Provide JD text and/or a URL.")
        else:
            jd, err = ui.safe_run("Ingest JD", ingest_jd,
                                  text=jd_text.strip() or None, url=jd_url.strip() or None)
            if err:
                st.error(err)
            else:
                st.session_state.jd = jd
                st.session_state.tailored = None
                st.success(f"Ingested **{jd.title or 'Unknown role'}** at "
                           f"**{jd.company or 'Unknown company'}** ({len(jd.keywords)} keywords)")
                if jd.keywords:
                    st.write("Keywords:", ", ".join(jd.keywords[:20]))

    if st.session_state.jd and ui.feature("company_research"):
        if st.button("Run company research (optional)"):
            jd = st.session_state.jd
            res, err = ui.safe_run("Company research", company_research, jd.company, jd.title, jd)
            if err:
                st.warning(err)
            else:
                st.session_state.research = res
                st.write((res or {}).get("company_summary") or "No research data (offline/blocked).")

    # --- Step 2: Tailor ---------------------------------------------------
    st.divider()
    st.subheader("2. Tailor resume")
    if st.button("Tailor resume"):
        if not st.session_state.jd:
            st.error("Ingest a JD first (step 1).")
        else:
            ui.tailor_with_fallback(profile, st.session_state.jd, st.session_state.research)

    if st.session_state.tailored:
        tr: TailoredResume = st.session_state.tailored
        st.text_area("Tailored summary", value=tr.summary, height=90, disabled=True)
        with st.expander("Tailored experience & projects", expanded=False):
            for job in tr.experience:
                st.markdown(f"**{job.title}** - {job.company}")
                for bullet in job.bullets:
                    st.markdown(f"- {bullet}")
            for proj in tr.projects:
                st.markdown(f"**{proj.name}**")
                for bullet in proj.bullets:
                    st.markdown(f"- {bullet}")

    # --- Step 3: Render + ATS --------------------------------------------
    st.divider()
    st.subheader("3. Render resume + ATS report")
    if st.button("Render resume & run ATS"):
        if not st.session_state.tailored or not st.session_state.jd:
            st.error("Tailor a resume first (step 2).")
        else:
            out_dir = ui.job_output_dir(st.session_state.jd)
            st.session_state.output_dir = out_dir
            files, err = ui.safe_run("Render resume", render_resume, st.session_state.tailored,
                                     out_dir, "resume_tailored", formats=["pdf", "txt"],
                                     settings=st.session_state.settings)
            if err:
                st.error(err)
            else:
                st.session_state.resume_files = files
                st.success(f"Resume written to `{out_dir}`")
                if files.get("pdf_note"):
                    st.info(files["pdf_note"].read_text(encoding="utf-8").strip())
            report, err2 = ui.safe_run("ATS report", ats_report,
                                       st.session_state.tailored, st.session_state.jd)
            if not err2:
                st.session_state.ats = report

    if st.session_state.ats:
        rpt = st.session_state.ats
        st.metric("ATS score", f"{rpt.score}/100")
        c1, c2 = st.columns(2)
        c1.write("**Matched keywords**")
        c1.write(", ".join(rpt.matched[:25]) or "(none)")
        c2.write("**Missing keywords**")
        c2.write(", ".join(rpt.missing[:25]) or "(none)")
        if rpt.format_warnings:
            st.warning("Format warnings: " + "; ".join(rpt.format_warnings))
        if rpt.suggestions:
            st.info("Suggestions:\n- " + "\n- ".join(rpt.suggestions[:6]))

    if st.session_state.resume_files:
        files = st.session_state.resume_files
        cols = st.columns(4)
        with cols[0]:
            ui.download_button("Resume .pdf", files.get("pdf"), "application/pdf")
        with cols[1]:
            ui.download_button("Resume .txt", files.get("txt"), "text/plain")
        with cols[2]:
            ui.download_button("Resume .html", files.get("html"), "text/html")
        with cols[3]:
            ui.download_button("Resume .tex", files.get("tex"), "application/x-tex")

    # --- Step 4: Cover letter --------------------------------------------
    if ui.feature("cover_letter"):
        st.divider()
        st.subheader("4. Cover letter")
        if st.button("Generate cover letter"):
            if not st.session_state.jd:
                st.error("Ingest a JD first.")
            else:
                out_dir = st.session_state.output_dir or ui.job_output_dir(st.session_state.jd)
                result, err = ui.safe_run("Cover letter", generate_cover_letter, profile,
                                          st.session_state.jd, st.session_state.tailored,
                                          st.session_state.research, out_dir, "cover_letter",
                                          None, st.session_state.settings)
                if err:
                    st.error(err)
                else:
                    st.session_state.cover = result
                    st.success("Cover letter generated")
                    st.text_area("Preview", value=result.get("body_text", ""),
                                 height=180, disabled=True)
        if st.session_state.cover:
            for fmt, path in st.session_state.cover.get("files", {}).items():
                if fmt == "txt":
                    ui.download_button(f"Download {path.name}", path, "text/plain")

    # --- Step 5: Recruiter email -----------------------------------------
    if ui.feature("email_draft"):
        st.divider()
        st.subheader("5. Recruiter email (.eml)")
        if st.button("Build recruiter email"):
            if not st.session_state.jd:
                st.error("Ingest a JD first.")
            elif not st.session_state.resume_files.get("txt"):
                st.error("Render resume first (step 3).")
            else:
                attach = st.session_state.resume_files.get("pdf") or st.session_state.resume_files["txt"]
                out_dir = st.session_state.output_dir or ui.job_output_dir(st.session_state.jd)
                eml, err = ui.safe_run("Email draft", build_recruiter_email, profile,
                                       st.session_state.jd, attach, st.session_state.tailored,
                                       out_dir, "recruiter_email", None, st.session_state.settings)
                if err:
                    st.error(err)
                else:
                    st.session_state.email_path = eml
                    st.success(f"Email draft saved: `{eml.name}` (resume attached)")
        if st.session_state.email_path:
            ui.download_button("Download .eml", st.session_state.email_path, "message/rfc822")

    # --- Step 6: Track ----------------------------------------------------
    st.divider()
    st.subheader("6. Save to tracker")
    if st.button("Add to tracker"):
        if not st.session_state.jd:
            st.error("Ingest a JD first.")
        else:
            jd: JobDescription = st.session_state.jd
            files = st.session_state.resume_files or {}
            cover_files = (st.session_state.cover or {}).get("files", {})
            notes = ""
            if st.session_state.offline_variant:
                ov = st.session_state.offline_variant
                notes = f"Offline variant: {ov['name']} (score {ov['score']:.2f})"
            status = "tailored" if st.session_state.tailored else "shortlisted"
            _, err = ui.safe_run(
                "Tracker", jobs_db.record_manual,
                company=jd.company or "Unknown", role=jd.title or "Unknown",
                url=jd.source_url or "", status=status,
                settings=st.session_state.settings,
                resume_file=str(files.get("pdf") or files.get("txt") or ""),
                cover_file=str(cover_files.get("txt") or ""),
                email_file=str(st.session_state.email_path or ""),
                notes=notes,
            )
            if err:
                st.error(err)
            else:
                jobs_db.export_to_xlsx(settings=st.session_state.settings)
                st.success("Saved to tracker (and exported applications.xlsx).")


try:
    _page()
except Exception as exc:  # noqa: BLE001
    st.error(f"Unexpected error: {exc}")
    with st.expander("Details"):
        st.code(traceback.format_exc())
