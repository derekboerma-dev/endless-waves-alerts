#!/usr/bin/env python3
"""Zet alle tijden van Open-Meteo om naar de lokale kloktijd van de regio.

Waarom: met timezone=auto kiest Open-Meteo de tijdzone op het opgevraagde punt. Een golfpunt op zee krijgt
dan een scheepvaartzone (Etc/GMT of Etc/GMT+1 = UTC-1), terwijl de wind op het land in lokale tijd staat.
Voor Marokko geven de twee servers zelfs een verschillende offset voor Africa/Casablanca. Golf, wind, getij
en zon liepen daardoor 1 tot 2 uur uit de pas. Hier rekenen we elke reeks terug naar UTC (met de offset
uit het antwoord zelf) en dan naar de tijdzone van de regio (config: regions[].tz) met de tz-database
van Python."""
import datetime as dt
from zoneinfo import ZoneInfo

FMT = "%Y-%m-%dT%H:%M"


def _conv(ts, off, tz):
    if not ts:
        return ts
    t = dt.datetime.strptime(ts[:16], FMT) - dt.timedelta(seconds=off)
    return t.replace(tzinfo=dt.timezone.utc).astimezone(tz).strftime(FMT)


def localize(j, tzname):
    """Eén Open-Meteo-antwoord (dict met hourly/daily) naar lokale tijd; meermaals aanroepen is veilig."""
    if not isinstance(j, dict) or j.get("error") or j.get("_tz") == tzname:
        return j
    if j.get("_tz"):  # al eerder omgezet naar een andere zone: eerst terug kunnen we niet, dus overslaan
        return j
    off = j.get("utc_offset_seconds")
    if off is None:
        return j
    tz = ZoneInfo(tzname)
    h = j.get("hourly") or {}
    if h.get("time"):
        h["time"] = [_conv(t, off, tz) for t in h["time"]]
    d = j.get("daily") or {}
    for k in ("sunrise", "sunset"):
        if d.get(k):
            d[k] = [_conv(t, off, tz) for t in d[k]]
    if d.get("sunrise"):
        d["time"] = [(s or "")[:10] for s in d["sunrise"]]
    j["_tz"] = tzname
    return j


def localize_region(r, tzname):
    """Alle reeksen van één regio uit data/latest.json of een archiefbestand."""
    if not tzname or not isinstance(r, dict):
        return r
    for j in (r.get("marine") or {}).values():
        localize(j, tzname)
    for group in ("marine_spot", "wind"):
        for per in (r.get(group) or {}).values():
            for j in (per or {}).values():
                localize(j, tzname)
    for group in ("tide", "sst", "wind_hires"):
        for j in (r.get(group) or {}).values():
            localize(j, tzname)
    return r
