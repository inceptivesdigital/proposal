#!/usr/bin/env bash
# One command to run the Proposal Creator on this machine.
set -e
cd "$(dirname "$0")"

# Keys live in keys.env so nobody has to retype them. It is never committed.
if [ -f keys.env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./keys.env
  set +a
  if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "  Loaded keys.env  (Anthropic key found)"
  else
    echo "  Loaded keys.env  (no Anthropic key yet — generating will not work)"
  fi
else
  echo "  No keys.env found. Copy keys.env.example to keys.env and paste your key in."
fi

python3 -m venv .venv 2>/dev/null || true
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt uvicorn
echo
echo "  Proposal Creator is running."
echo "  Open  http://127.0.0.1:8000"
echo "  Stop with Ctrl+C"
echo
python -m uvicorn api.index:app --host 127.0.0.1 --port 8000
