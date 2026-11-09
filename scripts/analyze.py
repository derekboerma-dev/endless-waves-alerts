#!/usr/bin/env python3
"""Endless Waves Alerts - analyse.

Toetst de voorspelling (ECMWF en GFS, via Open-Meteo) aan de spotcriteria en zoekt
per regio reeksen goede dagen. Per regio bepaalt het blok 'alert' in config/spots.json
wanneer een reeks een melding waard is.

Invoer : data/latest.json, config/spots.json, state/alerted.json
Uitvoer: out/alerts.json   - meldingen (nieuw / zekerder / vervallen) + alle reeksen
         out/report.html   - verslag (basis voor het Claude-verslag)
         out/ntfy.txt      - titel en tekst voor de pushmelding (leeg = geen melding)
         docs/data.json    - data voor de web-app (GitHub Pages)
         state/alerted.json

Goede dag (trip-regio's, gelijk aan Endless Waves):
  >= 2 ochtenduren (07-11 lokaal, binnen daglicht) waarin golfrichting in de swellbogen,
  Tp >= 10 s (per spot aan te passen), Hs binnen bereik, en wind offshore (+22,5 graden
  marge, <= 22 kn, windstoten <= 28 kn) of windstil (<= 6 kn).
Thuisspot (Wijk aan Zee): hele daglichtperiode, >= 2 goede uren = goede sessie.
"""
import datetime as dt
import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config" / "spots.json").read_text())
D = CFG["defaults"]
PAIRS = [("ecmwf_wam025", "ecmwf_ifs025", "ECMWF"), ("ncep_gfswave025", "gfs_seamless", "GFS")]
TIERS = ["kans", "waarschijnlijk", "bevestigd"]
DAYS_NL = ["ma", "di", "wo", "do", "vr", "za", "zo"]
MONTHS_NL = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


# ---------------------------------------------------------------- hulpfuncties
def angdiff(a, b):
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


def in_arcs(x, arcs, margin=0.0):
    return x is not None and any(angdiff(x, c) <= h + margin for c, h in arcs)


def compass(deg):
    if deg is None:
        return "?"
    pts = ["N", "NNO", "NO", "ONO", "O", "OZO", "ZO", "ZZO", "Z", "ZZW", "ZW", "WZW", "W", "WNW", "NW", "NNW"]
    return pts[int((deg % 360) / 22.5 + 0.5) % 16]


def nl_date(ds):
    d = dt.date.fromisoformat(ds)
    return f"{DAYS_NL[d.weekday()]} {d.day} {MONTHS_NL[d.month - 1]}"


def tier_for(lead):
    t = D.get("tiers", {"bevestigd": 3, "waarschijnlijk": 7})
    return "bevestigd" if lead <= t["bevestigd"] else ("waarschijnlijk" if lead <= t["waarschijnlijk"] else "kans")


def board_for(hs, tp, home=False):
    """Plankadvies uit Dereks quiver op basis van golfhoogte (diep water) en periode."""
    if hs is None:
        return None
    if hs < (1.2 if home else 1.0) or (tp is not None and tp < 8):
        return "Onfire 6'0 (35L)"
    if hs < 1.8:
        return "Channel Islands Happy Everyday 5'11"
    if hs < 2.5:
        return "Bitch Boards 6'4 HP" if (tp or 0) >= 13 else "Morris 6'4 pintail"
    return "Lost Mayhem 7'2"


def daylight(wind):
    """{datum: (zonsopkomst-uur, zonsondergang-uur)} in lokale tijd."""
    out = {}
    d = (wind or {}).get("daily") or {}
    for day, sr, ss in zip(d.get("time", []), d.get("sunrise", []), d.get("sunset", [])):
        if sr and ss:
            out[day] = (int(sr[11:13]) + int(sr[14:16]) / 60, int(ss[11:13]) + int(ss[14:16]) / 60)
    return out


