#!/usr/bin/env bash
# One command to run the Proposal Creator on this machine.
set -e
cd "$(dirname "$0")"
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt uvicorn
echo
echo "  Proposal Creator is running."
echo "  Open  http://127.0.0.1:8000"
echo "  Stop with Ctrl+C"
echo
python -m uvicorn api.index:app --host 127.0.0.1 --port 8000
