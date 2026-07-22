#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x venv/bin/python ]]; then
  echo "Creating virtual environment..."
  python3.11 -m venv venv 2>/dev/null || python3 -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate
pip install -q -r requirements.txt

echo "Tip: for optional local browser auto-fill: pip install -r requirements-local.txt && python -m playwright install chromium"

if [[ ! -f config/profile.yaml ]]; then
  echo "Generating profile from seed resume..."
  python -m src.resume_parser
fi

echo "Starting Resume Job-Hunt Toolkit..."
streamlit run app.py
