#!/usr/bin/env python3
"""
enumerate_area_ids.py  —  MANUAL / ~monthly bootstrap tool. NOT part of the daily cron.

Rebuilds data/area_ids.json: the list of every service-area id on the capaciteitskaart,
enriched with grid operator, province, and which flow directions (afname/invoeding) it
appears in.

WHY THIS IS SEPARATE FROM fetch.py:
  The area geometry+ids live only in MapTiler-hosted vector tiles, fetched with a key that
  belongs to Netbeheer's MapTiler account. MapTiler's ToS forbids using another party's key
  as your own, so we touch it as rarely as possible: once to bootstrap, and ~monthly to catch
  new stations. The daily archiver (fetch.py) never touches MapTiler — it reads this file.

The id set is near-static; run this when the daily sweep reports an id it doesn't recognise,
or roughly monthly. See DATA_SOURCES.md §5.2/§5.3.

Usage:  python tools/enumerate_area_ids.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

# The z0 tile contains every feature of every layer (minzoom 0), so one request enumerates
# everything. Tileset id + key are read from the live app config at
# GET /capaciteitskaart/totaal/afname.data (field CAPACITEITSKAART_TILES_URL).
TILESET_ID = "105ba28a-afb8-4232-ac3d-0b40bf3fc76c"
MAPTILER_KEY = "LsAKfag3t3bTv3H1zlTP"  # Netbeheer's public client key — manual bootstrap use only
TILE_URL = f"https://api.maptiler.com/tiles/{TILESET_ID}/0/0/0.pbf?key={MAPTILER_KEY}"
CONFIG_URL = "https://data.partnersinenergie.nl/capaciteitskaart/totaal/afname.data"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT = DATA_DIR / "area_ids.json"

# The gebied (area) layers carry the per-area `id`; TenneT layers have no RNB field.
GEBIED_LAYERS = {
    "rnb_gebied_afnamefgb": (None, "afname"),
    "rnb_gebied_opwekfgb": (None, "invoeding"),
    "tennet_gebied_afnamefgb": ("TenneT", "afname"),
    "tennet_gebied_opwekfgb": ("TenneT", "invoeding"),
}


# ---------------------------------------------------------------------------
# Minimal Mapbox Vector Tile (protobuf) decoder — no external protobuf dep.
# Implements exactly what we need: layer name, feature property key/value tables,
# and each feature's (key,value) tag pairs. Geometry is skipped.
# ---------------------------------------------------------------------------
class _Reader:
    __slots__ = ("b", "p")

    def __init__(self, b: bytes):
        self.b = b
        self.p = 0

    def varint(self) -> int:
        shift = result = 0
        while True:
            byte = self.b[self.p]
            self.p += 1
            result |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                return result
            shift += 7

    def skip(self, wire: int) -> None:
        if wire == 0:
            self.varint()
        elif wire == 2:
            # NB: two statements on purpose. `self.p += self.varint()` would evaluate the
            # left self.p BEFORE varint() advances it, landing short by the length-prefix.
            n = self.varint()
            self.p += n
        elif wire == 5:
            self.p += 4
        elif wire == 1:
            self.p += 8
        else:
            raise ValueError(f"bad wire type {wire}")


def _parse_value(b: bytes) -> object:
    r = _Reader(b)
    val = None
    while r.p < len(b):
        tag = r.varint()
        field, wire = tag >> 3, tag & 7
        if field == 1 and wire == 2:  # string_value
            ln = r.varint()
            val = b[r.p:r.p + ln].decode("utf-8")
            r.p += ln
        elif field == 4 and wire == 0:  # int_value
            val = r.varint()
        else:
            r.skip(wire)
    return val


def decode_layers(tile: bytes) -> dict[str, list[dict]]:
    """Return {layer_name: [ {prop: value, ...}, ... ]} for every layer in the tile."""
    layers: dict[str, list[dict]] = {}
    top = _Reader(tile)
    while top.p < len(tile):
        tag = top.varint()
        field, wire = tag >> 3, tag & 7
        if field == 3 and wire == 2:  # a layer
            ln = top.varint()
            end = top.p + ln
            lr = _Reader(tile)
            lr.p = top.p
            name = None
            keys: list[str] = []
            values: list[object] = []
            feat_tags: list[list[int]] = []
            while lr.p < end:
                t2 = lr.varint()
                f2, w2 = t2 >> 3, t2 & 7
                if f2 == 1 and w2 == 2:  # name
                    kl = lr.varint()
                    name = tile[lr.p:lr.p + kl].decode("utf-8")
                    lr.p += kl
                elif f2 == 3 and w2 == 2:  # keys
                    kl = lr.varint()
                    keys.append(tile[lr.p:lr.p + kl].decode("utf-8"))
                    lr.p += kl
                elif f2 == 4 and w2 == 2:  # values
                    kl = lr.varint()
                    values.append(_parse_value(tile[lr.p:lr.p + kl]))
                    lr.p += kl
                elif f2 == 2 and w2 == 2:  # feature
                    kl = lr.varint()
                    fend = lr.p + kl
                    fr = _Reader(tile)
                    fr.p = lr.p
                    tags: list[int] = []
                    while fr.p < fend:
                        ft = fr.varint()
                        ff, fw = ft >> 3, ft & 7
                        if ff == 2 and fw == 2:  # packed tags
                            tl = fr.varint()
                            tend = fr.p + tl
                            while fr.p < tend:
                                tags.append(fr.varint())
                        else:
                            fr.skip(fw)
                    feat_tags.append(tags)
                    lr.p = fend
                else:
                    lr.skip(w2)
            props = []
            for tags in feat_tags:
                o = {}
                for i in range(0, len(tags) - 1, 2):
                    o[keys[tags[i]]] = values[tags[i + 1]]
                props.append(o)
            layers[name] = props
            top.p = end
        else:
            top.skip(wire)
    return layers


def main() -> int:
    # NOTE: Netbeheer's MapTiler key is domain-restricted (Referer-locked to their site);
    # off-site requests get 403 "Key usage restricted". We send the Referer so this bootstrap
    # works, and precisely because the key is not meant for off-site use we keep this a rare,
    # manual, ~monthly step — never in the daily cron. See DATA_SOURCES.md §4/§5.2.
    ua = {
        "User-Agent": "gridwatch-nl enumerate (contact: jeremy-graft@users.noreply.github.com)",
        "Referer": "https://data.partnersinenergie.nl/",
    }
    with httpx.Client(timeout=30, headers=ua, follow_redirects=True) as c:
        tile = c.get(TILE_URL).content
    if len(tile) < 1000:
        print(f"ERROR: tile suspiciously small ({len(tile)} bytes)", file=sys.stderr)
        return 1

    layers = decode_layers(tile)
    areas: dict[str, dict] = {}
    for layer, (op_const, direction) in GEBIED_LAYERS.items():
        for p in layers.get(layer, []):
            aid = p.get("id")
            if aid is None:
                continue
            a = areas.setdefault(
                aid, {"id": aid, "operator": op_const, "province": None, "directions": []}
            )
            if direction not in a["directions"]:
                a["directions"].append(direction)
            if not a["operator"] and p.get("RNB"):
                a["operator"] = p["RNB"]
            if not a["province"] and p.get("provincie"):
                a["province"] = p["provincie"]

    area_list = sorted(areas.values(), key=lambda a: a["id"])
    for a in area_list:
        a["directions"].sort()

    by_op: dict[str, int] = {}
    for a in area_list:
        by_op[a["operator"] or "UNKNOWN"] = by_op.get(a["operator"] or "UNKNOWN", 0) + 1

    payload = {
        "_comment": "Service-area id list for the capaciteitskaart. Generated by "
        "tools/enumerate_area_ids.py from the MapTiler z0 vector tile. "
        "The daily archiver (fetch.py) reads this and never touches MapTiler.",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_tile": f"https://api.maptiler.com/tiles/{TILESET_ID}/0/0/0.pbf",
        "total": len(area_list),
        "by_operator": dict(sorted(by_op.items())),
        "areas": area_list,
    }
    DATA_DIR.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUT} — {len(area_list)} areas")
    for op, n in sorted(by_op.items()):
        print(f"  {op}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
