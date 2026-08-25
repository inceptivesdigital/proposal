"""Render a proposal JSON to PDF.  python cli.py samples/kestrel.json out.pdf"""
import json, sys, os
from renderer import render

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "samples/kestrel.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "proposal.pdf"
    data = json.load(open(src))
    screens = data.get("screens", {})
    base = os.path.dirname(os.path.abspath(src))
    screens = {k: (v if os.path.isabs(v) else os.path.join(base, v))
               for k, v in screens.items()}
    res = render(data, out, screens)
    print("wrote", res["path"])
    if not res["milestones_ok"]:
        print("WARNING:", res["milestone_warning"])

if __name__ == "__main__":
    main()
