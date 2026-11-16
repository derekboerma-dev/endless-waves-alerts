#!/usr/bin/env python3
"""Modelscore: welke voorspelling kwam het best uit bij de thuisspot?

Vergelijkt elke bewaarde voorspelling (data/archive/<dag>.json.gz, de laatste run van die dag) met de metingen
van Rijkswaterstaat (state/obs.json, uit buoy.py):
  - golfhoogte op open zee (model Hs) tegen boei IJgeul 1 (Hm0), 6 km uit de kust;
  - wind (snelheid, richting en vooral de soort: offshore / zwak / zijwind / onshore) tegen IJmuiden buitenhaven.
Per model en per looptijd (dag 0-1, 1-2, 2-4, 4-7, 7+ na de run), alleen daglichturen 06-21 u.

Modellen (keten golf + wind, zoals de app ze gebruikt):
  ECMWF = ECMWF WAM + ECMWF IFS,  GFS = GFS Wave + GFS,  EWAM = DWD EWAM + DWD ICON.
  In de eerste 48 uur rekent de app voor alle ketens met de fijnmazige wind (HARMONIE); dan telt die wind.

Gewicht per model en looptijd (gebruikt in analyze.py voor de dagkans, alleen bij de thuisspot):
  fout = relatieve fout golfhoogte + aandeel uren met de verkeerde windsoort
  ruw gewicht = gemiddelde fout van alle modellen / fout van dit model, begrensd op 0,5-1,5.
  Pas vanaf 36 vergeleken uren per model in die looptijd (±3 dagen); anders gewicht 1 (gelijk).
  Met weinig uren telt het verschil maar deels mee: gewicht = 1 + (ruw - 1) x min(1, uren / 224).
  Pas na ±14 dagen daglicht (224 uur) telt het volle verschil; één weertype bepaalt zo niet alles.

Uitvoer: state/verify.json (ook in de app, tabblad van de thuisspot).
"""
import datetime as dt
import gzip
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import analyze as A  # noqa: E402
import tzfix  # noqa: E402

ROOT = A.ROOT
BUCKETS = [("0-1", 0, 0), ("1-2", 1, 1), ("2-4", 2, 3), ("4-7", 4, 6), ("7+", 7, 99)]
MIN_HOURS = 36
FULL_HOURS = 224
HIRES_H = A.D.get("hires_wind_hours", 48)


def bucket(k):
    return next(b for b, lo, hi in BUCKETS if lo <= k <= hi)


def wind_kind(spot, ws, wd):
    if ws is None or wd is None:
        return None
    if A.in_arcs(wd, spot["wind"], A.D["wind_margin_deg"]) and ws <= A.D.get("max_offshore_kn", 99):
        return "off"
    if ws <= spot.get("glassy_kn", A.D["glassy_kn"]):
        return "glassy"
    if A.is_cross(spot, wd, ws):
        return "cross"
    return "on"


def series(j, *keys):
    h = (j or {}).get("hourly") or {}
    t = h.get("time") or []
    return {tt: tuple((h.get(k) or [None] * len(t))[i] for k in keys) for i, tt in enumerate(t)}


