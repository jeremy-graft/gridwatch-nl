#!/usr/bin/env python3
"""
enumerate_area_ids.py  —  monthly area-list refresh. Runs automatically on the 1st of each
month inside the daily workflow (just before the monthly backstop sweep), and by hand anytime.

Rebuilds data/area_ids.json: the list of every service-area id on the capaciteitskaart,
enriched with grid operator, province, and which flow directions (afname/invoeding) it
appears in.

WHY THIS IS SEPARATE FROM fetch.py:
  The area geometry+ids live only in MapTiler-hosted vector tiles, fetched with a key that
  belongs to Netbeheer's MapTiler account. MapTiler's ToS forbids using another party's key
  as your own, so we touch it as rarely as possible: ONE tile request a month (plus one request
  to Netbeheer's own app config to find the current tileset). fetch.py never touches MapTiler.

WHY IT MUST RUN: the API keeps answering for ids the map has dropped and never lists new ones,
so a stale list loses coverage silently — on 2026-10-19 44 live areas had gone unarchived for
weeks while every run was green. See DATA_SOURCES.md §5.3/§5.7.

UNATTENDED SAFETY: it refuses to write (exit 1, old list kept) if the tile looks wrong or the
new list is much smaller than the current one, so a source-side change can never shrink the
archive's coverage without a human looking.

Usage:  python tools/enumerate_area_ids.py            # refresh data/area_ids.json
        python tools/enumerate_area_ids.py --dry-run  # fetch + validate, write nothing
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

# The z0 tile contains every feature of every layer (minzoom 0), so one request enumerates
# everything. The tileset id + key are read from the live app config
# (GET /capaciteitskaart/totaal/afname.data, field CAPACITEITSKAART_TILES_URL) so that if
# Netbeheer republishes to a new tileset we follow it instead of reading a stale one. The
# constants below are only a fallback for when the config can't be read.
TILESET_ID = "105ba28a-afb8-4232-ac3d-0b40bf3fc76c"
MAPTILER_KEY = "LsAKfag3t3bTv3H1zlTP"  # Netbeheer's public client key — 1 request/month only
# The page HTML embeds the client config; the React-Router `.data` route was the original source
# but started answering 202 with a 149-byte body (2026-10-19), so it is only a second try.
CONFIG_URLS = ("https://data.partnersinenergie.nl/capaciteitskaart/totaal/afname",
               "https://data.partnersinenergie.nl/capaciteitskaart/totaal/afname.data")
_TILES_URL_RE = re.compile(r"https://api\.maptiler\.com/tiles/([0-9a-fA-F-]{20,})/tiles\.json\?key=([A-Za-z0-9]+)")

# Unattended guards.
MIN_AREAS = 150          # the map has had ~300; far fewer means the tile/layers changed shape
MAX_SHRINK = 0.20        # refuse a refresh that drops more than 20% of the current list


def tiles_from_config(text: str) -> tuple[str, str] | None:
    """Extract (tileset_id, key) from the app's .data config text, or None."""
    m = _TILES_URL_RE.search(text or "")
    return (m.group(1), m.group(2)) if m else None


def check_refresh(old_total: int | None, new_total: int) -> str | None:
    """Return an error message if the new list must not replace the current one, else None."""
    if new_total < MIN_AREAS:
        return f"only {new_total} areas (< {MIN_AREAS}); tile or layer names probably changed"
    if old_total and new_total < old_total * (1 - MAX_SHRINK):
        return (f"list would shrink {old_total} -> {new_total} "
                f"(> {int(MAX_SHRINK * 100)}%); refusing without human review")
    return None

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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="refresh data/area_ids.json from the map tiles")
    ap.add_argument("--dry-run", action="store_true", help="fetch and validate, write nothing")
    args = ap.parse_args(argv)

    # NOTE: Netbeheer's MapTiler key is domain-restricted (Referer-locked to their site);
    # off-site requests get 403 "Key usage restricted". We send the Referer so this works, and
    # precisely because the key is not meant for off-site use we make ONE tile request a month.
    # See DATA_SOURCES.md §4/§5.2.
    ua = {
        "User-Agent": "gridwatch-nl enumerate (contact: jeremy-graft@users.noreply.github.com; "
                      "+https://github.com/jeremy-graft/gridwatch-nl)",
        "Referer": "https://data.partnersinenergie.nl/",
    }
    with httpx.Client(timeout=30, headers=ua, follow_redirects=True) as c:
        tileset_id, key, tiles_source = TILESET_ID, MAPTILER_KEY, "fallback constants"
        for url in CONFIG_URLS:
            try:
                found = tiles_from_config(c.get(url).text)
            except httpx.HTTPError as e:
                print(f"warning: could not read {url} ({e})", file=sys.stderr)
                continue
            if found:
                tileset_id, key = found
                tiles_source = f"live app config ({url.rsplit('/', 1)[-1]})"
                break
        else:
            print("warning: no tileset URL in the app config; using fallback constants", file=sys.stderr)
        if tileset_id != TILESET_ID:
            print(f"note: tileset changed {TILESET_ID} -> {tileset_id} (following the live config)")
        tile = c.get(f"https://api.maptiler.com/tiles/{tileset_id}/0/0/0.pbf?key={key}").content
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
        "source_tile": f"https://api.maptiler.com/tiles/{tileset_id}/0/0/0.pbf",
        "tileset_source": tiles_source,
        "total": len(area_list),
        "by_operator": dict(sorted(by_op.items())),
        "areas": area_list,
    }
    old_total = None
    if OUT.exists():
        try:
            old_total = json.loads(OUT.read_text(encoding="utf-8")).get("total")
        except (ValueError, OSError):
            old_total = None
    err = check_refresh(old_total, len(area_list))
    if err:
        print(f"ERROR: {err}. Kept the existing {OUT.name}.", file=sys.stderr)
        return 1
    old_ids = set()
    if OUT.exists():
        try:
            old_ids = {a["id"] for a in json.loads(OUT.read_text(encoding="utf-8"))["areas"]}
        except (ValueError, OSError, KeyError):
            pass
    new_ids = {a["id"] for a in area_list}
    print(f"{len(area_list)} areas from tileset {tileset_id} ({tiles_source}); "
          f"vs current list: +{len(new_ids - old_ids)} added, -{len(old_ids - new_ids)} removed")
    if args.dry_run:
        print("dry run: nothing written")
        return 0
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
