#!/usr/bin/env python3
"""Instellingen die in de app (tab Instellingen) aanpasbaar zijn.

De app stuurt een wijziging als GitHub-issue 'Instellingen: ...' met in de body een JSON-blok:
  {"defaults": {"max_gust_kn": 30}, "regions": {"vendee": {"run_min_days": 3}},
   "spots": {"Bud Bud": {"hs": [0.6, 2.2], "tide": "mid"}}}
De workflow settings.yml draait dan `python scripts/settings.py apply` met de body via de omgeving (ISSUE_BODY).
Alleen sleutels uit SCHEMA, binnen de grenzen; al het andere wordt geweigerd. Alleen issues van de eigenaar
van de repository worden verwerkt (controle in de workflow).

`export(cfg)` levert de huidige waarden plus het schema voor docs/data.json (de app leest die).
"""
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG_P = ROOT / "config" / "spots.json"
TIDES = ["all", "low", "low-mid", "mid", "mid-high", "high", "not-high"]

# sleutel: (type, min, max, stap, label, uitleg)
SCHEMA = {
    "defaults": {
        "min_good_hours": ("int", 1, 5, 1, "Goede uren per dag", "Zoveel goede uren zijn nodig voor een goede dag."),
        "max_offshore_kn": ("int", 8, 40, 1, "Max. offshore wind (kn)", "Sterkere aflandige wind telt niet als goed."),
        "max_gust_kn": ("int", 12, 50, 1, "Max. windstoten (kn)", "Bij andere wind dan offshore."),
        "max_gust_offshore_kn": ("int", 12, 60, 1, "Max. stoten bij offshore (kn)", "Aflandige stoten storen minder."),
        "glassy_kn": ("int", 0, 12, 1, "Windstil tot (kn)", "Zwakkere wind telt altijd als goed."),
        "long_range_from_day": ("int", 4, 16, 1, "Strenger vanaf dag", "Vanaf deze dag moeten alle modellen het eens zijn."),
    },
    "regions": {
        "enabled": ("bool", None, None, None, "Alerts aan", "Uit = geen meldingen voor deze regio (voorspelling blijft zichtbaar)."),
        "run_min_days": ("int", 1, 10, 1, "Dagen op rij", "Minimaal aantal goede dagen achter elkaar."),
        "max_lead_days": ("int", 1, 15, 1, "Max. dagen vooruit", "Alleen melden als de reeks binnen zoveel dagen begint."),
        "min_strict_days": ("int", 0, 10, 1, "Waarvan streng", "Dagen die ook volgens de strenge variant goed zijn (12 s, 3 uur, echte offshore)."),
        "min_powerful_days": ("int", 0, 10, 1, "Waarvan krachtig", "Dagen met een krachtig uur (hoogte en periode, zie 'top')."),
        "min_strict_or_powerful_days": ("int", 0, 10, 1, "Waarvan streng of krachtig", "Dagen die streng óf krachtig zijn."),
        "min_agree_days": ("int", 0, 10, 1, "Modellen eens", "Dagen waarop alle modellen 'goed' zeggen."),
    },
    "spots": {
        "hs": ("range", 0.1, 6.0, 0.1, "Golfhoogte op de spot (m)", "Van – tot, zoals Surfline het toont."),
        "tp_min": ("int", 4, 20, 1, "Min. periode (s)", "Kortere golven tellen niet als goed."),
        "tide": ("enum", TIDES, None, None, "Getij", "Voorkeur voor de beste tijd."),
    },
}


def export(cfg):
    d = cfg["defaults"]
    return {
        "schema": {sec: {k: {"type": t, "min": a if t != "enum" else None, "max": b, "step": st, "label": lab, "help": h,
                             **({"options": a} if t == "enum" else {})}
                         for k, (t, a, b, st, lab, h) in keys.items()} for sec, keys in SCHEMA.items()},
        "defaults": {k: d.get(k) for k in SCHEMA["defaults"]},
        "regions": [{"id": r["id"], "name": r["name"], "mode": r["alert"].get("mode", "trip"),
                     "values": {k: r["alert"].get(k, True if k == "enabled" else None) for k in SCHEMA["regions"]},
                     "spots": [{"name": s["name"], "values": {"hs": s["hs"], "tp_min": s.get("tp_min", d["tp_min"]),
                                                              "tide": s.get("tide", "all")}} for s in r["spots"]]}
                    for r in cfg["regions"]],
    }


