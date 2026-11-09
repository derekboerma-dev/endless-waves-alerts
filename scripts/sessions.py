#!/usr/bin/env python3
"""Leest sessiescores die vanuit de app als GitHub-issue zijn ingediend en zet ze in docs/sessions.json.

Een issue heeft de titel 'Sessie: <spot> <datum>' en een body met regels:
  Spot: <naam>
  Datum: JJJJ-MM-DD
  Tijd: ochtend | middag | avond | UU:MM (optioneel)
  Score: <0-4> (<label>)
  Plank: <optioneel>
  Opmerking: <optioneel>
  Voorspeld: <graad en golf volgens de app, ter vergelijking>
Invoer: JSON van `gh issue list` (pad als argument). Uitvoer: docs/sessions.json (alle sessies, nieuwste eerst).
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIELDS = {"spot": "spot", "datum": "date", "tijd": "time", "score": "score", "plank": "board", "opmerking": "note", "voorspeld": "forecast"}


def parse(issue):
    rec = {"issue": issue.get("number"), "created": issue.get("createdAt")}
    for line in (issue.get("body") or "").splitlines():
        m = re.match(r"\s*([A-Za-z]+)\s*:\s*(.*)$", line)
        if m and m.group(1).lower() in FIELDS:
            rec[FIELDS[m.group(1).lower()]] = m.group(2).strip()
    if "score" in rec:
        m = re.match(r"(\d)", rec["score"])
        rec["score"] = int(m.group(1)) if m else None
    return rec if rec.get("spot") and rec.get("date") and rec.get("score") is not None else None


def main():
    raw = json.loads(pathlib.Path(sys.argv[1]).read_text()) if len(sys.argv) > 1 else []
    out_p = ROOT / "docs" / "sessions.json"
    old = json.loads(out_p.read_text()) if out_p.exists() else []
    seen = {r["issue"] for r in old}
    new = [r for r in (parse(i) for i in raw if str(i.get("title", "")).startswith("Sessie:")) if r and r["issue"] not in seen]
    allr = sorted(old + new, key=lambda r: (r["date"], r.get("created") or ""), reverse=True)
    out_p.write_text(json.dumps(allr, ensure_ascii=False, indent=1))
    print(f"sessies: {len(allr)} (nieuw {len(new)})")
    print(" ".join(str(r["issue"]) for r in new))  # laatste regel: te sluiten issues


if __name__ == "__main__":
    main()
