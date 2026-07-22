"""Local-only apply assistant. Opt-in, per-job, and never auto-submits.

Two modes:
1. ``open_link``  - open the application URL in your default browser (you fill + submit).
2. ``autofill``   - best-effort auto-fill using Playwright and YOUR logged-in browser
                    profile, then leave the window open for you to REVIEW and submit.
                    It never clicks the submit button.

Auto-fill is best-effort because every application form differs. Greenhouse and Lever
hosted forms (the same sources the searcher uses) are the most reliable targets. If
auto-fill is unavailable or fails, we fall back to just opening the link.

This module is intended for the local build only. In cloud mode there is no
server-side browser, so the UI restricts apply to ``open_link``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import webbrowser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from src.settings_loader import load_settings, project_root


@dataclass
class Applicant:
    name: str = ""
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    location: str = ""

    @classmethod
    def from_profile(cls, profile: Any) -> "Applicant":
        ident = profile.identity
        parts = (ident.name or "").split()

        def clean(value: str) -> str:
            return "" if (not value or value == "TODO") else value

        return cls(
            name=ident.name or "",
            first_name=parts[0] if parts else "",
            last_name=" ".join(parts[1:]) if len(parts) > 1 else "",
            email=clean(ident.email),
            phone=clean(ident.phone),
            linkedin=ident.linkedin or "",
            github=ident.github or "",
            location=clean(ident.location),
        )


def open_link(url: str) -> bool:
    """Open a URL in the default browser. Returns True if it was launched."""
    if not url:
        return False
    try:
        return webbrowser.open(url, new=2)
    except Exception:  # noqa: BLE001
        return False


def playwright_available() -> bool:
    try:
        import playwright  # noqa: F401
    except Exception:
        return False
    return True


def _browser_profile_dir(settings: Optional[dict[str, Any]]) -> Path:
    cfg = settings or load_settings()
    raw = (cfg.get("apply", {}) or {}).get("browser_profile_dir") or str(
        project_root() / ".browser_profile"
    )
    path = Path(raw).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def launch_autofill(
    url: str,
    resume_path: str | Path | None,
    applicant: Applicant,
    settings: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Start a NON-BLOCKING browser session to auto-fill a form for review.

    Spawns a detached worker process (so Streamlit stays responsive) that opens the
    apply URL in your persistent browser profile, fills common fields, attaches the
    resume, and waits for you to review/submit. Falls back to ``open_link`` when
    Playwright is not installed.
    """
    if not url:
        return {"started": False, "mode": "none", "message": "No application URL for this job."}

    if not playwright_available():
        opened = open_link(url)
        return {
            "started": opened,
            "mode": "open_link",
            "message": (
                "Playwright is not installed, so I opened the apply link in your browser. "
                "Install it for auto-fill: pip install playwright && python -m playwright install chromium"
            ),
        }

    payload = {
        "url": url,
        "resume": str(resume_path or ""),
        "applicant": asdict(applicant),
        "profile_dir": str(_browser_profile_dir(settings)),
    }
    try:
        proc = subprocess.Popen(  # noqa: S603 - trusted local invocation
            [sys.executable, "-m", "src.apply_assist", "--run", json.dumps(payload)],
            cwd=str(project_root()),
        )
        return {
            "started": True,
            "mode": "autofill",
            "message": (
                f"Opening a browser to auto-fill this application (pid {proc.pid}). "
                "Review every field, then submit it yourself - nothing is submitted automatically."
            ),
        }
    except Exception as exc:  # noqa: BLE001
        opened = open_link(url)
        return {
            "started": opened,
            "mode": "open_link",
            "message": f"Auto-fill could not start ({exc}); opened the apply link instead.",
        }


# ---------------------------------------------------------------------------
# Worker (runs inside the spawned subprocess; uses Playwright sync API)
# ---------------------------------------------------------------------------

# (value_key, [candidate CSS selectors]) - ordered from most to least specific.
_TEXT_FIELDS: list[tuple[str, list[str]]] = [
    ("email", ["input[type=email]", "input[name*=email i]", "#email"]),
    ("phone", ["input[type=tel]", "input[name*=phone i]", "#phone"]),
    ("first_name", ["input[name*=first i]", "#first_name"]),
    ("last_name", ["input[name*=last i]", "#last_name"]),
    ("name", ["input[name=name]", "input[name*=full i]", "input[id*=name i]"]),
    ("linkedin", ["input[name*=linkedin i]", "input[name*=urls i]"]),
    ("github", ["input[name*=github i]"]),
    ("location", ["input[name*=location i]", "input[name*=city i]"]),
]


def _fill_form(page: Any, applicant: dict[str, Any], resume: str) -> list[str]:
    filled: list[str] = []
    for key, selectors in _TEXT_FIELDS:
        value = applicant.get(key) or ""
        if not value:
            continue
        for selector in selectors:
            try:
                loc = page.locator(selector).first
                if loc.count() and loc.is_visible():
                    loc.fill(value, timeout=2000)
                    filled.append(key)
                    break
            except Exception:  # noqa: BLE001
                continue
    if resume and Path(resume).exists():
        try:
            file_input = page.locator("input[type=file]").first
            if file_input.count():
                file_input.set_input_files(resume, timeout=3000)
                filled.append("resume")
        except Exception:  # noqa: BLE001
            pass
    return filled


def _run(payload: dict[str, Any]) -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            payload["profile_dir"], headless=False
        )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto(payload["url"], wait_until="domcontentloaded", timeout=45000)
        except Exception as exc:  # noqa: BLE001
            print(f"navigation error: {exc}")

        try:
            filled = _fill_form(page, payload.get("applicant", {}), payload.get("resume", ""))
            print("auto-filled fields:", ", ".join(filled) or "(none matched)")
        except Exception as exc:  # noqa: BLE001
            print(f"auto-fill error: {exc}")

        print("Review the form and submit it yourself. Close the window when done.")
        # Keep the window open for review; never submit. Return when the user closes it.
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:  # noqa: BLE001
            time.sleep(1800)
        try:
            context.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Local apply assistant worker")
    parser.add_argument("--run", help="JSON payload (internal use)")
    args = parser.parse_args()
    if args.run:
        return _run(json.loads(args.run))
    print("This module is invoked by the app; nothing to do without --run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
