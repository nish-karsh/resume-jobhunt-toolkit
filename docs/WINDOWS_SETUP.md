# Windows Setup & Run Plan

A complete, step-by-step plan to get the **Resume Job-Hunt Toolkit** running on your personal Windows PC. No Synopsys tools, licenses, or corporate paths are required.

- **Time:** ~15-20 minutes (mostly downloads on first run)
- **Disk:** ~1 GB (Python + packages + Tectonic)
- **You need:** Windows 10/11, an internet connection, and a free NVIDIA account

> If you just want the short version, jump to the [copy-paste PowerShell block](#appendix-one-shot-powershell) at the bottom.

---

## What you'll end up with

A local web app (opens in your browser at `http://localhost:8501`) where you paste a job description, click a few buttons, and get a tailored resume, an ATS score, a cover letter, and a ready-to-send recruiter email - all powered by free NVIDIA NIM models, with everything stored privately on your PC.

---

## Step 0 - Get the project folder onto your PC

Copy the entire `Resume_Automate/` folder to your PC, for example to `C:\Users\<you>\Resume_Automate`.

- **Do NOT copy the `venv/` folder** from the Linux machine - it will not work on Windows. You will recreate it in Step 4 (or `run.bat` does it for you). If `venv/` came along, delete it.
- The `data/seed_resume.pdf` (your parsed resume) and `.env` may or may not have come across. Steps 3-5 cover recreating them if needed.

A clean way to move it: zip the folder **excluding** `venv/`, transfer the zip, and unzip on your PC.

---

## Step 1 - Install Python 3.11+

**Option A - winget (recommended):**

```powershell
winget install Python.Python.3.11
```

**Option B - installer:** download from [python.org/downloads](https://www.python.org/downloads/) and, on the first screen, tick **"Add python.exe to PATH"** before clicking Install.

**Verify** (open a *new* terminal so PATH refreshes):

```powershell
python --version
py -3.11 --version
```

Either should print `Python 3.11.x` (or newer). `run.bat` prefers `py -3.11`.

---

## Step 2 - Install Tectonic (LaTeX -> PDF)

Tectonic is a single-file LaTeX engine that compiles your tailored resume to a polished PDF - no giant TeX install required.

**Option A - winget (recommended):**

```powershell
winget install TectonicProject.Tectonic
```

If that ID is not found, try the alternate:

```powershell
winget install tectonic.tectonic
```

**Option B - scoop:** `scoop install tectonic`
**Option C - conda:** `conda install -c conda-forge tectonic`
**Option D - direct download:** grab the `x86_64-pc-windows-msvc.zip` from the [Tectonic releases page](https://github.com/tectonic-typesetting/tectonic/releases), unzip, and put `tectonic.exe` somewhere on your PATH.

**Verify** (new terminal):

```powershell
tectonic --version
```

> **Tectonic is optional.** If it is missing, the app still generates the resume as `.tex` + `.txt` and writes a small `*.pdf_note.txt` explaining how to get the PDF. You can also paste the `.tex` into [Overleaf](https://www.overleaf.com) to compile it. But installing Tectonic gives you one-click PDFs, so it is recommended.

---

## Step 3 - Get a free NVIDIA API key

1. Go to [build.nvidia.com](https://build.nvidia.com) and sign in (free NVIDIA Developer account).
2. Open any model, click **Get API Key**, and generate a key. It starts with `nvapi-`.
3. Copy the key somewhere safe for the next step.

The free tier is OpenAI-compatible and allows ~40 requests/min - this toolkit only makes ~4 calls per job, so you will stay well within limits. See [MODELS.md](MODELS.md) for details.

---

## Step 4 - Configure your API key (`.env`)

In the project folder, create a `.env` file from the template:

```powershell
cd C:\path\to\Resume_Automate
Copy-Item .env.example .env
notepad .env
```

Set the one line to your real key and save:

```env
NVIDIA_API_KEY=nvapi-your-actual-key-here
```

> `.env` is gitignored and never leaves your PC. Do not paste your key into screenshots or commits.

---

## Step 5 - First launch (`run.bat` does the heavy lifting)

Double-click **`run.bat`**, or from a terminal:

```powershell
cd C:\path\to\Resume_Automate
.\run.bat
```

On first run, `run.bat` automatically:

1. Creates the virtual environment (`py -3.11 -m venv venv`, falling back to `python -m venv venv`).
2. Installs all dependencies from `requirements.txt` (this is the slow part - a few minutes).
3. If `config/profile.yaml` is missing, parses `data/seed_resume.pdf` into it.
4. Starts Streamlit and opens the app at `http://localhost:8501`.

Leave the terminal window open while you use the app. Close it (or press `Ctrl+C`) to stop the app.

---

## Step 6 - Fill in your profile blanks

The parser fills most of your profile automatically, but four fields are left as `TODO` for you. Fill them either in the app **sidebar -> Profile** (then click **Save profile fields**), or by editing `config/profile.yaml` directly:

- `identity.location` - e.g. `Bangalore, India`
- `current_city` - e.g. `Noida`
- `target_titles` - e.g. `Design Verification Engineer, Verification Engineer`
- `notice_period` - e.g. `Immediate` or `30 days`

(`from_email` is already set to your resume email; change it if you want drafts to come from a different address.)

---

## Step 7 - (Optional) Verify and build variant PDFs

Now that Tectonic is installed, you can smoke-test the AI connection and (re)compile the six offline resume variants to PDF:

```powershell
venv\Scripts\activate
python -m src.nim_client --smoke        # confirms your key + a live model call
python -m src.variant_library --build   # rebuilds the 6 cached variants (uses ~6 API calls)
```

The variants live in `resumes/variants/<domain>/` and are what the app falls back to when NVIDIA is unreachable.

---

## Verification checklist

- [ ] `python --version` shows 3.11+
- [ ] `tectonic --version` works (or you accept `.tex`/Overleaf compilation)
- [ ] `.env` contains your real `nvapi-` key
- [ ] `run.bat` opens the app at `http://localhost:8501`
- [ ] Sidebar shows **"NIM online"** (not "Offline mode")
- [ ] The four profile `TODO` fields are filled
- [ ] A test JD produces a tailored resume in `resumes/output/`

Once these pass, you are ready to use the tool - see the [User Guide](USER_GUIDE.md).

---

## Manual setup (without `run.bat`)

If you prefer to run the steps yourself:

```powershell
cd C:\path\to\Resume_Automate
py -3.11 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m src.resume_parser        # parse seed resume -> config/profile.yaml
streamlit run app.py
```

---

## Updating or re-parsing

- **Changed your master resume?** Replace `data/seed_resume.pdf`, then in the app sidebar choose **Reload from seed PDF**, or run `python -m src.resume_parser`. You can also upload a different PDF per session from the sidebar.
- **Changed models or settings?** Edit `config/settings.yaml` (see [CONFIGURATION.md](CONFIGURATION.md)) and restart the app.
- **Updated dependencies?** `venv\Scripts\activate` then `pip install -r requirements.txt --upgrade`.

---

## Remote access & hosting

For daily use, running locally via `run.bat` is recommended (private and free). If you want to reach the app from your phone, or host it in the cloud, see **[HOSTING.md](HOSTING.md)** for options and privacy trade-offs.

---

## If something goes wrong

See **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** for fixes to the most common issues (Tectonic not found, 429/503 API errors, JD link scraping blocked, offline mode, venv problems).

---

## Appendix: one-shot PowerShell

After installing Python and Tectonic (Steps 1-2) and creating `.env` with your key (Steps 3-4), this sets everything up and launches:

```powershell
cd C:\path\to\Resume_Automate
py -3.11 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m src.resume_parser
streamlit run app.py
```
