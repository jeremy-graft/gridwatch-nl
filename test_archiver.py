#!/usr/bin/env python3
"""
Regression tests for the archiver's pure logic. No network — everything here runs offline
against fixtures and the committed data files, so it's safe in CI and fast.

Covers the two classes of bug that actually bit during development:
  1. The MVT decoder's varint/skip handling (a `self.p += self.varint()` evaluation-order bug
     silently misaligned the parser and produced garbage).
  2. fetch.py's decision logic — manifest fingerprinting (does a sweep trigger?) and operator
     bucketing (does an area land in the right file?).

Run:  python -m pytest test_archiver.py -q      (or: python test_archiver.py)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import fetch
from tools import enumerate_area_ids as enum_ids

ROOT = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# MVT decoder
# ---------------------------------------------------------------------------
def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _tag(field: int, wire: int) -> bytes:
    return _varint((field << 3) | wire)


def _len_delim(field: int, payload: bytes) -> bytes:
    return _tag(field, 2) + _varint(len(payload)) + payload


def _string_value(s: str) -> bytes:
    return _len_delim(1, s.encode("utf-8"))  # Value.string_value


def _int_value(i: int) -> bytes:
    return _tag(4, 0) + _varint(i)  # Value.int_value


def _feature(tag_pairs: list[int], geometry: bytes = b"\x09\x00\x00") -> bytes:
    """A Feature with packed tags (field 2) and a geometry field (field 4) that MUST be skipped."""
    packed = b"".join(_varint(v) for v in tag_pairs)
    return _len_delim(2, _len_delim(2, packed) + _len_delim(4, geometry))


def _layer(name: str, keys: list[str], values: list[bytes], features: list[bytes]) -> bytes:
    body = _len_delim(1, name.encode("utf-8"))
    body += _tag(5, 0) + _varint(4096)  # extent — a varint field that must be skipped
    for k in keys:
        body += _len_delim(3, k.encode("utf-8"))
    for v in values:
        body += _len_delim(4, v)
    for f in features:
        body += f
    return _len_delim(3, body)


def test_skip_length_delimited_does_not_misalign():
    """Regression: `self.p += self.varint()` evaluated the offset before advancing it, so a
    length-delimited skip landed short by the length prefix and derailed the parse."""
    payload = b"ABCDEFGH"
    buf = _len_delim(9, payload) + b"\xff"  # sentinel after the field
    r = enum_ids._Reader(buf)
    tag = r.varint()
    assert (tag >> 3, tag & 7) == (9, 2)
    r.skip(2)
    assert buf[r.p] == 0xFF, "skip(2) must land exactly past the payload"


def test_decode_layers_reads_properties_and_skips_geometry():
    tile = _layer(
        "rnb_gebied_afnamefgb",
        keys=["id", "RNB", "provincie"],
        values=[_string_value("OS TEXEL 10-1i"), _string_value("Liander"),
                _string_value("Noord-Holland")],
        features=[_feature([0, 0, 1, 1, 2, 2])],
    )
    layers = enum_ids.decode_layers(tile)
    assert layers["rnb_gebied_afnamefgb"] == [
        {"id": "OS TEXEL 10-1i", "RNB": "Liander", "provincie": "Noord-Holland"}
    ]


def test_decode_layers_handles_int_values_and_multiple_layers():
    tile = _layer("tennet_afnamefgb", ["color_code"], [_int_value(3)], [_feature([0, 0])])
    tile += _layer("tennet_gebied_afnamefgb", ["id"], [_string_value("Zeeland")],
                   [_feature([0, 0])])
    layers = enum_ids.decode_layers(tile)
    assert layers["tennet_afnamefgb"] == [{"color_code": 3}]
    assert layers["tennet_gebied_afnamefgb"] == [{"id": "Zeeland"}]


# ---------------------------------------------------------------------------
# Operator bucketing — decides which file an area is archived into
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "operator,expected",
    [
        ("Liander", "liander"),
        ("Enexis", "enexis"),
        ("Stedin", "stedin"),
        ("TenneT", "tennet"),
        ("Coteq, Enexis", "enexis"),   # compound operators must not fall through to "other"
        ("Enexis, Rendo", "enexis"),
        ("Westland", "other"),
        (None, "other"),
        ("", "other"),
    ],
)
def test_operator_bucket(operator, expected):
    assert fetch.operator_bucket(operator) == expected


def test_every_committed_area_buckets_to_a_known_file():
    areas = json.loads((ROOT / "data/area_ids.json").read_text(encoding="utf-8"))["areas"]
    valid = {"liander", "enexis", "stedin", "tennet", "other"}
    assert areas, "area_ids.json must not be empty"
    assert all(fetch.operator_bucket(a.get("operator")) in valid for a in areas)


# ---------------------------------------------------------------------------
# Manifest fingerprinting — decides whether the expensive sweep runs
# ---------------------------------------------------------------------------
def _manifest(update_id: str, updates: list[tuple[str, str, str]]) -> dict:
    return {
        "dataUpdate": {"id": update_id, "executedOn": "2026-07-17T11:30:04Z"},
        "gridOperatorUpdates": [
            {"gridOperator": op, "categoryShort": cat, "updatedAt": ts,
             "category": cat, "id": i}
            for i, (op, cat, ts) in enumerate(updates)
        ],
    }


BASE_UPDATES = [("Liander", "WR", "2026-05-29T02:00:00+02:00"),
                ("Enexis", "WR", "2026-07-15T02:00:00+02:00")]


def test_fingerprint_is_stable_under_reordering():
    """The API's array order must not be mistaken for a data change."""
    a = fetch.manifest_fingerprint(_manifest("uuid-1", BASE_UPDATES))
    b = fetch.manifest_fingerprint(_manifest("uuid-1", list(reversed(BASE_UPDATES))))
    assert a == b


