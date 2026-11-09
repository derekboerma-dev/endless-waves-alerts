#!/usr/bin/env python3
"""Voorspeld tegenover echt: zet elke sessiescore naast wat het systeem die dag voorspelde.

Voor elke sessie in docs/sessions.json:
  - pakt de voorspelling uit het archief van die dag (data/archive/<datum>.json.gz, dus de verwachting op
    dag 0, het dichtst bij wat er echt was);
  - rekent de graad van die spot opnieuw uit met dezelfde regels als de app (analyze.py);
  - haalt de omstandigheden op het tijdstip van de sessie op: golf, periode, richting, wind, getij.
Per spot volgt een samenvatting: hoe vaak, gemiddeld verschil (jouw graad min voorspelde graad) en
voorzichtige hints. Hints pas vanaf 3 sessies per spot; automatisch bijsturen pas vanaf ±10–15.

Uitvoer: docs/calibration.json (voor de app) en out/kalibratie.md (leesbaar, ook voor Claude).
"""
import gzip
import json
import pathlib
import statistics

import analyze as A

ROOT = A.ROOT
GRADE = ["niets", "matig", "redelijk", "goed", "top"]
SLOTS = {"ochtend": range(7, 11), "middag": range(11, 16), "avond": range(16, 20)}


def hours_for(t):
    t = (t or "").strip().lower()
    if t in SLOTS:
        return list(SLOTS[t])
    if len(t) >= 2 and t[:2].isdigit():
        h = int(t[:2])
        return [h, h + 1]
    return list(range(7, 19))


def archive_for(day):
    p = ROOT / "data" / "archive" / f"{day}.json.gz"
    if not p.exists():
        return None
    with gzip.open(p, "rt") as f:
        return json.load(f)


def find_spot(name):
    for reg in A.CFG["regions"]:
        for s in reg["spots"]:
            if s["name"] == name:
                return reg, s
    return None, None