# ---------------------------------------------------------------- per spot
def evaluate_spot(spot, region, marine, wind, strict):
    if not marine or marine.get("error") or not wind or wind.get("error"):
        return {}
    home = region["alert"].get("mode") == "home"
    st = {**D["strict"], **spot.get("strict", {})}
    tp_min = st["tp_min"] if strict else spot.get("tp_min", D["tp_min"])
    need = st["min_good_hours"] if strict else D["min_good_hours"]
    glassy = st["glassy_kn"] if strict else spot.get("glassy_kn", D["glassy_kn"])
    powerful = spot.get("powerful", D["powerful"])
    hs_lo, hs_hi = spot["hs"]
    mh, wh = marine["hourly"], wind["hourly"]
    widx = {t: i for i, t in enumerate(wh["time"])}
    gusts = wh.get("wind_gusts_10m") or [None] * len(wh["time"])
    light = daylight(wind) if D.get("daylight_only", True) else {}

    days = {}
    for i, t in enumerate(mh["time"]):
        day, hr = t[:10], int(t[11:13])
        if day in light:
            sr, ss = light[day]
            if hr + 0.5 < sr or hr > ss - 0.5:
                continue  # niet in daglicht
        elif home:
            if hr < 7 or hr > 18:
                continue
        if not home and hr not in D["morning_hours"]:
            continue
        rec = days.setdefault(day, {"good": [], "valid": 0, "powerful": False, "rows": []})
        hs, wdir, tp = mh["wave_height"][i], mh["wave_direction"][i], mh["wave_peak_period"][i]
        j = widx.get(t)
        if None in (hs, wdir, tp) or j is None or wh["wind_speed_10m"][j] is None:
            continue
        ws, wd, gu = wh["wind_speed_10m"][j], wh["wind_direction_10m"][j], gusts[j]
        rec["valid"] += 1
        dir_ok, tp_ok, hs_ok = in_arcs(wdir, spot["swell"]), tp >= tp_min, hs_lo <= hs <= hs_hi
        swell_ok = dir_ok and tp_ok and hs_ok
        offshore = in_arcs(wd, spot["wind"], D["wind_margin_deg"]) and ws <= D.get("max_offshore_kn", 99)
        wind_ok = (ws <= glassy or offshore) and (gu is None or gu <= D.get("max_gust_kn", 99))
        ok = swell_ok and wind_ok
        pts = int(dir_ok) + int(tp_ok) + int(hs_ok) + int(wind_ok)  # 0-4 voorwaarden gehaald
        rec["rows"].append({"h": hr, "hs": hs, "tp": tp, "dir": wdir, "ws": ws, "wd": wd, "gu": gu, "ok": ok, "pts": pts})
        if ok:
            rec["good"].append(hr)
            if hs >= powerful["hs_min"] and tp >= powerful["tp_min"]:
                rec["powerful"] = True
    out = {}
    for day, r in days.items():
        if r["valid"] < (3 if not home else 4):
            continue  # te weinig data (bijv. voorbij de modelhorizon)
        rows = r["rows"]
        pick = [x for x in rows if x["ok"]] or rows
        best = max(pick, key=lambda x: (x["hs"] if x["ok"] else 0, x["tp"]))
        win = f"{min(r['good']):02d}–{max(r['good']) + 1:02d} u" if r["good"] else None
        good = len(r["good"]) >= need
        # Conditiegraad 0-4: 0 slecht · 1 matig · 2 redelijk · 3 goed · 4 top (goed + krachtig; streng komt in de regio-stap)
        if good:
            score = 4 if r["powerful"] else 3
        else:
            p = max(x["pts"] for x in rows)
            score = 2 if (r["good"] or p == 4) else (1 if p == 3 else 0)
        out[day] = {"good": good, "score": score, "hours": len(r["good"]), "powerful": r["powerful"],
                    "window": win, "hs": round(best["hs"], 1), "tp": round(best["tp"]), "dir": compass(best["dir"]),
                    "ws": round(best["ws"]), "wd": compass(best["wd"]),
                    "gu": None if best["gu"] is None else round(best["gu"])}
    return out


