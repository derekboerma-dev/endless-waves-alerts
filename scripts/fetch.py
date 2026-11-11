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
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config" / "spots.json").read_text())

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
WIND_URL = "https://api.open-meteo.com/v1/forecast"

# Twee onafhankelijke modelketens: overeenstemming = extra zekerheid.
MARINE_MODELS = ["ecmwf_wam025", "ncep_gfswave025"]
WIND_MODELS = ["ecmwf_ifs025", "gfs_seamless"]
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
    """Eerst met alle componenten; lukt dat niet, dan de basisset."""
    j = fetch_model(MARINE_URL, lat, lon, MARINE_VARS_FULL, model, extra)
    if j.get("error"):
        j = fetch_model(MARINE_URL, lat, lon, MARINE_VARS, model, extra)
    return j


def main():
    out = {"fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
           "regions": {}, "problems": []}
    for reg in CONFIG["regions"]:
        lat, lon = reg["wave_point"]
        r = {"marine": {}, "wind": {}}
        for m in MARINE_MODELS:
            j = fetch_marine(lat, lon, m, {})
            r["marine"][m] = j
            if j.get("error"):
                out["problems"].append(f"{reg['id']} marine {m}: {j.get('reason')}")
        r["tide"] = {}
        r["marine_spot"], r["wind_hires"] = {}, {}
        country = reg.get("country") or ("NL" if reg["alert"].get("mode") == "home" else "FR")
        for s in reg["spots"]:
            # Golfpunt per spot: dichtstbijzijnde zeecel bij de spot (golfmodellen ±25 km raster).
            r["marine_spot"][s["name"]] = {}
            for m in MARINE_MODELS:
                # punt ±0,3° zeewaarts richting het regiopunt: de cel direct op de kust is vaak half land
                wl, wo = reg["wave_point"]
                dl, do = wl - s["lat"], wo - s["lon"]
                n = max(1e-6, (dl * dl + do * do) ** 0.5)
                f = min(1.0, 0.3 / n)
                j = fetch_marine(s["lat"] + dl * f, s["lon"] + do * f, m, {"cell_selection": "sea"})
                if has_values(j, "wave_height"):
                    r["marine_spot"][s["name"]][m] = j
            # Fijnmazige wind voor de korte termijn.
            for m in reg.get("hires_wind") or HIRES_WIND.get(country, []):
                j = get(WIND_URL, {"latitude": s["lat"], "longitude": s["lon"],
                                   "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
                                   "models": m, "forecast_days": 3, "timezone": "auto", "wind_speed_unit": "kn"})
                if has_values(j, "wind_speed_10m"):
                    j["model"] = m
                    r["wind_hires"][s["name"]] = j
                    break
            else:
                out["problems"].append(f"{reg['id']} fijnmazige wind {s['name']}: geen model met data (niet erg)")
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
                    out["problems"].append(f"{reg['id']} getij {s['name']}: {t.get('reason', 'geen data')}")
            r["tide"][s["name"]] = t
            # Watertemperatuur apart opvragen: een onbekende variabele laat zo niet het getij mislukken.
            w = get(MARINE_URL, {"latitude": s["lat"], "longitude": s["lon"], "hourly": "sea_surface_temperature",
                                 "forecast_days": 16, "timezone": "auto", "cell_selection": "sea"})
            if w.get("error") or not any(v is not None for v in (w.get("hourly") or {}).get("sea_surface_temperature") or []):
                w = get(MARINE_URL, {"latitude": lat, "longitude": lon, "hourly": "sea_surface_temperature",
                                     "forecast_days": 16, "timezone": "auto"})
                if w.get("error"):
                    out["problems"].append(f"{reg['id']} watertemperatuur {s['name']}: {w.get('reason')}")
            r.setdefault("sst", {})[s["name"]] = w
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
