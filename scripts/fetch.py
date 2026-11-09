#!/usr/bin/env python3
"""Haalt de golf- en windvoorspelling (16 dagen) op van Open-Meteo voor alle spots
uit config/spots.json en schrijft data/latest.json + een gecomprimeerde dagkopie
in data/archive/ (voor latere controle: kwam de voorspelling uit?).

Alleen standaardbibliotheek. Draait in GitHub Actions (open internet).
"""
import datetime as dt
import gzip
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config" / "spots.json").read_text())

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
WIND_URL = "https://api.open-meteo.com/v1/forecast"

# Twee onafhankelijke modelketens: overeenstemming = extra zekerheid.
MARINE_MODELS = ["ecmwf_wam025", "ncep_gfswave025"]
WIND_MODELS = ["ecmwf_ifs025", "gfs_seamless"]
MARINE_VARS = ["wave_height", "wave_direction", "wave_peak_period",
               "swell_wave_height", "swell_wave_direction", "swell_wave_peak_period"]
WIND_VARS = ["wind_speed_10m", "wind_direction_10m", "wind_gusts_10m"]


def get(url, params, tries=4):
    q = urllib.parse.urlencode(params, safe=",")
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(f"{url}?{q}", timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001 - log en opnieuw
            last = e
            time.sleep(5 * (i + 1))
    return {"error": True, "reason": str(last)}


def fetch_model(url, lat, lon, variables, model, extra):
    """Eén model per aanvraag: zo faalt een onbekende modelnaam niet de hele set."""
    params = {"latitude": lat, "longitude": lon, "hourly": ",".join(variables),
              "models": model, "forecast_days": 16, "timezone": "auto"}
    params.update(extra)
    return get(url, params)


def main():
    out = {"fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
           "regions": {}, "problems": []}
    for reg in CONFIG["regions"]:
        lat, lon = reg["wave_point"]
        r = {"marine": {}, "wind": {}}
        for m in MARINE_MODELS:
            j = fetch_model(MARINE_URL, lat, lon, MARINE_VARS, m, {})
            r["marine"][m] = j
            if j.get("error"):
                out["problems"].append(f"{reg['id']} marine {m}: {j.get('reason')}")
        for s in reg["spots"]:
            r["wind"][s["name"]] = {}
            for m in WIND_MODELS:
                j = fetch_model(WIND_URL, s["lat"], s["lon"], WIND_VARS, m, {"wind_speed_unit": "kn", "daily": "sunrise,sunset"})
                r["wind"][s["name"]][m] = j
                if j.get("error"):
                    out["problems"].append(f"{reg['id']} wind {s['name']} {m}: {j.get('reason')}")
        out["regions"][reg["id"]] = r

    data = ROOT / "data"
    (data / "archive").mkdir(parents=True, exist_ok=True)
    txt = json.dumps(out, separators=(",", ":"))
    (data / "latest.json").write_text(txt)
    day = out["fetched_at"][:10]
    with gzip.open(data / "archive" / f"{day}.json.gz", "wt") as f:
        f.write(txt)
    print(f"ok, {len(out['problems'])} problemen")
    for p in out["problems"]:
        print("  -", p)
    # Faal alleen als er helemaal niets binnenkwam.
    total = sum(len(r["marine"]) for r in out["regions"].values())
    if len(out["problems"]) >= total:
        sys.exit(1)


if __name__ == "__main__":
    main()