# ---------------------------------------------------------------- per regio
def analyse_region(reg, data):
    """{datum: {model: {good, strict, powerful, spots, best, detail}}}"""
    res = {}
    for mm, wm, label in PAIRS:
        marine = (data.get("marine") or {}).get(mm)
        for strict in (False, True):
            for s in reg["spots"]:
                wind = ((data.get("wind") or {}).get(s["name"]) or {}).get(wm)
                for day, e in evaluate_spot(s, reg, marine, wind, strict).items():
                    d = res.setdefault(day, {}).setdefault(label, {"good": False, "strict": False, "powerful": False,
                                                                  "spots": [], "detail": {}})
                    if strict:
                        d["strict"] = d["strict"] or e["good"]
                        continue
                    d["detail"][s["name"]] = e
                    if e["good"]:
                        d["good"] = True
                        d["spots"].append(s["name"])
                        d["powerful"] = d["powerful"] or e["powerful"]
    for day, models in res.items():
        for m in models.values():
            m["score"] = max((v["score"] for v in m["detail"].values()), default=0)
            if m["good"] and m["strict"]:
                m["score"] = 4
            cand = [m["detail"][s] for s in m["spots"]] or list(m["detail"].values())
            m["best"] = max(cand, key=lambda x: (x["good"], x["hs"])) if cand else None
            if m["best"]:
                m["best"] = {**m["best"], "spot": next(k for k, v in m["detail"].items() if v is m["best"])}
    return res


def day_counts(models, lead):
    """Telt deze dag mee in een reeks? Strenger vanaf long_range_from_day."""
    if not models:
        return False, "geen data"
    goods = [m for m, v in models.items() if v["good"]]
    if lead < D.get("long_range_from_day", 8):
        return bool(goods), "beide" if len(goods) == 2 else ("één model" if goods else "")
    if len(models) == 2:
        return len(goods) == 2, "beide" if len(goods) == 2 else ("alleen " + goods[0] if goods else "")
    only = next(iter(models.values()))
    ok = only["good"] and only["strict"]
    return ok, ("alleen " + next(iter(models)) + " (streng)") if ok else ""


def find_runs(reg, days, today):
    a = reg["alert"]
    seq, cur, prev = [], [], None
    for ds in sorted(days):
        d = dt.date.fromisoformat(ds)
        if d < today:
            continue
        ok, _ = day_counts(days[ds], (d - today).days)
        if ok and (prev is None or (d - prev).days == 1) and cur:
            cur.append(ds)
        elif ok:
            if cur:
                seq.append(cur)
            cur = [ds]
        else:
            if cur:
                seq.append(cur)
            cur = []
        prev = d
    if cur:
        seq.append(cur)
    runs = []
    for r in seq:
        if len(r) < a.get("run_min_days", D["run_min_days"]):
            continue
        lead = (dt.date.fromisoformat(r[0]) - today).days
        md = [days[ds] for ds in r]
        agree = sum(1 for m in md if len(m) == 2 and all(v["good"] for v in m.values()))
        strict = sum(1 for m in md if any(v["strict"] for v in m.values()))
        powerful = sum(1 for m in md if any(v["powerful"] for v in m.values()))
        sp_or_pw = sum(1 for m in md if any(v["strict"] or v["powerful"] for v in m.values()))
        reasons = []
        if agree < a.get("min_agree_days", 0):
            reasons.append(f"modellen eens op {agree} van minimaal {a['min_agree_days']} dagen")
        if strict < a.get("min_strict_days", 0):
            reasons.append(f"{strict} strenge dagen (minimaal {a['min_strict_days']})")
        if powerful < a.get("min_powerful_days", 0):
            reasons.append(f"{powerful} krachtige dagen (minimaal {a['min_powerful_days']})")
        if sp_or_pw < a.get("min_strict_or_powerful_days", 0):
            reasons.append(f"{sp_or_pw} strenge of krachtige dagen (minimaal {a['min_strict_or_powerful_days']})")
        if "max_lead_days" in a and lead > a["max_lead_days"]:
            reasons.append(f"begint over {lead} dagen (thuisspot: max {a['max_lead_days']})")
        spots = sorted({s for m in md for v in m.values() for s in v["spots"]})
        runs.append({"region": reg["id"], "region_name": reg["name"], "country": reg["country"],
                     "mode": a.get("mode", "trip"), "start": r[0], "end": r[-1], "days": len(r), "lead_days": lead,
                     "tier": tier_for(lead), "models_agree_days": agree, "strict_days": strict,
                     "powerful_days": powerful, "spots": spots, "dates": r,
                     "qualifies": not reasons, "below_threshold": reasons})
    return runs


