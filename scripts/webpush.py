#!/usr/bin/env python3
"""Web Push rechtstreeks naar de Endless Waves-app op het beginscherm (iOS 16.4+).

Secrets (GitHub → Settings → Secrets and variables → Actions):
  VAPID_PRIVATE_KEY  privésleutel (base64url, 32 bytes); de publieke sleutel staat in docs/index.html
  WEBPUSH_SUB        het abonnement dat de app toont na "Meldingen aan" (JSON; meerdere mag als lijst)
Gebruik: webpush.py <titel> <tekst> [url]   of zonder argumenten: leest out/ntfy.txt
"""
import json
import os
import sys

from pywebpush import WebPushException, webpush


def main():
    key, subs = os.environ.get("VAPID_PRIVATE_KEY", "").strip(), os.environ.get("WEBPUSH_SUB", "").strip()
    if not key or not subs:
        print("geen web push ingesteld")
        return
    if len(sys.argv) > 2:
        title, body = sys.argv[1], sys.argv[2]
    else:
        if not os.path.exists("out/ntfy.txt") or not os.path.getsize("out/ntfy.txt"):
            print("geen melding")
            return
        lines = open("out/ntfy.txt", encoding="utf-8").read().splitlines()
        title, body = lines[0], "\n".join(lines[1:])
    url = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("APP_URL", "./")
    subs = json.loads(subs)
    subs = subs if isinstance(subs, list) else [subs]
    ok = 0
    for sub in subs:
        try:
            r = webpush(sub, json.dumps({"title": title, "body": body, "url": url}), vapid_private_key=key,
                        vapid_claims={"sub": os.environ.get("VAPID_SUB", "https://derekboerma-dev.github.io/endless-waves-alerts/")}, ttl=86400)
            print("web push:", r.status_code)
            ok += 1
        except WebPushException as e:
            code = getattr(e.response, "status_code", None)
            print("antwoord:", getattr(e.response, "text", "")[:300])
            print("web push mislukt:", code, "(404/410 = abonnement verlopen: in de app opnieuw 'Meldingen aan')" if code in (404, 410) else e)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
