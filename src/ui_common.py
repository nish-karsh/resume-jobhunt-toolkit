"""Shared Streamlit helpers for the multipage app (home + Tailor + Job Search)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional

import streamlit as st
import yaml
from dotenv import load_dotenv

from src.nim_client import NimClient, NimClientError
from src.resume_parser import ensure_profile, load_profile
from src.schemas import JobDescription, MasterProfile
from src.settings_loader import (
    app_mode,
    feature_enabled,
    load_settings,
    project_root,
    resolve_path,
)
from src.tailor import TailorError, tailor_resume
from src.variant_library import load_variant_tailored, match_variant

_PAGE_ICON = "📄"


def rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    else:  # older Streamlit
        st.experimental_rerun()


_rerun = rerun  # backwards-compatible alias


_SECRET_KEYS = [
    "NVIDIA_API_KEY", "NVIDIA_API_BASE", "ADZUNA_APP_ID", "ADZUNA_APP_KEY",
    "APP_PASSWORD", "DATA_DIR", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS",
    # Lets a host (e.g. Streamlit Community Cloud, which has no Docker/env editor)
    # switch the app to cloud mode by adding SETTINGS__MODE="cloud" to its secrets.
    "SETTINGS__MODE",
]


def _bridge_secrets() -> None:
    """Copy st.secrets into the environment (Streamlit Cloud) so modules that read
    os.environ (NIM client, Adzuna) work the same as on hosts that inject env vars."""
    try:
        for key in _SECRET_KEYS:
            value = st.secrets.get(key)  # type: ignore[attr-defined]
            if value and not os.environ.get(key):
                os.environ[key] = str(value)
    except Exception:  # noqa: BLE001 - no secrets file present
        pass


def bootstrap(page_title: str) -> None:
    """First call on every page: set config, load env, init state, gate access."""
    st.set_page_config(page_title=page_title, page_icon=_PAGE_ICON, layout="wide")
    load_dotenv(project_root() / ".env")
    _bridge_secrets()
    init_session()
    require_auth()


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


def _app_password() -> str:
    try:
        secret = st.secrets.get("app_password", "")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - no secrets file present
        secret = ""
    return str(
        secret
        or os.environ.get("APP_PASSWORD")
        or os.environ.get("app_password")
        or ""
    )


def require_auth() -> None:
    """Show a password gate when an app password is configured; else pass through."""
    password = _app_password()
    if not password or st.session_state.get("_authed"):
        return
    st.title("Private access")
    st.caption("This deployment is password protected.")
    entered = st.text_input("Password", type="password")
    if st.button("Enter"):
        if entered == password:
            st.session_state._authed = True
            _rerun()
        else:
            st.error("Incorrect password.")
    st.stop()


# ---------------------------------------------------------------------------
# Session / status
# ---------------------------------------------------------------------------


def feature(name: str, default: bool = True) -> bool:
    return feature_enabled(st.session_state.settings, name, default)


def mode() -> str:
    return app_mode(st.session_state.settings)


def init_session() -> None:
    ss = st.session_state
    if "settings" not in ss:
        ss.settings = load_settings()
    if "profile" not in ss:
        try:
            ss.profile = ensure_profile(ss.settings)
        except Exception as exc:  # noqa: BLE001
            ss.profile = None
            ss.profile_error = str(exc)
    ss.setdefault("jd", None)
    ss.setdefault("research", None)
    ss.setdefault("tailored", None)
    ss.setdefault("offline_variant", None)
    ss.setdefault("ats", None)
    ss.setdefault("cover", None)
    ss.setdefault("email_path", None)
    ss.setdefault("resume_files", {})
    ss.setdefault("output_dir", None)
    ss.setdefault("job_results", [])
    ss.setdefault("search_warnings", [])


def nim_status() -> dict[str, Any]:
    try:
        client = NimClient(st.session_state.settings)
        reachable = client.is_reachable()
        return {
            "reachable": reachable,
            "model": client.model_chain[0] if reachable else "",
            "error": "",
        }
    except NimClientError as exc:
        return {"reachable": False, "model": "", "error": str(exc)}


def safe_run(label: str, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{label} failed: {exc}"


# ---------------------------------------------------------------------------
# Profile sidebar (shared)
# ---------------------------------------------------------------------------


def _load_profile_yaml_extra() -> dict[str, Any]:
    path = resolve_path("profile_yaml", st.session_state.settings)
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _save_profile_fields(location: str, city: str, titles: str, notice: str) -> None:
    path = resolve_path("profile_yaml", st.session_state.settings)
    data = _load_profile_yaml_extra()
    data.setdefault("identity", {})
    data["identity"]["location"] = location or "TODO"
    data["current_city"] = city or "TODO"
    data["target_titles"] = titles or "TODO"
    data["notice_period"] = notice or "TODO"
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)
    st.session_state.profile = load_profile(path)


def sidebar() -> None:
    st.sidebar.title("Resume Toolkit")
    st.sidebar.caption(f"Mode: **{mode()}**")

    status = nim_status()
    if status["reachable"]:
        st.sidebar.success(f"NIM online - {status['model']}")
    else:
        st.sidebar.warning(f"Offline - {status['error'] or 'NIM unreachable'}")

    with st.sidebar.expander("Profile fields", expanded=False):
        extra = _load_profile_yaml_extra()
        identity = extra.get("identity", {})

        def clean(value: Any) -> str:
            return "" if (not value or value == "TODO") else str(value)

        loc = st.text_input("Location", value=clean(identity.get("location")),
                            placeholder="e.g. Bangalore, India")
        city = st.text_input("Current city", value=clean(extra.get("current_city")),
                            placeholder="e.g. Noida")
        titles = st.text_input("Target titles", value=clean(extra.get("target_titles")),
                            placeholder="DV Engineer, Verification Engineer")
        notice = st.text_input("Notice period", value=clean(extra.get("notice_period")),
                            placeholder="Immediate / 30 days")
        if st.button("Save profile fields"):
            _save_profile_fields(loc, city, titles, notice)
            st.success("Saved to profile.yaml")


# ---------------------------------------------------------------------------
# Downloads / paths
# ---------------------------------------------------------------------------


def download_button(label: str, path: Optional[Path], mime: str = "") -> None:
    if not path or not Path(path).exists():
        return
    path = Path(path)
    st.download_button(
        label,
        data=path.read_bytes(),
        file_name=path.name,
        mime=mime or "application/octet-stream",
        key=f"dl_{path.name}_{path.stat().st_mtime_ns}",
    )


def slug(text: str, fallback: str = "job") -> str:
    value = re.sub(r"[^\w\-]+", "_", (text or fallback).strip())[:50]
    return value.strip("_") or fallback


def job_output_dir(jd: JobDescription) -> Path:
    company = slug(jd.company, "company")
    role = slug(jd.title, "role")
    return resolve_path("output_dir", st.session_state.settings) / f"{company}_{role}"


# ---------------------------------------------------------------------------
# Tailoring with offline fallback (shared by both pages)
# ---------------------------------------------------------------------------


def tailor_with_fallback(
    profile: MasterProfile,
    jd: JobDescription,
    research: Optional[dict],
) -> None:
    st.session_state.offline_variant = None
    status = nim_status()

    if status["reachable"]:
        tailored, err = safe_run("Tailor resume", tailor_resume, profile, jd, research)
        if tailored:
            st.session_state.tailored = tailored
            st.success(f"Resume tailored online (model: {tailored.meta.model_used})")
            return
        st.warning(f"Online tailoring failed: {err}. Trying offline variant match...")

    try:
        variant_name, variant_path, score = match_variant(jd, st.session_state.settings)
        tailored = load_variant_tailored(variant_name, st.session_state.settings)
        tailored.meta.job_title = jd.title or tailored.meta.job_title
        tailored.meta.company = jd.company or tailored.meta.company
        tailored.meta.model_used = f"offline:{variant_name}"
        st.session_state.tailored = tailored
        st.session_state.offline_variant = {
            "name": variant_name,
            "path": str(variant_path),
            "score": score,
        }
        st.info(
            f"**Offline fallback** - closest cached variant `{variant_name}` "
            f"(score {score:.2f})."
        )
    except (TailorError, Exception) as exc:  # noqa: BLE001
        st.error(f"Both online and offline tailoring failed: {exc}")
