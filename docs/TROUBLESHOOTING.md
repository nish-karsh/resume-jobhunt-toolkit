# Troubleshooting

Fixes for the most common issues, grouped by symptom. If the app shows an error box with a **Details** expander, open it - the traceback usually points at the cause.

---

## API / models

### Sidebar says "Offline mode"
The app cannot reach NVIDIA NIM. Causes and fixes:
- **No/invalid key:** confirm `.env` has `NVIDIA_API_KEY=nvapi-...`. Test with `python -m src.nim_client --smoke`.
- **No internet / firewall/VPN:** verify you can reach `https://integrate.api.nvidia.com`. Corporate networks may block it.
- Offline mode is a *feature*, not a crash - you still get a cached-variant resume. Restore connectivity for full AI tailoring.

### `429 Too Many Requests`
You exceeded ~40 requests/min (free tier). The client already retries with exponential backoff. Wait 1-2 minutes, and space out large batches (e.g. don't rebuild variants and tailor several jobs in the same minute).

### `503` / worker or capacity limit on the primary model
Normal during peak load on the 120B model. The app **automatically falls back** to `nvidia/llama-3.3-nemotron-super-49b-v1.5`, then `meta/llama-3.3-70b-instruct`. No action needed. To avoid it entirely, set a smaller model as primary (see [MODELS.md](MODELS.md)).

### A model slug returns "not found"
NVIDIA rotates its catalog. List current models with `python -m src.nim_client`, pick a live slug, and update `config/settings.yaml`.

---

## PDF / Tectonic

### "Tectonic not found" / no PDF produced
- Install Tectonic and open a **new** terminal so PATH updates (see [WINDOWS_SETUP.md](WINDOWS_SETUP.md#step-2---install-tectonic-latex---pdf)). Verify with `tectonic --version`.
- Without Tectonic the app still writes `resume_tailored.tex` and `.txt`, plus a `*.pdf_note.txt` with instructions. You can compile the `.tex` on [Overleaf](https://www.overleaf.com) instead.

### PDF compilation fails on special characters
The renderer sanitizes LaTeX special characters and strips emojis/non-Latin glyphs (e.g. the stray 🔗 in some resume bullets) before compiling. If a specific character still breaks compilation, remove it from `config/profile.yaml` and re-tailor. (On this project's Linux dev box Tectonic cannot run at all due to a missing system library - that is expected; it works on Windows.)

---

## Job descriptions

### JD URL ingest fails or returns junk
LinkedIn, Naukri, Indeed, and many company portals block automated fetching. This is expected. **Paste the full JD text** into the "Paste JD text" box instead - it is the reliable path and gives better keyword extraction anyway.

---

## Python / environment

### `run.bat` can't create the venv
Ensure Python 3.11+ is installed and on PATH (`py -3.11 --version`). If `py` is missing, `run.bat` falls back to `python -m venv venv`; make sure `python --version` works.

### `ModuleNotFoundError` (e.g. streamlit, yaml, pdfplumber)
The venv isn't active or dependencies aren't installed:
```powershell
venv\Scripts\activate
pip install -r requirements.txt
```
Always run from the project root so `src` imports resolve.

### `streamlit` isn't recognized
Activate the venv first (`venv\Scripts\activate`), or run via `python -m streamlit run app.py`.

### Port 8501 already in use
Another Streamlit instance is running. Close it, or start on another port: `streamlit run app.py --server.port 8502`.

### The browser didn't open
Open `http://localhost:8501` manually. The URL is also printed in the launcher terminal.

---

## Profile / content

### Profile is empty or fields look wrong
Re-parse your resume: replace `data/seed_resume.pdf` if needed, then run `python -m src.resume_parser` (or use the sidebar **Reload from seed PDF**). Then fix any `TODO` fields and mis-parsed entries directly in `config/profile.yaml`.

### Tailored resume is missing something true
The guardrail only reuses content already in `profile.yaml`. If a real skill/bullet is missing from the output, make sure it exists in your profile (add it truthfully), then re-tailor.

### Offline variants feel stale
Rebuild them after major profile edits: `python -m src.variant_library --build`.

---

## Email / tracker

### "Render resume first" when building the email
Step 5 attaches the rendered resume, so run **Step 3 (Render + ATS)** before **Step 5 (Build recruiter email)**.

### The `.eml` won't open / send
Open it with Outlook, Thunderbird, or Windows Mail. Add the recruiter's address, review, and send - the app never auto-sends. The tailored resume is already attached.

### `applications.xlsx` is locked
Close the file in Excel before clicking **Add to applications.xlsx** (Excel locks open files for writing).

---

## Still stuck?

- Re-run the smoke checks: `python -m src.nim_client --smoke` and `python -m src.resume_parser`.
- Confirm you are in the project root with the venv active.
- Check the **Details** expander in the app's error box for the traceback.