def _check(spec, v, where):
    t, a, b = spec[0], spec[1], spec[2]
    if t == "bool":
        if not isinstance(v, bool):
            raise ValueError(f"{where}: aan/uit verwacht")
        return v
    if t == "int":
        if not isinstance(v, (int, float)) or int(v) != v or not a <= v <= b:
            raise ValueError(f"{where}: geheel getal {a}–{b} verwacht, kreeg {v!r}")
        return int(v)
    if t == "range":
        if (not isinstance(v, list) or len(v) != 2 or not all(isinstance(x, (int, float)) for x in v)
                or not a <= v[0] < v[1] <= b):
            raise ValueError(f"{where}: bereik van – tot binnen {a}–{b} verwacht, kreeg {v!r}")
        return [round(float(v[0]), 2), round(float(v[1]), 2)]
    if t == "enum":
        if v not in a:
            raise ValueError(f"{where}: kies uit {', '.join(a)}")
        return v
    raise ValueError(where)


def apply(cfg, ch):
    """Past de wijzigingen toe op cfg (in place). Geeft een lijst met leesbare regels; ValueError bij iets ongeldigs."""
    out = []
    if not isinstance(ch, dict) or not set(ch) <= {"defaults", "regions", "spots"}:
        raise ValueError("onbekende onderdelen")
    for k, v in (ch.get("defaults") or {}).items():
        if k not in SCHEMA["defaults"]:
            raise ValueError(f"algemeen.{k}: niet aanpasbaar")
        v = _check(SCHEMA["defaults"][k], v, f"algemeen · {SCHEMA['defaults'][k][4]}")
        out.append(f"Algemeen · {SCHEMA['defaults'][k][4]}: {cfg['defaults'].get(k)} → {v}")
        cfg["defaults"][k] = v
    regs = {r["id"]: r for r in cfg["regions"]}
    for rid, vals in (ch.get("regions") or {}).items():
        if rid not in regs:
            raise ValueError(f"regio {rid} bestaat niet")
        a = regs[rid]["alert"]
        for k, v in vals.items():
            if k not in SCHEMA["regions"]:
                raise ValueError(f"{rid}.{k}: niet aanpasbaar")
            v = _check(SCHEMA["regions"][k], v, f"{regs[rid]['name']} · {SCHEMA['regions'][k][4]}")
            out.append(f"{regs[rid]['name']} · {SCHEMA['regions'][k][4]}: {a.get(k, True if k == 'enabled' else '–')} → {v}")
            a[k] = v
    spots = {s["name"]: s for r in cfg["regions"] for s in r["spots"]}
    for name, vals in (ch.get("spots") or {}).items():
        if name not in spots:
            raise ValueError(f"spot {name} bestaat niet")
        s = spots[name]
        for k, v in vals.items():
            if k not in SCHEMA["spots"]:
                raise ValueError(f"{name}.{k}: niet aanpasbaar")
            v = _check(SCHEMA["spots"][k], v, f"{name} · {SCHEMA['spots'][k][4]}")
            out.append(f"{name} · {SCHEMA['spots'][k][4]}: {s.get(k, '–')} → {v}")
            s[k] = v
    if not out:
        raise ValueError("geen wijzigingen gevonden")
    return out


def main():
    if len(sys.argv) < 2 or sys.argv[1] != "apply":
        print(json.dumps(export(json.loads(CFG_P.read_text())), ensure_ascii=False, indent=1))
        return
    body = os.environ.get("ISSUE_BODY", "")
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", body, re.S)
    res = pathlib.Path(os.environ.get("RESULT_FILE", "/tmp/settings_result.md"))
    try:
        if not m:
            raise ValueError("geen JSON-blok in het issue")
        cfg = json.loads(CFG_P.read_text())
        lines = apply(cfg, json.loads(m.group(1)))
        CFG_P.write_text(json.dumps(cfg, ensure_ascii=False, indent=1))
        res.write_text("Verwerkt in `config/spots.json`; er start nu een nieuwe run.\n\n" + "\n".join(f"- {x}" for x in lines))
        print("\n".join(lines))
    except (ValueError, json.JSONDecodeError) as e:
        res.write_text(f"Niet verwerkt: {e}\n\nEr is niets gewijzigd.")
        print("FOUT:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
