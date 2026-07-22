# Job Search, Tracking & Apply

The **Job Search** page finds open roles from free, legal sources, tracks them with a
status pipeline, and lets you apply to the ones **you pick** (never automatically).

Open it from the sidebar: **Job Search** (or the link on the home page).

---

## Sources (all free / legal)

| Source | What | Auth |
|--------|------|------|
| **Adzuna** | Aggregated job board, great for **India** roles. | Free `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` from [developer.adzuna.com](https://developer.adzuna.com). ~250 requests/day. |
| **Remotive** | Curated **remote** jobs. | Keyless. Jobs are delayed ~24h and attribution is required by their ToS. |
| **Greenhouse** | Public company job boards. | Keyless. Add board tokens (see below). |
| **Lever** | Public company postings. | Keyless. Add company slugs (see below). |

> There is **no LinkedIn or Naukri scraping** — it violates their terms. Paste those
> JDs into the **Tailor Resume** page instead.

### Adzuna keys

1. Register at [developer.adzuna.com](https://developer.adzuna.com) (free).
2. Put the credentials in your `.env` (local) or host secrets (cloud):
   ```env
   ADZUNA_APP_ID=your_app_id
   ADZUNA_APP_KEY=your_app_key
   ```
Without keys, Adzuna is simply skipped (you'll see a hint); the other sources still work.

### Company boards (Greenhouse / Lever)

Add tokens to `config/settings.yaml` under `job_search.company_boards`:

```yaml
job_search:
  company_boards:
    greenhouse:
      - stripe          # from boards.greenhouse.io/stripe
    lever:
      - netflix         # from jobs.lever.co/netflix
```

Find the token in the careers URL: `boards.greenhouse.io/<token>` or
`jobs.lever.co/<company>`. Company-board results are filtered to your search terms so
you only see relevant roles (a board lists *every* team).

---

## How search works

- Queries come from your box, or fall back to `job_search.default_queries` in settings.
- Results are **normalized** (title, company, location, url, date, salary), **deduped**
  across sources, **relevance-scored** against your search terms + profile skills, and
  sorted best-first.
- Every result is saved into the **job store** (`data/jobhunt.db`) as `found`, so
  re-running a search won't create duplicates and already-tracked jobs keep their status.

---

## Status pipeline

```
found → shortlisted → tailored → applied → interview → closed   (+ skipped)
```

- **Shortlist** the ones worth pursuing (multiselect → *Shortlist selected*).
- Pick one under **Work on a job** to **Tailor & render** a resume for it (status → `tailored`,
  resume path saved).
- **Apply** (see below), then set status to `applied` / `interview` / `closed` as you go.

Everything mirrors to `data/applications.xlsx` (download from the home page) so you keep
your familiar spreadsheet.

---

## Applying (only what you select)

Nothing is ever applied automatically. For a selected job you get:

- **Open apply link** — opens the posting in your browser; you fill and submit.
- **Auto-fill (local)** — *local mode only.* Opens the apply page in your **own logged-in
  browser profile**, best-effort fills name/email/phone and attaches your tailored resume,
  then **stops for your review**. It **never clicks submit**. Greenhouse/Lever forms are the
  most reliable; other forms may only partially fill — just complete and submit yourself.

Auto-fill requires the local extras:

```powershell
pip install -r requirements-local.txt
python -m playwright install chromium
```

The first time, log in to the job sites in the window that opens; the session is saved to a
persistent profile (`.browser_profile/`) for next time.

In **cloud mode** there is no server-side browser, so only **Open apply link** is available.

---

## Privacy

- Search queries go to the free APIs listed above; job data is stored locally in
  `data/jobhunt.db`.
- The apply assistant runs on **your** machine with **your** browser profile and pauses
  before submitting. Review every field before you send anything.
