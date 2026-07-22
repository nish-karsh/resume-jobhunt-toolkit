# Documentation

Documentation home for the **Resume Job-Hunt Toolkit** - tailors your resume to each job with free NVIDIA NIM models, plus ATS checks, cover letters, recruiter emails, a **job searcher** with tracking, an opt-in **local apply assistant**, an offline fallback, and a **private cloud** deployment.

New here? Read in this order:

1. **[Windows Setup & Run Plan](WINDOWS_SETUP.md)** - install and launch on your PC, step by step.
2. **[User Guide](USER_GUIDE.md)** - how to use the app day to day.
3. **[Job Search & Apply](JOB_SEARCH.md)** - find, track, and apply to roles.
4. **[Deploy to Cloud](DEPLOY_CLOUD.md)** - make it a private, always-on web app.
5. **[Troubleshooting](TROUBLESHOOTING.md)** - when to reach for it.

---

## All documents

| Doc | What's inside |
|-----|---------------|
| [WINDOWS_SETUP.md](WINDOWS_SETUP.md) | Detailed Windows install/run plan: Python, Tectonic, API key, `.env`, `run.bat`, verification, one-shot PowerShell. |
| [USER_GUIDE.md](USER_GUIDE.md) | The Tailor Resume workflow, where outputs land, sending the email, offline mode, and tips. |
| [JOB_SEARCH.md](JOB_SEARCH.md) | Job sources (Adzuna/Remotive/Greenhouse/Lever), status pipeline, and the opt-in apply assistant. |
| [DEPLOY_CLOUD.md](DEPLOY_CLOUD.md) | Local vs cloud modes, Hugging Face Spaces (Docker, private), secrets, persistence, and alternatives. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Pipeline diagram, module map, data schemas, and the no-fabrication guardrail. |
| [CONFIGURATION.md](CONFIGURATION.md) | Reference for `.env`, `settings.yaml` (mode/features/job_search), and `profile.yaml`. |
| [MODELS.md](MODELS.md) | The NVIDIA NIM model chain, the `models.tailor` default, free-tier limits, and how to swap models. |
| [HOSTING.md](HOSTING.md) | Local (recommended), phone tunnel, and always-on private cloud. |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Fixes for API, PDF engines, JD scraping, environment, profile, and email/tracker issues. |

**Related (project root):**
- [../README.md](../README.md) - project overview and quick reference.
- [../GUIDE.md](../GUIDE.md) - job-hunt playbook: LinkedIn optimization, referrals, and the interview funnel.

---

## 60-second quick start

```powershell
# 1) install prerequisites (once)
winget install Python.Python.3.11
winget install TectonicProject.Tectonic

# 2) configure your free key (from build.nvidia.com)
cd C:\path\to\Resume_Automate
Copy-Item .env.example .env
notepad .env        # set NVIDIA_API_KEY=nvapi-...

# 3) run
.\run.bat           # opens http://localhost:8501
```

Then paste a job description, click through **Ingest -> Tailor -> Render+ATS -> Cover letter -> Email -> Save to tracker**, and review before sending. Full details in the [User Guide](USER_GUIDE.md).

---

## At a glance

- **Runs on:** your Windows PC (local-first, private). Linux supported for dev via `run.sh`.
- **AI:** free NVIDIA NIM, primary `nvidia/nemotron-3-super-120b-a12b` with automatic fallbacks; ~4 calls per job.
- **Offline:** TF-IDF match to six cached role variants when the API is unreachable.
- **Outputs:** tailored resume (`.pdf`/`.tex`/`.txt`), ATS report, cover letter, recruiter `.eml`, and `applications.xlsx` - all under your project folder.
- **Privacy:** `.env`, resume, and tracker are gitignored; only the model-call text ever leaves your PC.
