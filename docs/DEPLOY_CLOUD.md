# Deploy to the Cloud (free + private)

Run the toolkit as an always-available, **password-protected** web app you can reach from
any device — without leaving your PC on. The recommended **free** host is
**Streamlit Community Cloud**; Render and Google Cloud Run are Docker-based alternatives.

---

## Two versions, one codebase

The app runs in one of two **modes** (set `mode:` in `config/settings.yaml`, or the
`SETTINGS__MODE` env var / secret):

| | `local` | `cloud` |
|---|---------|---------|
| Tailor / ATS / cover / email | Yes | Yes |
| Job search + tracker | Yes | Yes |
| PDF engine | Tectonic → WeasyPrint → fpdf2 | WeasyPrint → fpdf2 (portable) |
| Apply assistant | Browser auto-fill (review-before-submit) | **Open link only** (no server browser) |
| Access | localhost | **Password gate** (`app_password`) |
| Data | project folder | `$DATA_DIR`, or ephemeral (use the in-app backup/restore) |

---

## Secrets

Set these in your host's secret store (never commit them):

| Key | Required | Purpose |
|-----|----------|---------|
| `NVIDIA_API_KEY` | Yes | AI tailoring / cover letters. |
| `app_password` (or `APP_PASSWORD`) | Strongly recommended | Password gate for the whole app. |
| `SETTINGS__MODE` | On Streamlit Cloud | Set to `"cloud"` to enable cloud mode (no Docker there to set env vars). |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Optional | Adzuna job search. |
| `SMTP_HOST/PORT/USER/PASS` | Optional | Sending recruiter emails. |

Locally, copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml`, or use `.env`.

---

## Step 1 - Push to a private GitHub repo

Streamlit Community Cloud deploys from GitHub, so the code needs to live in a **private** repo.

```bash
cd Resume_Automate
git init -b main
git add .
git commit -m "Resume Job-Hunt Toolkit"

# Option 1 - GitHub CLI:
gh repo create <user>/resume-jobhunt-toolkit --private --source=. --push

# Option 2 - create an empty PRIVATE repo in the browser, then:
git remote add origin https://github.com/<user>/resume-jobhunt-toolkit.git
git push -u origin main
```

The `.gitignore` keeps secrets and runtime data out of the repo (`.env`,
`.streamlit/secrets.toml`, `data/*.db`, `data/*.xlsx`, `resumes/output/`, root resume PDFs).
`config/profile.yaml` **is** committed (it's your resume data) — fine for a private repo.

---

## Step 2 - Deploy on Streamlit Community Cloud (free, private)

1. Go to [share.streamlit.io](https://share.streamlit.io) and **sign in with GitHub**
   (authorize access to your private repositories).
2. **Create app → Deploy from GitHub** → pick your repo, branch `main`, main file `app.py`.
   Deploying from a private repo keeps the app private (one free private app per account).
3. Open **Advanced settings → Secrets** and paste (TOML):
   ```toml
   NVIDIA_API_KEY = "nvapi-...your key..."
   app_password   = "choose-a-strong-password"
   SETTINGS__MODE = "cloud"
   # optional job-search keys:
   # ADZUNA_APP_ID  = "..."
   # ADZUNA_APP_KEY = "..."
   ```
4. **Deploy**. The first build installs `requirements.txt` (a few minutes). The app bridges
   `st.secrets` into the environment automatically, so cloud mode + the password gate turn on.
5. Open the app URL, enter your password, and use it like the local app.

**Notes**
- **PDFs use fpdf2** here (no system libraries needed). For the nicer WeasyPrint output, add a
  `packages.txt` at the repo root with these apt packages (one per line): `libpango-1.0-0`,
  `libpangocairo-1.0-0`, `libgdk-pixbuf-2.0-0`, `libcairo2`, `shared-mime-info`, and add
  `weasyprint>=60` to `requirements.txt`.
- **Storage is ephemeral** (resets when the app reboots or sleeps). Use the **Backup / restore
  tracker** control on the Job Search page to download `jobhunt.db` and re-upload it later.

---

## Alternatives (Docker, full WeasyPrint PDFs)

The repo's `Dockerfile` sets `mode=cloud`, `DATA_DIR=/data`, and installs WeasyPrint's system
libraries. Both hosts below build from it and read `$PORT`.

### Render (free web service)
- New → **Web Service** → build from the repo's `Dockerfile` → set env vars
  (`NVIDIA_API_KEY`, `APP_PASSWORD`, `SETTINGS__MODE=cloud`). The free tier spins down when idle
  (~50s cold start) and has no free persistent disk; add a paid **Disk** mounted at `/var/data`
  and set `DATA_DIR=/var/data` to persist the tracker.

### Google Cloud Run (free tier)
- `gcloud run deploy --source .` (needs a Google account with billing enabled; usage stays
  within the free tier for personal use). Scales to zero. Set the same env vars; use a mounted
  volume or Cloud Storage for persistence.

> Hugging Face **Docker** Spaces now require a paid PRO plan (only static Spaces are free), so
> they are no longer a free option for this app.

---

## Local test of the cloud image

If you have Docker locally:

```bash
docker build -t resume-toolkit .
docker run --rm -p 7860:7860 \
  -e NVIDIA_API_KEY=nvapi-... \
  -e APP_PASSWORD=changeme \
  -v "$PWD/clouddata:/data" \
  resume-toolkit
# open http://localhost:7860
```

---

## Privacy note

In the cloud, your resume/profile and the text of AI calls are processed on the host you
choose. Keep the **repo private**, always set `app_password`, and prefer your own private
deployment over public ones. The browser auto-fill assistant is disabled in the cloud by design.