def overlap(a, b):
    return len(set(a["dates"]) & set(b.get("dates", [])))


# ---------------------------------------------------------------- hoofdprogramma
def main():
    latest = json.loads((ROOT / "data" / "latest.json").read_text())
    state_p = ROOT / "state" / "alerted.json"
    state = json.loads(state_p.read_text()) if state_p.exists() else {"events": []}
    today = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date.today()

    all_runs, per_region = [], {}
    for reg in CFG["regions"]:
        data = latest["regions"].get(reg["id"])
        if not data:
            continue
        per_region[reg["id"]] = analyse_region(reg, data)
        all_runs += find_runs(reg, per_region[reg["id"]], today)
    alert_runs = [r for r in all_runs if r["qualifies"]]

    # Vergelijk met eerder gemeld: zelfde regio en overlap (>= 1 dag thuisspot, >= 2 dagen trip) = zelfde reeks.
    def same(r, e):
        return e["region"] == r["region"] and overlap(r, e) >= (1 if r["mode"] == "home" else 2)

    new, upgraded = [], []
    events = [e for e in state["events"] if dt.date.fromisoformat(e["end"]) >= today and not e.get("cancelled")]
    for run in alert_runs:
        match = next((e for e in events if same(run, e)), None)
        if match is None:
            new.append(run)
            events.append({**run, "first_alert": today.isoformat(), "last_tier": run["tier"]})
            continue
        if TIERS.index(run["tier"]) > TIERS.index(match["last_tier"]):
            upgraded.append({**run, "previous_tier": match["last_tier"]})
            match["last_tier"] = run["tier"]
        match.update({k: run[k] for k in ("start", "end", "dates", "days")})
    cancelled = []
    for e in events:
        if not any(same(r, e) for r in alert_runs) and dt.date.fromisoformat(e["start"]) >= today:
            e["cancelled"] = today.isoformat()
            cancelled.append(e)
    state["events"] = [e for e in events if not e.get("cancelled")]
    state_p.parent.mkdir(exist_ok=True)
    state_p.write_text(json.dumps(state, indent=1, ensure_ascii=False))

    alerts = {"generated": today.isoformat(), "fetched_at": latest.get("fetched_at"),
              "notify": bool(new or upgraded or cancelled), "new": new, "upgraded": upgraded,
              "cancelled": cancelled, "all_runs": all_runs, "problems": latest.get("problems", [])}
    (ROOT / "out").mkdir(exist_ok=True)
    (ROOT / "out" / "alerts.json").write_text(json.dumps(alerts, indent=1, ensure_ascii=False))
    (ROOT / "out" / "ntfy.txt").write_text(ntfy_text(alerts))
    (ROOT / "out" / "report.html").write_text(render(alerts, per_region, today))
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "data.json").write_text(json.dumps(app_data(alerts, per_region, today), ensure_ascii=False,
                                                        separators=(",", ":")))
    print(f"reeksen: {len(all_runs)} (boven drempel {len(alert_runs)}), nieuw: {len(new)}, "
          f"zekerder: {len(upgraded)}, vervallen: {len(cancelled)}")


