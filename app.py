"""Resume Job-Hunt Toolkit - home page.

Streamlit multipage app. The detailed flows live in ``pages/``:
- 1_Tailor_Resume : paste a JD -> tailor -> ATS -> cover letter -> email -> track
- 2_Job_Search    : search open roles -> select -> tailor -> apply (opt-in) -> track
"""

from __future__ import annotations

import traceback

import streamlit as st

from src import jobs_db
from src import ui_common as ui
from src.settings_loader import resolve_path

ui.bootstrap("Resume Job-Hunt Toolkit")
ui.sidebar()


def _home() -> None:
    st.title("Resume Job-Hunt Toolkit")
    st.caption(f"Private, AI-assisted job hunt - running in **{ui.mode()}** mode.")

    if st.session_state.profile is None:
        st.error(getattr(st.session_state, "profile_error", "Could not load profile."))
        return

    profile = st.session_state.profile
    st.write(f"Welcome, **{profile.identity.name or 'there'}**. Pick a tool to start:")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Tailor a resume")
        st.write("Paste a specific job description, generate a tailored resume + ATS "
                 "report, cover letter, and a ready-to-send recruiter email.")
        st.page_link("pages/1_Tailor_Resume.py", label="Open Tailor Resume", icon="✍️")
    with col2:
        st.subheader("Search jobs")
        if ui.feature("job_search"):
            st.write("Find open roles from free sources (Adzuna, Remotive, company "
                     "boards), track them, and apply to the ones you pick.")
            st.page_link("pages/2_Job_Search.py", label="Open Job Search", icon="🔎")
        else:
            st.info("Job search is disabled in settings (`features.job_search`).")

    st.divider()
    st.subheader("Your pipeline")
    try:
        counts = jobs_db.stats(settings=st.session_state.settings)
    except Exception as exc:  # noqa: BLE001
        counts = {}
        st.warning(f"Could not read job store: {exc}")

    if counts:
        order = ["found", "shortlisted", "tailored", "applied", "interview", "closed"]
        cols = st.columns(len(order))
        for col, key in zip(cols, order):
            col.metric(key.capitalize(), counts.get(key, 0))

        recent = jobs_db.list_jobs(settings=st.session_state.settings)[:15]
        rows = [
            {
                "Company": j["company"],
                "Role": j["title"],
                "Status": j["status"],
                "Source": j["source"],
                "Posted": j["posted_at"],
            }
            for j in recent
        ]
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)

        xlsx = resolve_path("tracker_xlsx", st.session_state.settings)
        if not xlsx.exists():
            jobs_db.export_to_xlsx(settings=st.session_state.settings)
        ui.download_button("Download applications.xlsx", xlsx,
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("No jobs tracked yet. Start from Tailor Resume or Job Search.")


try:
    _home()
except Exception as exc:  # noqa: BLE001
    st.error(f"Unexpected error: {exc}")
    with st.expander("Details"):
        st.code(traceback.format_exc())
