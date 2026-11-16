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
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.parse
import urllib.request

import tzfix

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config" / "spots.json").read_text())

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
WIND_URL = "https://api.open-meteo.com/v1/forecast"

# Drie onafhankelijke modelketens (golf + wind): ECMWF, GFS (NOAA) en DWD (EWAM ±5 km + ICON; EWAM ±3 dagen vooruit).
MARINE_MODELS = ["ecmwf_wam025", "ncep_gfswave025", "dwd_ewam"]
WIND_MODELS = ["ecmwf_ifs025", "gfs_seamless", "icon_seamless"]
PART_MODELS = ["dwd_ewam", "meteofrance_wave"]
PART_VARS = ["wave_height", "swell_wave_height", "swell_wave_direction", "swell_wave_period", "swell_wave_peak_period",
             "secondary_swell_wave_height", "secondary_swell_wave_direction", "secondary_swell_wave_period",
             "wind_wave_height", "wind_wave_direction", "wind_wave_period"]
MARINE_VARS = ["wave_height", "wave_direction", "wave_peak_period", "wave_period",
               "swell_wave_height", "swell_wave_direction", "swell_wave_peak_period", "swell_wave_period"]
# Losse componenten (windzee en tweede swell). Niet elk model levert alles; dan valt de aanvraag terug op MARINE_VARS.
MARINE_VARS_FULL = MARINE_VARS + ["wind_wave_height", "wind_wave_direction", "wind_wave_peak_period", "wind_wave_period",
                                  "secondary_swell_wave_height", "secondary_swell_wave_direction",
                                  "secondary_swell_wave_period"]
# Fijnmazige windmodellen voor de eerste ±48 uur, per land; de eerste met data wint.
HIRES_WIND = {"NL": ["knmi_harmonie_arome_netherlands", "knmi_seamless"],
              "FR": ["meteofrance_arome_france_hd", "meteofrance_arome_france"],
              "PT": ["dmi_harmonie_arome_europe", "icon_eu"],
              "MA": ["dmi_harmonie_arome_europe", "icon_eu"]}
WIND_VARS = ["wind_speed_10m", "wind_direction_10m", "wind_gusts_10m", "temperature_2m"]