def test_fingerprint_changes_when_an_operator_republishes():
    a = fetch.manifest_fingerprint(_manifest("uuid-1", BASE_UPDATES))
    bumped = [("Liander", "WR", "2026-08-01T02:00:00+02:00"), BASE_UPDATES[1]]
    assert fetch.manifest_fingerprint(_manifest("uuid-1", bumped)) != a


def test_fingerprint_changes_when_pipeline_id_changes():
    a = fetch.manifest_fingerprint(_manifest("uuid-1", BASE_UPDATES))
    assert fetch.manifest_fingerprint(_manifest("uuid-2", BASE_UPDATES)) != a


def test_fingerprint_triggers_on_pipeline_rerun_even_if_updatedAt_frozen():
    """Measured 2026-07-30: the ingest pipeline re-ran and 62 real changes landed (relief
    years moved) while every per-operator updatedAt stayed frozen. Triggering on updatedAt
    alone would have missed them, so a new dataUpdate id MUST still force a sweep."""
    old = fetch.manifest_fingerprint(_manifest("run-A", BASE_UPDATES))
    new = fetch.manifest_fingerprint(_manifest("run-B", BASE_UPDATES))  # same updatedAt values
    assert new != old, "a pipeline re-run must trigger a sweep even with frozen updatedAt"


def test_fingerprint_tolerates_missing_fields():
    assert fetch.manifest_fingerprint({}) == {"dataUpdateId": None, "updates": []}
    assert fetch.manifest_fingerprint(
        {"dataUpdate": None, "gridOperatorUpdates": None}
    ) == {"dataUpdateId": None, "updates": []}


def test_committed_manifest_fingerprints_and_is_self_consistent():
    m = json.loads((ROOT / "data/manifests.json").read_text(encoding="utf-8"))
    fp = fetch.manifest_fingerprint(m)
    assert fp["dataUpdateId"], "real manifest must yield a pipeline id"
    assert fp["updates"], "real manifest must yield operator updates"
    assert fetch.manifest_fingerprint(m) == fp, "fingerprint must be deterministic"


# ---------------------------------------------------------------------------
# Volatile-field stripping — without this, one ingest re-run produces a ~5100-line
# diff of rotating row ids that buries the ~60 real changes.
# ---------------------------------------------------------------------------
def test_normalize_area_drops_rotating_project_ids():
    sa = {"id": "X", "projects": [{"id": 69807, "name": "A", "gridOperator": "Liander",
                                   "year": "2029"}]}
    out = fetch.normalize_area(sa)
    assert "id" not in out["projects"][0], "rotating project row id must be stripped"
    assert out["projects"][0]["name"] == "A" and out["projects"][0]["year"] == "2029"
    assert out["id"] == "X", "the area's own id is stable and must be kept"


