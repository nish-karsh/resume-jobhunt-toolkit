# Configuration Reference

Everything you can tune lives in three places: `.env` (secret key), `config/settings.yaml` (behavior), and `config/profile.yaml` (your resume/identity).

---

## `.env` - your API key

Create it from the template (`Copy-Item .env.example .env`) and set one line:

```env
NVIDIA_API_KEY=nvapi-your-actual-key-here
```

- Loaded at startup by `app.py` via `python-dotenv`.
- Gitignored - never committed or uploaded.
- Get a key from [build.nvidia.com](https://build.nvidia.com) (see [MODELS.md](MODELS.md)).

---

## `config/settings.yaml` - behavior

```yaml
base_url: https://integrate.api.nvidia.com/v1

mode: local                 # local | cloud (override: SETTINGS__MODE=cloud)

features:
  pdf_engine: auto          # auto | latex | weasyprint | fpdf
  job_search: true
  apply_autofill: true      # local only; forced off in cloud mode
  company_research: true
  cover_letter: true
  email_draft: true

apply:
  browser_profile_dir: ""   # empty -> <project>/.browser_profile

models:
  primary: nvidia/nemotron-3-super-120b-a12b
  tailor: meta/llama-3.3-70b-instruct   # dedicated tailoring model (see MODELS.md)
  fallbacks:
    - nvidia/llama-3.3-nemotron-super-49b-v1.5
    - meta/llama-3.3-70b-instruct
  utility: nvidia/nemotron-3-nano-30b-a3b
  high_end_alt: qwen/qwen3.5-397b-a17b

job_search:
  enabled_sources: [adzuna, remotive, greenhouse, lever]
  adzuna_country: in
  results_per_source: 25
  max_days_old: 30
  default_location: India
  default_queries: [Design Verification Engineer, ASIC Verification Engineer, VLSI Engineer]
  company_boards:
    greenhouse: []          # tokens from boards.greenhouse.io/<token>
    lever: []               # slugs from jobs.lever.co/<company>

# ... rate_limit_rpm, request_timeout_s, max_retries, export, smtp ...

paths:
  seed_resume: data/seed_resume.pdf
  profile_yaml: config/profile.yaml
  profile_cache_json: data/profile_cache.json
  output_dir: resumes/output
  variants_dir: resumes/variants
  tracker_xlsx: data/applications.xlsx
  jobs_db: data/jobhunt.db
  templates_dir: templates
```

| Key | Meaning |
|-----|---------|
| `base_url` | OpenAI-compatible NIM endpoint. Change only if you self-host or use another compatible provider. |
| `mode` | `local` (all features, Tectonic + auto-fill) or `cloud` (password-gated, HTML→PDF, apply = open link). |
| `features.pdf_engine` | `auto` picks Tectonic → WeasyPrint → fpdf2. Force one with `latex`/`weasyprint`/`fpdf`. |
| `features.*` | Toggle job search, local auto-fill, company research, cover letter, email. |
| `apply.browser_profile_dir` | Where the local auto-fill browser stores your login session. |
| `models.primary` | Main writing/reasoning model (non-tailoring). |
| `models.tailor` | Dedicated resume-tailoring model. Defaults to a reliable instruct model to avoid truncation. |
| `models.fallbacks` | Tried in order when a model fails (429/503/timeout). |
| `job_search.*` | Sources, country, freshness, default queries, and company-board tokens. |
| `rate_limit_rpm` / `request_timeout_s` / `max_retries` | Free-tier pacing and retry behavior. |
| `export.*` | Output formats; `.tex`/`.html`/`.txt` are always written, `pdf` uses the engine above. |
| `smtp.*` | Optional email sending; `enabled: false` = draft-only (`.eml`). |
| `paths.*` | Input/output locations. When `DATA_DIR` is set, `output_dir`, `tracker_xlsx`, and `jobs_db` live under it (cloud persistence). |

See [MODELS.md](MODELS.md) for how to change models safely.

### Environment overrides

Any setting can be overridden with an environment variable using **double-underscore nesting**, which is handy for temporary experiments without editing the file:

```powershell
# Use the high-end alternative as primary for one session
$env:SETTINGS__MODELS__PRIMARY = "qwen/qwen3.5-397b-a17b"
streamlit run app.py
```

Examples: `SETTINGS__BASE_URL`, `SETTINGS__RATE_LIMIT_RPM`, `SETTINGS__MODELS__UTILITY`. The API key is set separately via `NVIDIA_API_KEY`.

---

## `config/profile.yaml` - your resume & identity

This is the source of truth for your resume content. It is auto-generated from `data/seed_resume.pdf` on first run, then you refine it. Top-level fields:

| Field | Notes |
|-------|-------|
| `identity` | `name`, `email`, `phone`, `location` *(TODO)*, `linkedin`, `github`, `portfolio_links[]` |
| `summary` | Your professional summary (the tailor rewrites a copy per job; this stays as your base). |
| `skills` | Category -> list of skills (e.g. `Technical`, `Embedded Hardware`, `Laboratory`). |
| `experience[]` | `company`, `title`, `location`, `start`, `end`, `bullets[]`. |
| `projects[]` | `name`, `link`, `tech[]`, `bullets[]`. |
| `education[]` | `institution`, `degree`, `field`, `start`, `end`, `gpa`, `location`. |
| `certifications[]`, `achievements[]` | Plain lists. |
| `bullet_bank[]` | Auto-built reusable bullets (`id`, `text`, `tags[]`, `source`, `has_metric`). Regenerated when you re-parse. |
| `target_domain` | `primary`, `secondary[]`, `locations[]` - guides tailoring and which offline variants exist. |
| `current_city` | *TODO* |
| `target_titles` | *TODO* |
| `notice_period` | *TODO* |
| `from_email` | The "from" address used in email drafts (defaults to your resume email). |

### The four `TODO` fields

Fill these via the app **sidebar -> Profile -> Save profile fields**, or edit the file directly:

- `identity.location`
- `current_city`
- `target_titles`
- `notice_period`

### Editing tips

- For **permanent** resume changes, edit `profile.yaml` (or update `data/seed_resume.pdf` and re-parse). Per-job tailoring reads from here.
- After editing skills/experience, consider rebuilding the offline variants: `python -m src.variant_library --build`.
- Keep everything **truthful** - the tailoring guardrail only reuses what is here; it will not invent anything to fill gaps.

---

## What is safe to commit

`.gitignore` already excludes your secrets and personal data: `.env`, the `nvapi` key file, `.streamlit/secrets.toml`, resume PDFs, `data/*.xlsx`, `data/*.db`, `resumes/output/`, and `.browser_profile/`. Configuration files (`settings.yaml`) and code are safe to version; treat `profile.yaml` as personal (it contains your contact details).