def conditions(data, reg, spot, day, hours):
    """Gemiddelde omstandigheden op de sessie-uren (ECMWF, anders GFS)."""
    for mm, wm, lab in A.PAIRS:
        marine = (data.get("marine") or {}).get(mm) or {}
        wind = ((data.get("wind") or {}).get(spot["name"]) or {}).get(wm) or {}
        mh, wh = marine.get("hourly") or {}, wind.get("hourly") or {}
        widx = {t: i for i, t in enumerate(wh.get("time") or [])}
        rows = []
        for i, t in enumerate(mh.get("time") or []):
            if not t.startswith(day) or int(t[11:13]) not in hours:
                continue
            j = widx.get(t)
            vals = (mh["wave_height"][i], mh["wave_peak_period"][i], mh["wave_direction"][i])
            if None in vals or j is None:
                continue
            sh = A.surf_height(vals[0], vals[1], vals[2], spot)  # geschat op de spot
            rows.append((sh,) + vals[1:] + (wh["wind_speed_10m"][j], wh["wind_direction_10m"][j], vals[0]))
        if rows:
            tinfo, _ = A.tide_series((data.get("tide") or {}).get(spot["name"]))
            tide = [tinfo.get(f"{day}T{h:02d}:00") for h in hours]
            tide = [x for x in tide if x]
            mid = rows[len(rows) // 2]
            return {"model": lab, "hs": round(statistics.mean(r[0] for r in rows), 1),
                    "hs_off": round(statistics.mean(r[5] for r in rows), 1),
                    "tp": round(statistics.mean(r[1] for r in rows)), "dir": A.compass(mid[2]),
                    "ws": round(statistics.mean(r[3] for r in rows)), "wd": A.compass(mid[4]),
                    "tide": A.tide_label(*tide[len(tide) // 2]) if tide else None,
                    "hs_ok": A.hs_range(spot, reg)[0] <= statistics.mean(r[0] for r in rows) <= A.hs_range(spot, reg)[1]}
    return None


def predicted_grade(data, reg, spot, day):
    sc = []
    for mm, wm, lab in A.PAIRS:
        marine = (data.get("marine") or {}).get(mm)
        wind = ((data.get("wind") or {}).get(spot["name"]) or {}).get(wm)
        e = A.evaluate_spot(spot, reg, marine, wind, False).get(day)
        st = A.evaluate_spot(spot, reg, marine, wind, True).get(day)
        if e:
            sc.append(4 if e["good"] and (e["powerful"] or (st and st["good"])) else e["score"])
    return int(sum(sc) / len(sc)) if sc else None


def main():
    sess_p = ROOT / "docs" / "sessions.json"
    sessions = json.loads(sess_p.read_text()) if sess_p.exists() else []
    per = {}
    for r in sessions:
        reg, spot = find_spot(r["spot"])
        data_all = archive_for(r["date"])
        rec = {k: r.get(k) for k in ("date", "time", "score", "board", "note", "height")}
        if reg and data_all and reg["id"] in data_all.get("regions", {}):
            data = data_all["regions"][reg["id"]]
            rec["predicted"] = predicted_grade(data, reg, spot, r["date"])
            rec["cond"] = conditions(data, reg, spot, r["date"], hours_for(r.get("time")))
        else:
            rec["predicted"], rec["cond"] = None, None
            rec["missing"] = "geen voorspelling uit het archief voor deze dag"
        if rec["predicted"] is not None and r.get("score") is not None:
            rec["diff"] = r["score"] - rec["predicted"]
        per.setdefault(r["spot"], []).append(rec)

    out = {}
    for name, recs in per.items():
        diffs = [x["diff"] for x in recs if "diff" in x]
        hints = []
        if len(diffs) >= 3:
            m = statistics.mean(diffs)
            if m >= 0.75:
                hints.append(f"Voorspelling is gemiddeld {m:.1f} graad te laag: criteria mogelijk te streng.")
            elif m <= -0.75:
                hints.append(f"Voorspelling is gemiddeld {abs(m):.1f} graad te hoog: criteria mogelijk te ruim.")
            rising = [x["score"] for x in recs if (x.get("cond") or {}).get("tide", "") .startswith("opkomend")]
            falling = [x["score"] for x in recs if (x.get("cond") or {}).get("tide", "").startswith("afgaand")]
            if len(rising) >= 2 and len(falling) >= 2 and abs(statistics.mean(rising) - statistics.mean(falling)) >= 1:
                better = "opkomend" if statistics.mean(rising) > statistics.mean(falling) else "afgaand"
                hints.append(f"Je scoort duidelijk beter bij {better} tij.")
            big_ok = [x for x in recs if x.get("cond") and not x["cond"]["hs_ok"] and x["score"] >= 3]
            if len(big_ok) >= 2:
                hints.append("Meerdere goede sessies buiten het ingestelde hoogtebereik: bereik mogelijk aanpassen.")
            hh = [(x["height"], x["cond"]["hs"]) for x in recs if x.get("height") and x.get("cond") and x["cond"]["hs"]]
            if len(hh) >= 3:
                ratio = statistics.mean(h / p for h, p in hh)
                if abs(ratio - 1) >= 0.15:
                    hints.append(f"Golfhoogte op de spot is gemiddeld {ratio:.2f}x de schatting: 'exposure' van deze spot "
                                 f"met die factor bijstellen.")
            boards = {}
            for x in recs:
                if x.get("board"):
                    boards.setdefault(x["board"], []).append(x["score"])
            for b, sc in boards.items():
                if len(sc) >= 3:
                    hints.append(f"{b}: gemiddeld {GRADE[round(statistics.mean(sc))]} over {len(sc)} sessies.")
        hh = [x["height"] / x["cond"]["hs"] for x in recs if x.get("height") and x.get("cond") and x["cond"]["hs"]]
        out[name] = {"height_ratio": round(statistics.mean(hh), 2) if hh else None, "n": len(recs), "n_compared": len(diffs),
                     "mean_diff": round(statistics.mean(diffs), 2) if diffs else None,
                     "hints": hints, "sessions": sorted(recs, key=lambda x: x["date"], reverse=True)}

    (ROOT / "docs" / "calibration.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    lines = ["# Voorspeld tegenover echt", "",
             "Automatisch gemaakt uit de sessiescores. Verschil = jouw graad min voorspelde graad "
             "(0 niets · 1 matig · 2 redelijk · 3 goed · 4 top). Hints pas vanaf 3 sessies per spot.", ""]
    for name, o in sorted(out.items()):
        md = "–" if o["mean_diff"] is None else f"{o['mean_diff']:+.1f}"
        lines += [f"## {name}", f"Sessies: {o['n']} · vergeleken: {o['n_compared']} · gemiddeld verschil: {md}", ""]
        lines += [f"- {h}" for h in o["hints"]] or ["- Nog te weinig sessies voor conclusies."]
        lines += ["", "| Datum | Tijd | Jij | Voorspeld | Golf (spot, schatting) | Echt (m) | Wind | Getij | Plank | Opmerking |", "|---|---|---|---|---|---|---|---|---|---|"]
        for x in o["sessions"]:
            c = x.get("cond") or {}
            pred = GRADE[x["predicted"]] if x.get("predicted") is not None else "?"
            golf = f"{c.get('hs')} m {c.get('tp')} s {c.get('dir')}" if c else "?"
            wind = f"{c.get('wd')} {c.get('ws')} kn" if c else "?"
            lines.append(f"| {x['date']} | {x.get('time') or ''} | {GRADE[x['score']]} | {pred} | {golf} | {x.get('height') or ''} | {wind} | "
                         f"{c.get('tide') or ''} | {x.get('board') or ''} | {x.get('note') or ''} |")
        lines.append("")
    (ROOT / "out").mkdir(exist_ok=True)
    (ROOT / "out" / "kalibratie.md").write_text("\n".join(lines))
    print(f"kalibratie: {len(out)} spots, {sum(o['n'] for o in out.values())} sessies")


if __name__ == "__main__":
    main()