# ---------------------------------------------------------------- uitvoer
def run_line(r):
    return (f"{r['region_name']}: {nl_date(r['start'])} – {nl_date(r['end'])} ({r['days']} d, {r['tier']}, "
            f"over {r['lead_days']} d)")


def ntfy_text(a):
    """Eerste regel = titel, rest = tekst. Leeg als er niets te melden is."""
    if not a["notify"]:
        return ""
    lines = [f"+ {run_line(r)}" for r in a["new"]]
    lines += [f"↑ {run_line(r)} (was {r['previous_tier']})" for r in a["upgraded"]]
    lines += [f"× vervallen: {c['region_name']} {nl_date(c['start'])}" for c in a["cancelled"]]
    items = a["new"] + a["upgraded"]
    if len(items) == 1:
        title = f"Surf: {items[0]['region_name']} ({items[0]['tier']})"
    elif items:
        title = f"Surf: {len(items)} meldingen – " + ", ".join(sorted({r['region_name'].split(' (')[0] for r in items}))
    else:
        title = "Surf: eerdere melding vervallen"
    return title + "\n" + "\n".join(lines)


def combined_score(models):
    """Eén graad per dag voor het startscherm: gemiddelde van de modellen, naar beneden afgerond.
    disagree = modellen verschillen 2 of meer graden."""
    sc = [v.get("score", 0) for v in models.values()]
    if not sc:
        return None
    return {"v": int(sum(sc) / len(sc)), "disagree": max(sc) - min(sc) >= 2, "n": len(sc)}


def combined_hs(models):
    """Golfhoogte (Hs, m) van de beste spot, gemiddeld over de modellen."""
    hs = [v["best"]["hs"] for v in models.values() if v.get("best")]
    return round(sum(hs) / len(hs), 1) if hs else None


def app_data(alerts, per_region, today):
    regions = []
    for reg in CFG["regions"]:
        days = per_region.get(reg["id"], {})
        out_days = []
        for k in range(16):
            ds = (today + dt.timedelta(days=k)).isoformat()
            models = days.get(ds, {})
            counts, why = day_counts(models, k)
            best = None
            for lab in ("ECMWF", "GFS"):
                b = (models.get(lab) or {}).get("best")
                if b and (best is None or (b["good"] and not best["good"])):
                    best = {**b, "model": lab}
            out_days.append({
                "date": ds, "label": nl_date(ds), "lead": k, "counts": counts, "why": why,
                "score": combined_score(models), "hs": combined_hs(models),
                "models": {lab: {"good": v["good"], "strict": v["strict"], "powerful": v["powerful"], "score": v.get("score", 0),
                                 "spots": v["spots"], "detail": v["detail"]} for lab, v in models.items()},
                "best": best,
                "board": board_for(best["hs"], best["tp"], reg["alert"].get("mode") == "home") if best and best["good"] else None})
        regions.append({"id": reg["id"], "name": reg["name"], "country": reg["country"], "alert": reg["alert"],
                        "spots": [{"name": s["name"], "src": s["src"]} for s in reg["spots"]],
                        "days": out_days, "runs": [r for r in alerts["all_runs"] if r["region"] == reg["id"]]})
    return {"generated": alerts["generated"], "fetched_at": alerts["fetched_at"],
            "new": alerts["new"], "upgraded": alerts["upgraded"], "cancelled": alerts["cancelled"],
            "problems": alerts["problems"], "regions": regions,
            "tiers": D.get("tiers"), "long_range_from_day": D.get("long_range_from_day")}


