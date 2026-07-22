@echo off
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
  echo Creating virtual environment...
  py -3.11 -m venv venv 2>nul || python -m venv venv
)

call venv\Scripts\activate.bat
pip install -q -r requirements.txt

echo Tip: for optional local browser auto-fill run: pip install -r requirements-local.txt ^&^& python -m playwright install chromium

if not exist "config\profile.yaml" (
  echo Generating profile from seed resume...
  python -m src.resume_parser
)

echo Starting Resume Job-Hunt Toolkit...
streamlit run app.py
endlocal
