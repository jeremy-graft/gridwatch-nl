#!/usr/bin/env python3
"""
build_area_history.py  —  ONE-OFF. Aggregates the historical postcode CSVs to the SAME 301
areas used by the live archive, using the postcode->area representatives from
build_pc_area_map.py.

Colour is uniform within an area, so each area's colour in a snapshot = the colour of its
representative postcode in that snapshot's CSV. An area gets a value for a snapshot only if
its representative postcode is present (the 5 truncated snapshots cover only low postcodes).

Output: backfill/area_status_history.json — per area, a colour (+congestion-management)
time-series across the archived snapshots, keyed by the live archive's area ids.
"""
from __future__ import annotations
import csv, glob, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "backfill/pc_area_map.json"
AREA_IDS = ROOT / "data/area_ids.json"
OUT = ROOT / "backfill/area_status_history.json"

COLOR_LEGEND = {0: "white/available", 1: "yellow/limited", 2: "orange/investigation+queue",
                3: "red/shortage+queue"}


def main() -> int:
    mp = json.loads(MAP.read_text(encoding="utf-8"))
    meta = {a["id"]: a for a in json.loads(AREA_IDS.read_text(encoding="utf-8"))["areas"]}

    # load every snapshot CSV: postcode -> row, remembering its header
    snaps = {}
    for f in sorted(glob.glob(str(ROOT / "backfill/raw/*.csv"))):
        date = re.search(r"(\d{4}-\d{2}-\d{2})", f).group(1)
        rows = {}
        with open(f, encoding="utf-8") as fh:
            r = csv.reader(fh)
            hdr = next(r)
            for row in r:
                if row and len(row[0]) == 6:
                    rows[row[0]] = row
        snaps[date] = (hdr, rows)
    dates = sorted(snaps)

    col_idx = {"invoeding": 1, "afname": 2}
    out_areas: dict[str, dict] = {}
    for direction in ("afname", "invoeding"):
        cm_col = f"congestiemanagement {direction}"
        for aid, pc6 in mp.get(direction, {}).items():
            e = out_areas.setdefault(aid, {
                "operator": (meta.get(aid) or {}).get("operator"),
                "province": (meta.get(aid) or {}).get("province"),
                "representative_pc6": {}, "afname": {}, "invoeding": {},
            })
            e["representative_pc6"][direction] = pc6
            for date in dates:
                hdr, rows = snaps[date]
                row = rows.get(pc6)
                if not row:
                    continue
                val = {}
                c = row[col_idx[direction]]
                if c.isdigit():
                    val["color"] = int(c)
                if cm_col in hdr:
                    ci = hdr.index(cm_col)
                    if ci < len(row) and row[ci].isdigit():
                        val["cm"] = int(row[ci])
                if val:
                    e[direction][date] = val

    # per-snapshot coverage (how many areas resolved)
    coverage = {}
    for date in dates:
        n_a = sum(1 for a in out_areas.values() if date in a["afname"])
        n_i = sum(1 for a in out_areas.values() if date in a["invoeding"])
        coverage[date] = {"afname_areas": n_a, "invoeding_areas": n_i}

    payload = {
        "_comment": "Historical congestion COLOUR per area, aggregated from the archived "
                    "capaciteitskaart CSV exports (backfill/raw/) via the live find endpoint's "
                    "postcode->area mapping. Colour only; queue/relief/projects did not exist "
                    "in these old exports. Area ids match data/area_ids.json (RNB areas).",
        "color_legend": COLOR_LEGEND,
        "cm_legend": {0: "no congestion management", 1: "congestion management active"},
        "snapshot_dates": dates,
        "snapshot_notes": "2024-01-11 and 2024-03-03 are full-national; the other 5 are "
                          "Archive-truncated (~postcodes <=2585, Randstad-north only). "
                          "3-column snapshots (pre 2023-09) have no congestion-management flag.",
        "coverage_per_snapshot": coverage,
        "areas_mapped": len(out_areas),
        "areas": dict(sorted(out_areas.items())),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}: {len(out_areas)} areas across {len(dates)} snapshots")
    for d, c in coverage.items():
        print(f"  {d}: afname {c['afname_areas']} / invoeding {c['invoeding_areas']} areas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