def render(alerts, per_region, today):
    """Basisverslag; het Claude-verslag en de web-app zijn de vormgegeven versies."""
    e = html.escape
    head = "".join(f"<th>{DAYS_NL[(today + dt.timedelta(days=k)).weekday()]}<br>{(today + dt.timedelta(days=k)).day}</th>"
                   for k in range(16))
    rows = []
    for reg in CFG["regions"]:
        days = per_region.get(reg["id"], {})
        cells = []
        for k in range(16):
            ds = (today + dt.timedelta(days=k)).isoformat()
            v = days.get(ds, {})
            counts, _ = day_counts(v, k)
            g = [m for m, x in v.items() if x["good"]]
            cls = "both" if len(g) == 2 else ("one" if g else ("none" if v else "na"))
            star = "★" if any(x["strict"] for x in v.values()) else ""
            cells.append(f'<td class="{cls}{"" if counts or not g else " weak"}">{star}</td>')
        rows.append(f"<tr><th>{e(reg['name'])}</th>{''.join(cells)}</tr>")

    def li(r, extra=""):
        cond = "" if r["qualifies"] else f" <span class='mut'>(onder drempel: {e('; '.join(r['below_threshold']))})</span>"
        return (f"<li><b>{e(r['region_name'])}</b>: {nl_date(r['start'])} t/m {nl_date(r['end'])} ({r['days']} d, over "
                f"{r['lead_days']} d) — <b>{r['tier']}</b>{extra}{cond}<br><span class='mut'>modellen eens "
                f"{r['models_agree_days']}/{r['days']} · streng {r['strict_days']} · krachtig {r['powerful_days']} · "
                f"{e(', '.join(r['spots']))}</span></li>")

    parts = []
    for key, title in (("new", "Nieuw"), ("upgraded", "Zekerder geworden")):
        if alerts[key]:
            parts.append(f"<h2>{title}</h2><ul>" + "".join(
                li(r, f" (was {r['previous_tier']})" if key == "upgraded" else "") for r in alerts[key]) + "</ul>")
    if alerts["cancelled"]:
        parts.append("<h2>Vervallen</h2><ul>" + "".join(
            f"<li>{e(c['region_name'])} {nl_date(c['start'])} t/m {nl_date(c['end'])}</li>" for c in alerts["cancelled"]) + "</ul>")
    parts.append("<h2>Alle reeksen</h2>" + ("<ul>" + "".join(li(r) for r in alerts["all_runs"]) + "</ul>"
                                            if alerts["all_runs"] else "<p>Geen reeksen in beeld.</p>"))
    if alerts["problems"]:
        parts.append("<h2>Dataproblemen</h2><ul>" + "".join(f"<li>{e(p)}</li>" for p in alerts["problems"]) + "</ul>")
    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Endless Waves Alerts</title>
<style>:root{{--bg:#fff;--fg:#1d1d1f;--mut:#6b6b6b;--both:#2e9d5b;--one:#9fd3ae;--none:#eee;--na:#fafafa;--line:#ddd}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151515;--fg:#eee;--mut:#9a9a9a;--both:#3fbf73;--one:#2f6b45;--none:#2a2a2a;--na:#1c1c1c;--line:#333}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif;margin:0 auto;max-width:980px;padding:16px}}
table{{border-collapse:collapse;width:100%;font-size:12px}}th,td{{border:1px solid var(--line);padding:4px;text-align:center}}
th:first-child{{text-align:left;white-space:nowrap}}td.both{{background:var(--both);color:#fff}}td.one{{background:var(--one)}}
td.weak{{opacity:.45}}td.none{{background:var(--none)}}td.na{{background:var(--na)}}.wrap{{overflow-x:auto}}.mut{{color:var(--mut)}}</style></head><body>
<h1>Endless Waves Alerts</h1><p class="mut">Voorspelling {e(str(alerts['fetched_at']))} · ECMWF en GFS via Open-Meteo</p>
{''.join(parts)}<h2>Komende 16 dagen</h2><div class="wrap"><table><tr><th>Regio</th>{head}</tr>{''.join(rows)}</table></div>
<p class="mut"><small>Donkergroen = beide modellen goed · lichtgroen = één model · vaag = telt niet mee (vanaf dag
{D.get('long_range_from_day', 8)} moeten beide modellen het eens zijn) · ★ = ook goed volgens de strenge variant.</small></p></body></html>"""


if __name__ == "__main__":
    main()
