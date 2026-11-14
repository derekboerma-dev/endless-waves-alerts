#!/usr/bin/env python3
"""Metingen van Rijkswaterstaat (meetboeien/palen) bij de thuisspot ophalen.

API: Rijkswaterstaat WaterWebservices DD-API 2.0 (geen sleutel nodig).
  catalogus:  POST {BASE}/METADATASERVICES/OphalenCatalogus
  metingen:   POST {BASE}/ONLINEWAARNEMINGENSERVICES/OphalenWaarnemingen
Zoekt per grootheid de dichtstbijzijnde locatie bij de thuisspot (max 40 km) en haalt de laatste 36 uur op.
Uitvoer: data/buoy/latest.json (en data/buoy/<datum>.json als archief).
Grootheden: Hm0 (significante golfhoogte, cm), Tm02 (gem. periode, s), Th0 (golfrichting, °),
            WINDSHD (windsnelheid, m/s), WINDRTG (windrichting, °).
"""
import datetime as dt
import json
import math
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = "https://ddapi20-waterwebservices.rijkswaterstaat.nl"
WANT = ["Hm0", "Tm02", "Th0", "WINDSHD", "WINDRTG"]
MAX_KM = 40


def post(path, body, timeout=90):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def latlon(loc):
    """Coördinaten uit de catalogus: ETRS89 graden (lat/lon) of UTM31 (meters)."""
    x, y = loc.get("Lon") or loc.get("X"), loc.get("Lat") or loc.get("Y")
    if x is None or y is None:
        return None
    x, y = float(x), float(y)
    if abs(x) <= 180 and abs(y) <= 90:
        return (y, x) if 45 < y < 60 else (x, y)
    # UTM zone 31N -> lat/lon (eenvoudige omrekening)
    k0, a, e2 = 0.9996, 6378137.0, 0.00669438
    x -= 500000.0
    m = y / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    p = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) + (21 * e1 ** 2 / 16) * math.sin(4 * mu)
    n = a / math.sqrt(1 - e2 * math.sin(p) ** 2)
    t, c = math.tan(p) ** 2, e2 / (1 - e2) * math.cos(p) ** 2
    r = a * (1 - e2) / (1 - e2 * math.sin(p) ** 2) ** 1.5
    d = x / (n * k0)
    lat = p - (n * math.tan(p) / r) * (d * d / 2 - (5 + 3 * t + 10 * c) * d ** 4 / 24)
    lon = (d - (1 + 2 * t + c) * d ** 3 / 6) / math.cos(p)
    return math.degrees(lat), 3 + math.degrees(lon)


def main():
    cfg = json.loads((ROOT / "config" / "spots.json").read_text())
    home = next((r for r in cfg["regions"] if r["alert"].get("mode") == "home"), None)
    if not home:
        print("geen thuisspot")
        return
    spot = home["spots"][0]
    here = (spot["lat"], spot["lon"])
    cat = post("/METADATASERVICES/OphalenCatalogus", {"CatalogusFilter": {
        "Compartimenten": True, "Grootheden": True, "Eenheden": True, "Hoedanigheden": True, "Parameters": True}})
    meta = {m.get("AquoMetadata_MessageID"): m for m in cat.get("AquoMetadataLijst") or []}
    locs = {l.get("Locatie_MessageID"): l for l in cat.get("LocatieLijst") or []}
    best = {}
    for link in cat.get("AquoMetadataLocatieLijst") or []:
        m, l = meta.get(link.get("AquoMetaData_MessageID") or link.get("AquoMetadata_MessageID")), locs.get(link.get("Locatie_MessageID"))
        if not m or not l:
            continue
        g = ((m.get("Grootheid") or {}).get("Code"))
        if g not in WANT or (m.get("Compartiment") or {}).get("Code") != "OW":
            continue
        ll = latlon(l)
        if not ll:
            continue
        d = km(here, ll)
        if d <= MAX_KM and (g not in best or d < best[g][0]):
            best[g] = (d, l, m)
    for g, (d, l, m) in best.items():
        print(f"{g}: {l.get('Code')} {l.get('Naam')} ({d:.0f} km) eenheid {(m.get('Eenheid') or {}).get('Code')}")
    now = dt.datetime.now(dt.timezone.utc)
    per = {"Begindatumtijd": (now - dt.timedelta(hours=36)).strftime("%Y-%m-%dT%H:%M:%S.000+00:00"),
           "Einddatumtijd": now.strftime("%Y-%m-%dT%H:%M:%S.000+00:00")}
    out = {"fetched_at": now.isoformat(timespec="minutes"), "spot": spot["name"], "series": {}}
    for g, (d, l, m) in best.items():
        body = {"Locatie": {"Code": l.get("Code")},
                "AquoPlusWaarnemingMetadata": {"AquoMetadata": {"Compartiment": {"Code": "OW"}, "Grootheid": {"Code": g}}},
                "Periode": per}
        try:
            r = post("/ONLINEWAARNEMINGENSERVICES/OphalenWaarnemingen", body)
        except Exception as e:  # noqa: BLE001
            print(f"{g}: ophalen mislukt: {e}")
            continue
        pts = []
        for w in r.get("WaarnemingenLijst") or []:
            for x in w.get("MetingenLijst") or []:
                v = (x.get("Meetwaarde") or {}).get("Waarde_Numeriek")
                t = x.get("Tijdstip")
                if v is None or t is None or v > 9e8:
                    continue
                pts.append([t[:16], v])
        pts.sort()
        out["series"][g] = {"station": l.get("Code"), "naam": l.get("Naam"), "km": round(d, 1),
                            "eenheid": (m.get("Eenheid") or {}).get("Code"), "data": pts}
        print(f"{g}: {len(pts)} metingen, laatste {pts[-1] if pts else '-'}")
    # windmeting op het opgegeven Rijkswaterstaat-station (luchtcompartiment), bijv. IJmuiden buitenhaven
    st = spot.get("rws_wind")
    for g in ("WINDSHD", "WINDRTG") if st else ():
        body = {"Locatie": {"Code": st}, "AquoPlusWaarnemingMetadata": {"AquoMetadata": {
            "Compartiment": {"Code": "LT"}, "Grootheid": {"Code": g}, "ProcesType": "meting"}}, "Periode": per}
        try:
            r = post("/ONLINEWAARNEMINGENSERVICES/OphalenWaarnemingen", body)
        except Exception as e:  # noqa: BLE001
            print(f"wind {g}: ophalen mislukt: {e}")
            continue
        pts = sorted([x["Tijdstip"][:16], x["Meetwaarde"]["Waarde_Numeriek"]] for w in r.get("WaarnemingenLijst") or []
                     for x in w.get("MetingenLijst") or [] if (x.get("Meetwaarde") or {}).get("Waarde_Numeriek") is not None
                     and x["Meetwaarde"]["Waarde_Numeriek"] < 9e3)
        dedup = {}
        for t, v in pts:
            dedup.setdefault(t, v)
        out["series"][g] = {"station": st, "naam": st, "km": None, "eenheid": "m/s" if g == "WINDSHD" else "graad",
                            "data": [[t, v] for t, v in sorted(dedup.items())]}
        print(f"wind {g}: {len(dedup)} metingen")
    if not out["series"]:
        print("geen metingen gevonden")
        sys.exit(0)
    p = ROOT / "data" / "buoy"
    p.mkdir(parents=True, exist_ok=True)
    (p / "latest.json").write_text(json.dumps(out, ensure_ascii=False))
    (p / f"{now.date().isoformat()}.json").write_text(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