def get(url, params, tries=4):
    q = urllib.parse.urlencode(params, safe=",")
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(f"{url}?{q}", timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 400:  # onbekend model of variabele: opnieuw proberen heeft geen zin
                try:
                    last = json.loads(e.read().decode()).get("reason", e)
                except Exception:  # noqa: BLE001
                    pass
                break
            time.sleep(5 * (i + 1))
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


def has_values(j, var):
    return not j.get("error") and any(v is not None for v in (j.get("hourly") or {}).get(var) or [])


def fetch_marine(lat, lon, model, extra):
    """Eerst met alle componenten; lukt dat niet (onbekende variabele bij dit model), dan stap voor stap minder.
    De windzee moet er zo lang mogelijk in blijven: zonder windzee-component gaat de richting mis (17 nov)."""
    drop = [[], ["wind_wave_peak_period"], ["wind_wave_peak_period", "swell_wave_peak_period", "wave_peak_period"]]
    for d in drop:
        j = fetch_model(MARINE_URL, lat, lon, [v for v in MARINE_VARS_FULL if v not in d], model, extra)
        if not j.get("error"):
            return j
    return fetch_model(MARINE_URL, lat, lon, MARINE_VARS, model, extra)


LOCK = threading.Lock()


def problem(out, msg):
    with LOCK:
        out["problems"].append(msg)


def put(d, k, v):
    with LOCK:
        d[k] = v


def merge_donor(a, b):
    """Swell/windzee-verdeling: EWAM (fijn, ±3 dagen) aangevuld met Météo-France (langer) voor de uren erna.
    Zonder deze aanvulling had ECMWF na dag 3 weer alleen het totaal (zelfde fout als 17 nov)."""
    ha, hb = a["hourly"], b["hourly"]
    ia = {t: i for i, t in enumerate(ha["time"])}
    sa = ha.get("swell_wave_height") or []
    out = {"time": list(hb["time"])}
    for k in PART_VARS:
        va, vb = ha.get(k) or [], hb.get(k) or [None] * len(hb["time"])
        col = []
        for n, t in enumerate(hb["time"]):
            i = ia.get(t)
            use_a = i is not None and i < len(sa) and sa[i] is not None
            col.append((va[i] if i < len(va) else None) if use_a else vb[n])
        out[k] = col
    m = dict(b)
    m["hourly"] = out
    m["model"] = f"{a['model']}+{b['model']}"
    return m


def fetch_spot(reg, r, s, out, country):
    lat, lon = reg["wave_point"]
    # Golfpunt per spot: punt ±0,3° zeewaarts richting het regiopunt (de cel direct op de kust is vaak half land).
    dl, do = lat - s["lat"], lon - s["lon"]
    n = max(1e-6, (dl * dl + do * do) ** 0.5)
    f = min(1.0, 0.3 / n)
    plat, plon = s["lat"] + dl * f, s["lon"] + do * f
    spot_marine = {}
    for m in MARINE_MODELS:
        j = fetch_marine(plat, plon, m, {"cell_selection": "sea"})
        if has_values(j, "wave_height"):
            spot_marine[m] = j
    put(r["marine_spot"], s["name"], spot_marine)
    # Verdeling swell/windzee voor ECMWF (dat model levert alleen het totaal): DWD EWAM (Europa, ±5 km),
    # na ±3 dagen aangevuld met Météo-France MFWAM. Zie analyze.with_partitions.
    donors = []
    for m in PART_MODELS:
        j = get(MARINE_URL, {"latitude": plat, "longitude": plon, "hourly": ",".join(PART_VARS),
                             "models": m, "forecast_days": 16, "timezone": "auto", "cell_selection": "sea"})
        if has_values(j, "swell_wave_height"):
            j["model"] = m
            donors.append(j)
    if donors:
        put(r["marine_part"], s["name"], merge_donor(*donors) if len(donors) == 2 else donors[0])
    # Fijnmazige wind voor de korte termijn.
    for m in reg.get("hires_wind") or HIRES_WIND.get(country, []):
        j = get(WIND_URL, {"latitude": s["lat"], "longitude": s["lon"],
                           "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
                           "models": m, "forecast_days": 3, "timezone": "auto", "wind_speed_unit": "kn"})
        if has_values(j, "wind_speed_10m"):
            j["model"] = m
            put(r["wind_hires"], s["name"], j)
            break
    else:
        problem(out, f"{reg['id']} fijnmazige wind {s['name']}: geen model met data (niet erg)")
    # Getij (zeespiegel incl. getij, model van Météo-France via Open-Meteo). Valt het spotpunt op land,
    # dan het golfpunt van de regio als reserve.
    t = get(MARINE_URL, {"latitude": s["lat"], "longitude": s["lon"], "hourly": "sea_level_height_msl",
                         "forecast_days": 16, "timezone": "auto", "cell_selection": "sea"})
    vals = (t.get("hourly") or {}).get("sea_level_height_msl") or []
    if t.get("error") or not any(v is not None for v in vals):
        t = get(MARINE_URL, {"latitude": lat, "longitude": lon, "hourly": "sea_level_height_msl",
                             "forecast_days": 16, "timezone": "auto"})
        vals = (t.get("hourly") or {}).get("sea_level_height_msl") or []
        if t.get("error") or not any(v is not None for v in vals):
            problem(out, f"{reg['id']} getij {s['name']}: {t.get('reason', 'geen data')}")
    put(r["tide"], s["name"], t)
    # Watertemperatuur apart opvragen: een onbekende variabele laat zo niet het getij mislukken.
    w = get(MARINE_URL, {"latitude": s["lat"], "longitude": s["lon"], "hourly": "sea_surface_temperature",
                         "forecast_days": 16, "timezone": "auto", "cell_selection": "sea"})
    if w.get("error") or not any(v is not None for v in (w.get("hourly") or {}).get("sea_surface_temperature") or []):
        w = get(MARINE_URL, {"latitude": lat, "longitude": lon, "hourly": "sea_surface_temperature",
                             "forecast_days": 16, "timezone": "auto"})
        if w.get("error"):
            problem(out, f"{reg['id']} watertemperatuur {s['name']}: {w.get('reason')}")
    put(r["sst"], s["name"], w)
    wind = {}
    for m in WIND_MODELS:
        j = fetch_model(WIND_URL, s["lat"], s["lon"], WIND_VARS, m, {"wind_speed_unit": "kn", "daily": "sunrise,sunset"})
        wind[m] = j
        if j.get("error"):
            problem(out, f"{reg['id']} wind {s['name']} {m}: {j.get('reason')}")
    put(r["wind"], s["name"], wind)


def main():
    out = {"fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
           "regions": {}, "problems": []}
    for reg in CONFIG["regions"]:
        lat, lon = reg["wave_point"]
        r = {"marine": {}, "wind": {}, "tide": {}, "sst": {}, "marine_part": {}, "marine_spot": {}, "wind_hires": {}}
        for m in MARINE_MODELS:
            j = fetch_marine(lat, lon, m, {})
            r["marine"][m] = j
            if j.get("error"):
                out["problems"].append(f"{reg['id']} marine {m}: {j.get('reason')}")
        country = reg.get("country") or ("NL" if reg["alert"].get("mode") == "home" else "FR")
        # spots tegelijk ophalen (6 tegelijk); na elkaar duurde het ±11 minuten
        with ThreadPoolExecutor(max_workers=6) as ex:
            list(ex.map(lambda s: fetch_spot(reg, r, s, out, country), reg["spots"]))
        tzfix.localize_region(r, reg.get("tz"))  # alles naar de lokale kloktijd van de regio
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
