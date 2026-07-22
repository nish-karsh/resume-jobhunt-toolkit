# User Guide

How to use the **Resume Job-Hunt Toolkit** day to day. If you have not installed it yet, start with the [Windows Setup & Run Plan](WINDOWS_SETUP.md).

---

## Launching

Double-click `run.bat` (Windows) or run `./run.sh` (Linux). The app opens at `http://localhost:8501`. Keep the launcher terminal open while you work; close it to stop the app.

---

## Screen layout

The app has two parts:

- **Sidebar (left)** - status, your profile, and resume source.
- **Main panel (right)** - the job description input and the 6 numbered steps.

### Sidebar

| Control | What it does |
|--------|--------------|
| **NIM status** | Green **"NIM online - `<model>`"** means AI tailoring is available. Yellow **"Offline mode"** means the app will use the local cached-variant fallback. |
| **Profile fields** | Edit `Location`, `Current city`, `Target titles`, `Notice period`, then click **Save profile fields** to write them to `config/profile.yaml`. |
| **Resume source** | Use the **Default seed PDF** (`data/seed_resume.pdf`) or **Upload new PDF** and click **Parse uploaded resume**. **Reload from seed PDF** re-parses the default if you replaced the file. |

---

## The workflow

At the top of the main panel, provide the job description:

- **Paste JD text (primary)** - the most reliable input. Paste the full posting, including the requirements/qualifications section.
- **Or JD URL (best-effort)** - the app will try to fetch the page, but LinkedIn, Naukri, and many portals block automated fetching. If it fails, just paste the text - this is expected and normal.

Then work through the steps. Each step's output is remembered for the session, so you can run them in order.

### 1. Ingest JD + company research

Click **Ingest JD**. The app extracts the role title, company, and keywords and shows a summary (e.g. *"Ingested: VLSI Design Verification Engineer at Qualcomm India (18 keywords)"*).

Optionally click **Run company research** for extra context that improves tailoring. This makes a small online call and is skipped gracefully if you are offline or the lookup is blocked.

### 2. Tailor resume

Click **Tailor resume**. The tailoring engine:

- Reorders your **skills** to surface the ones the JD asks for.
- Selects and rephrases the most relevant **bullets** for each role/project.
- Rewrites your **summary** to target the role.

It enforces a strict **no-fabrication guardrail**: it can only reuse and rephrase experience that is already in your resume - it never invents employers, titles, dates, degrees, tools, or metrics (see [ARCHITECTURE.md](ARCHITECTURE.md#no-fabrication-guardrail)).

- **Online:** you'll see *"Resume tailored online (model: ...)"*.
- **Offline fallback:** if NIM is unreachable, the app automatically matches your JD to the closest of six pre-built variants and labels it clearly, e.g. *"Offline fallback - closest cached variant: `design_verification` (TF-IDF score 0.34)"*.

The tailored summary is shown in a preview box.

### 3. Render + ATS report

Click **Render resume & run ATS**. This writes the resume files and computes your ATS match:

- Files go to `resumes/output/<Company>_<Role>/` as `resume_tailored.tex`, `.txt`, and `.pdf` (if Tectonic is installed; otherwise a `*.pdf_note.txt` tells you how to get the PDF).
- The **ATS score** (0-100) is shown along with **matched** and **missing** keywords, any **format warnings**, and **suggestions**.

Use the missing-keyword list to decide whether to add genuinely-true skills/keywords to your master resume (`config/profile.yaml`) and re-tailor.

### 4. Cover letter

Click **Generate cover letter**. A tailored letter is produced (grounded in your profile + the JD) and shown as a preview. It is saved to the job output folder as `.txt`, `.md`, and `.tex` (plus `.pdf` if Tectonic is installed); the app offers the `.txt` as a download button.

### 5. Recruiter email (`.eml`)

Click **Build recruiter email** (do **Render** in step 3 first, so there is a resume to attach). This creates a `recruiter_email.eml` with a tailored subject/body and your tailored resume attached.

- Download the `.eml` and open it in **Outlook**, **Thunderbird**, or **Windows Mail**.
- Add the recruiter's address, review the text, and send it yourself. **Nothing is auto-sent.**

### 6. Save to tracker

Click **Add to applications.xlsx**. A row is appended to `data/applications.xlsx` with the company, role, job link, date, status, and the paths to the generated resume/cover/email files. Expand **Application tracker** to view the table inside the app.

### Downloads

At the bottom, a **Downloads** section gives direct buttons for the resume `.tex`, `.txt`, and `.pdf`.

---

## Where your files live

| Path | Contents |
|------|----------|
| `resumes/output/<Company>_<Role>/` | Per-job: `resume_tailored.{tex,txt,pdf}`, `cover_letter.{txt,md,tex}`, `recruiter_email.eml` |
| `resumes/variants/<domain>/` | The 6 cached offline variants (DV, RTL, PD/STA, Emulation, Embedded, EDA-SW) |
| `data/applications.xlsx` | Your application tracker |
| `config/profile.yaml` | Your structured master resume - edit this for permanent changes |

---

## Editing outputs further

- **Resume:** edit `resume_tailored.tex` and recompile with `tectonic resume_tailored.tex`, or edit the `.txt` and paste into your own editor. For permanent content changes, edit `config/profile.yaml` and re-tailor.
- **Tracker:** open `data/applications.xlsx` in Excel and update the **Status** column (e.g. Applied -> Interview -> Offer) as you progress.

---

## Offline mode

If you have no internet or no API key, the sidebar shows **Offline mode** and tailoring uses local **TF-IDF** matching to pick the closest cached variant. Quality is lower than live AI tailoring, but you still get a usable, role-appropriate resume. Restore connectivity and your key for full tailoring. To refresh the cached variants after major profile edits, run `python -m src.variant_library --build`.

---

## Tips for the best results

- **Paste the full JD**, including the "Requirements"/"Qualifications" section - that is where the keywords live.
- **Fill your profile** (sidebar) so the summary and email are personalized.
- **Run company research** for senior/competitive roles - it sharpens the tailoring.
- **Always review** before sending: the guardrail prevents fabrication, but you should confirm the tone and that every claim is true.
- **Close missing-keyword gaps honestly** - only add skills you actually have to `profile.yaml`, then re-tailor.
- **Log every application** in the tracker so you can follow up in 5-7 days.

For strategy beyond the tool (LinkedIn, referrals, interview funnel), see the root **[GUIDE.md](../GUIDE.md)**.

---

## A typical session

1. Copy a job posting -> paste into **Paste JD text** -> **Ingest JD**.
2. (Optional) **Run company research**.
3. **Tailor resume** -> skim the summary.
4. **Render resume & run ATS** -> check the score; add any true missing keywords to your profile and re-tailor if needed.
5. **Generate cover letter**.
6. **Build recruiter email** -> download the `.eml`.
7. **Add to applications.xlsx**.
8. Open the `.eml`, add the recruiter, review, and send.