def main():
    home = next((r for r in A.CFG["regions"] if r["alert"].get("mode") == "home"), None)
    obs_p = ROOT / "state" / "obs.json"
    if not home or not obs_p.exists():
        print("geen metingen")
        return
    spot = home["spots"][0]
    obs = json.loads(obs_p.read_text())["hours"]
    acc = {}  # (model, bucket) -> lijsten

    def add(lab, b, key, val):
        acc.setdefault((lab, b), {}).setdefault(key, []).append(val)

    files = sorted((ROOT / "data" / "archive").glob("*.json.gz"))[-60:]
    for f in files:
        try:
            with gzip.open(f, "rt") as fh:
                arch = json.load(fh)
        except Exception as e:  # noqa: BLE001
            print("overgeslagen", f.name, e)
            continue
        data = (arch.get("regions") or {}).get(home["id"])
        if not data:
            continue
        tzfix.localize_region(data, home.get("tz"))
        issue_utc = dt.datetime.fromisoformat(arch["fetched_at"].replace("Z", "+00:00"))
        issue = issue_utc.astimezone(tzfix.ZoneInfo(home["tz"])).replace(tzinfo=None)
        issue_s = issue.strftime("%Y-%m-%dT%H:%M")
        hires = series((data.get("wind_hires") or {}).get(spot["name"]), "wind_speed_10m", "wind_direction_10m")
        hires_end = (issue + dt.timedelta(hours=HIRES_H)).strftime("%Y-%m-%dT%H:%M")
        winds = (data.get("wind") or {}).get(spot["name"]) or {}
        for mm, wm, lab in A.PAIRS:
            mj = A.marine_for(data, spot, mm)
            if (not mj or mj.get("error")) and lab == "EWAM":
                mj = (data.get("marine_part") or {}).get(spot["name"])  # archief van vóór 17 nov
            hs = series(mj, "wave_height")
            wv = series(winds.get(wm), "wind_speed_10m", "wind_direction_10m")
            for t, o in obs.items():
                hr = int(t[11:13])
                if t <= issue_s or not 6 <= hr <= 21:
                    continue
                k = (dt.date.fromisoformat(t[:10]) - issue.date()).days
                b = bucket(k)
                m = hs.get(t, (None,))[0]
                if m and o.get("hs") and o["hs"] > 0.2:
                    add(lab, b, "hs_rel", abs(m - o["hs"]) / o["hs"])
                    add(lab, b, "hs_ratio", o["hs"] / m)
                w = hires.get(t) if t < hires_end and hires.get(t, (None,))[0] is not None else wv.get(t)
                if w and w[0] is not None and o.get("ws") is not None and o.get("wd") is not None:
                    add(lab, b, "ws_abs", abs(w[0] - o["ws"]))
                    if o["ws"] >= 6:
                        add(lab, b, "wd_abs", A.angdiff(w[1], o["wd"]))
                    add(lab, b, "kind_ok", wind_kind(spot, w[0], w[1]) == wind_kind(spot, o["ws"], o["wd"]))

    def med(x):
        x = sorted(x)
        return x[len(x) // 2] if x else None

    def mean(x):
        return sum(x) / len(x) if x else None

    res = {"updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), "spot": spot["name"],
           "obs_hours": len(obs), "obs_from": min(obs) if obs else None, "runs": len(files),
           "buckets": [b for b, _, _ in BUCKETS], "models": {}, "weights": {}, "min_hours": MIN_HOURS,
           "full_hours": FULL_HOURS}
    for (lab, b), v in acc.items():
        n = len(v.get("hs_rel", []))
        res["models"].setdefault(lab, {})[b] = {
            "n": n, "n_wind": len(v.get("kind_ok", [])),
            "hs_err": round(mean(v.get("hs_rel", [])), 3) if n else None,
            "hs_ratio": round(med(v.get("hs_ratio", [])), 3) if n else None,
            "ws_err": round(mean(v.get("ws_abs", [])), 1) if v.get("ws_abs") else None,
            "wd_err": round(mean(v.get("wd_abs", []))) if v.get("wd_abs") else None,
            "wind_ok": round(mean([1.0 if x else 0.0 for x in v.get("kind_ok", [])]), 3) if v.get("kind_ok") else None}
    for b, _, _ in BUCKETS:
        errs, ns = {}, {}
        for lab, per in res["models"].items():
            e = per.get(b)
            if e and e["n"] >= MIN_HOURS and e["n_wind"] >= MIN_HOURS:
                errs[lab] = e["hs_err"] + (1 - e["wind_ok"])
                ns[lab] = min(e["n"], e["n_wind"])
        if len(errs) >= 2:
            avg = sum(errs.values()) / len(errs)
            res["weights"][b] = {}
            for lab, e in errs.items():
                raw = min(1.5, max(0.5, avg / max(e, 1e-3)))
                res["weights"][b][lab] = round(1 + (raw - 1) * min(1.0, ns[lab] / FULL_HOURS), 2)
    (ROOT / "state").mkdir(exist_ok=True)
    (ROOT / "state" / "verify.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    for lab, per in sorted(res["models"].items()):
        print(lab, {b: (e["n"], e["hs_err"], e["hs_ratio"], e["ws_err"], e["wind_ok"]) for b, e in per.items()})
    print("gewichten:", res["weights"] or "nog niet (te weinig uren)")


if __name__ == "__main__":
    main()
