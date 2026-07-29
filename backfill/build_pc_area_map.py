#!/usr/bin/env python3
"""
build_pc_area_map.py  —  ONE-OFF backfill helper (not part of the daily archiver).

Builds an authoritative postcode->area mapping using the map's OWN live `find` endpoint,
so the historical postcode-level CSVs (backfill/raw/) can be aggregated to the SAME 301
areas the current archive uses. "Resonates with current data" because the mapping IS the
current backend's mapping.

Method: take one representative PC6 per PC4 from a full historical snapshot, sample PC4s
evenly across the whole country, and call POST /api/serviceArea/find for both directions
(WITHDRAWAL=afname, INJECTION=invoeding). Record area_id -> representative PC6 the first
time each area is seen. Colours are uniform within an area, so one representative postcode
determines the whole area's colour in every snapshot.

Output: backfill/pc_area_map.json  { "afname": {area_id: pc6}, "invoeding": {...}, meta... }

Polite: sequential, rate-limited, one-time. RNB areas only in this pass (280 of 301);
the 21 TenneT regions are coarse and handled/annotated separately.
"""
from __future__ import annotations
import csv, json, random, sys, time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parent.parent
FULL_CSV = ROOT / "backfill/raw/capaciteitskaart_2024-03-03.csv"   # a full (untruncated) snapshot
AREA_IDS = ROOT / "data/area_ids.json"
OUT = ROOT / "backfill/pc_area_map.json"

BASE = "https://data.partnersinenergie.nl/api"
UA = "gridwatch-nl backfill (contact: jeremy-graft@users.noreply.github.com)"
DELAY = 0.4
CALL_BUDGET = 3600          # hard cap
PLATEAU_STOP = 700          # stop a direction once this many consecutive calls find nothing new

DIRECTIONS = [("WITHDRAWAL", "afname"), ("INJECTION", "invoeding")]


def main() -> int:
    # target area ids per direction (RNB only for this pass)
    areas = json.loads(AREA_IDS.read_text(encoding="utf-8"))["areas"]
    target = {
        "afname":   {a["id"] for a in areas if a["operator"] != "TenneT" and "afname" in a["directions"]},
        "invoeding":{a["id"] for a in areas if a["operator"] != "TenneT" and "invoeding" in a["directions"]},
    }

    # one representative PC6 per PC4, from a full snapshot
    pc4_sample: dict[str, str] = {}
    with FULL_CSV.open(encoding="utf-8") as f:
        r = csv.reader(f); next(r)
        for row in r:
            if row and len(row[0]) == 6:
                pc4_sample.setdefault(row[0][:4], row[0])
    pc4s = sorted(pc4_sample)
    # Shuffle so a call budget spends nationally, not just on the low-postcode region.
    random.seed(42)
    random.shuffle(pc4s)
    sampled = pc4s
    print(f"{len(pc4s)} PC4s; shuffled full sweep (budget {CALL_BUDGET}); "
          f"targets: afname={len(target['afname'])} invoeding={len(target['invoeding'])}",
          flush=True)

    # Preload any existing representatives so this can run as an incremental fill pass.
    rep = {"afname": {}, "invoeding": {}}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
            for k in ("afname", "invoeding"):
                rep[k] = {a: p for a, p in prev.get(k, {}).items() if a in target[k]}
            print(f"preloaded: afname={len(rep['afname'])} invoeding={len(rep['invoeding'])}", flush=True)
        except Exception:
            pass
    plateau = {"afname": 0, "invoeding": 0}
    calls = 0
    headers = {"User-Agent": UA, "Accept": "application/json"}
    with httpx.Client(timeout=30, headers=headers, follow_redirects=True) as client:
        for pc4 in sampled:
            if calls >= CALL_BUDGET:
                break
            pc6 = pc4_sample[pc4]
            for api_dir, key in DIRECTIONS:
                if calls >= CALL_BUDGET or plateau[key] > PLATEAU_STOP:
                    continue
                if len(rep[key]) >= len(target[key]):
                    continue  # this direction fully covered
                try:
                    resp = client.post(f"{BASE}/serviceArea/find",
                                       json={"postalCode6": pc6, "gridOperatorType": "RNB",
                                             "energyFlowDirection": api_dir})
                    calls += 1
                    aid = (resp.json().get("serviceArea") or {}).get("id") if resp.status_code == 200 else None
                except Exception:
                    aid = None
                    calls += 1
                if aid and aid in target[key] and aid not in rep[key]:
                    rep[key][aid] = pc6
                    plateau[key] = 0
                else:
                    plateau[key] += 1
                time.sleep(DELAY)
            if calls % 100 < len(DIRECTIONS):
                print(f"  calls={calls}  afname={len(rep['afname'])}/{len(target['afname'])}  "
                      f"invoeding={len(rep['invoeding'])}/{len(target['invoeding'])}", flush=True)

    payload = {
        "_comment": "postcode->area representatives via live /api/serviceArea/find (RNB pass). "
                    "One PC6 per area; colours are uniform within an area.",
        "calls_made": calls,
        "coverage": {
            "afname": f"{len(rep['afname'])}/{len(target['afname'])}",
            "invoeding": f"{len(rep['invoeding'])}/{len(target['invoeding'])}",
        },
        "missing": {
            "afname": sorted(target["afname"] - set(rep["afname"])),
            "invoeding": sorted(target["invoeding"] - set(rep["invoeding"])),
        },
        "afname": dict(sorted(rep["afname"].items())),
        "invoeding": dict(sorted(rep["invoeding"].items())),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDONE calls={calls}  afname={len(rep['afname'])}/{len(target['afname'])}  "
          f"invoeding={len(rep['invoeding'])}/{len(target['invoeding'])}\nwrote {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