def test_normalize_area_is_order_insensitive():
    """The backend returns projects in a non-deterministic order; identical content must
    canonicalise identically regardless of arrival order."""
    p1 = {"id": 1, "name": "Alpha", "gridOperator": "Liander", "dateString": "2029"}
    p2 = {"id": 2, "name": "Beta", "gridOperator": "TenneT", "dateString": "2030"}
    a = fetch.normalize_area({"projects": [p1, p2]})
    b = fetch.normalize_area({"projects": [dict(p2, id=99), dict(p1, id=98)]})
    assert fetch.canonical(a) == fetch.canonical(b)


def test_id_churn_alone_produces_no_diff_but_real_change_does():
    """The core regression: an ingest re-run that only rotates ids must produce an identical
    file, while a genuine relief-year move must still show up."""
    before = {"projects": [{"id": 69807, "name": "Oldenzaal", "gridOperator": "Enexis",
                            "year": "2026"}]}
    id_churn_only = {"projects": [{"id": 70398, "name": "Oldenzaal", "gridOperator": "Enexis",
                                   "year": "2026"}]}
    real_move = {"projects": [{"id": 70398, "name": "Oldenzaal", "gridOperator": "Enexis",
                               "year": "2029"}]}
    base = fetch.canonical(fetch.normalize_area(before))
    assert fetch.canonical(fetch.normalize_area(id_churn_only)) == base
    assert fetch.canonical(fetch.normalize_area(real_move)) != base


def test_normalize_manifest_strips_row_ids_keeps_dataupdate():
    m = _manifest("uuid-1", BASE_UPDATES)
    out = fetch.normalize_manifest(m)
    assert all("id" not in u for u in out["gridOperatorUpdates"])
    assert out["dataUpdate"]["id"] == "uuid-1", "dataUpdate is the change trigger — keep it"
    # sorted deterministically regardless of input order
    shuffled = fetch.normalize_manifest(_manifest("uuid-1", list(reversed(BASE_UPDATES))))
    assert fetch.canonical(out) == fetch.canonical(shuffled)


def test_normalize_does_not_mutate_its_input():
    sa = {"projects": [{"id": 1, "name": "A"}]}
    fetch.normalize_area(sa)
    assert sa["projects"][0]["id"] == 1, "raw response must not be mutated in place"


# ---------------------------------------------------------------------------
# Canonicalisation — stable diffs are the whole point of the archive
# ---------------------------------------------------------------------------
def test_canonical_sorts_keys_and_is_newline_terminated():
    out = fetch.canonical({"b": 1, "a": {"d": 2, "c": 3}})
    assert out.endswith("\n")
    assert out.index('"a"') < out.index('"b"')
    assert out.index('"c"') < out.index('"d"')


def test_canonical_is_idempotent_and_preserves_unicode():
    obj = {"name": "OS 'S-GRAVELAND 10-1i", "prov": "Fryslân"}
    once = fetch.canonical(obj)
    assert fetch.canonical(json.loads(once)) == once
    assert "Fryslân" in once, "must not escape non-ASCII (keeps diffs readable)"


# ---------------------------------------------------------------------------
# Guard rails — a block must never be mistaken for data
# ---------------------------------------------------------------------------
class _Resp:
    def __init__(self, status, ctype, text):
        self.status_code = status
        self.headers = {"content-type": ctype}
        self.text = text
        self.request = type("R", (), {"url": "https://example.test/api/x"})()

    def json(self):
        return json.loads(self.text)


def test_guard_json_rejects_403_and_html():
    with pytest.raises(fetch.BlockedError):
        fetch._guard_json(_Resp(403, "application/json", "{}"))
    with pytest.raises(fetch.BlockedError):
        fetch._guard_json(_Resp(200, "text/html", "<html>Just a moment...</html>"))


def test_guard_json_retries_on_5xx_and_passes_valid_json():
    with pytest.raises(fetch.TransientError):
        fetch._guard_json(_Resp(503, "application/json", "{}"))
    assert fetch._guard_json(_Resp(200, "application/json", '{"status":"OK"}')) == {"status": "OK"}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
