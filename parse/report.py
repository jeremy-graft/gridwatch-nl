#!/usr/bin/env python3
"""
parse/report.py — the "Netcongestie Monitor": a persistence-aware report over the archive.

Reads ONLY the git history of data/ (never the network), and writes:
  REPORT.md               — human-readable monthly report
  parse/report_data.json  — the same numbers, machine-readable (seed for any later product)

Design rules (DATA_SOURCES.md §5.6–5.8):
  * A project's identity across snapshots is (area, gridOperator, name) — never `id`.
  * `year >= 2090` is a "no date" sentinel → reported as WITHDRAWN, excluded from year math.
  * Past-dated years are flagged, not trusted.
  * "9.2 MW" / "-" strings are parsed; "-" → None.
  * A project's date is its PUBLISHED DELIVERY WINDOW from `dateString` ("Tussen 2031 en 2033",
    "2029 - Q4", "2026"), never the `year` field: for ranged projects the source alternates
    `year` between the window's start and end across publications, which looks like constant
    slipping when nothing changed (measured 2026-10-19: 35 of 35 Stedin "moves" were this).
  * Relief-date moves are classified by PERSISTENCE, as a guard against corrections and
    one-off publication glitches:
      stable      — never changed
      reverted    — changed, but is back at its original value
      persisted   — changed and currently differs from original
        confirmed   — the new value has held for >= 2 consecutive ingests
        unconfirmed — only seen in the latest ingest; may still revert
    Only CONFIRMED moves are called slippage. Everything else is reported as what it is.

Run:  python parse/report.py          (needs full git history: fetch-depth 0 in CI)
"""
from __future__ import annotations

import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT_MD = ROOT / "REPORT.md"
REPORT_JSON = ROOT / "parse" / "report_data.json"
SUMMARY_NL = ROOT / "SAMENVATTING.md"
BUCKETS = ("liander", "enexis", "stedin", "tennet", "other")
SENTINEL_YEAR = 2090           # >= this means "no date"
MIN_TRACK_FOR_RELIABILITY = 3  # a project must be seen in >= this many ingests to be scored


# ----------------------------------------------------------------------------- parsing
def parse_mw(s) -> float | None:
    """'9.2 MW' -> 9.2 ; '-' / None / '' -> None."""
    if s is None:
        return None
    m = re.match(r"\s*([\d.]+)", str(s))
    return float(m.group(1)) if m else None


def parse_count(s) -> int | None:
    """'23' -> 23 ; '-' -> None."""
    if s is None:
        return None
    m = re.match(r"\s*(\d+)", str(s))
    return int(m.group(1)) if m else None


def parse_year(y) -> int | None:
    if y is None:
        return None
    m = re.match(r"\s*(\d{4})", str(y))
    return int(m.group(1)) if m else None


_QUARTER_RE = re.compile(r"(\d{4})\s*-\s*Q([1-4])", re.I)
_RANGE_RE = re.compile(r"(\d{4})\D+(\d{4})")


def parse_window(p: dict) -> tuple | None:
    """A project's published delivery window as (start, end, quarter).

    'Tussen 2031 en 2033' -> (2031, 2033, 0) · '2029 - 2030' -> (2029, 2030, 0)
    '2029 - Q4' -> (2029, 2029, 4)          · '2026' -> (2026, 2026, 0)
    Falls back to the `year` field only when `dateString` is absent: `year` is not stable for
    ranged projects (it alternates between the window's start and end; DATA_SOURCES.md §5.8).
    """
    ds = (p.get("dateString") or "").strip()
    m = _QUARTER_RE.search(ds)
    if m:
        y = int(m.group(1))
        return (y, y, int(m.group(2)))
    m = _RANGE_RE.search(ds)
    if m:
        a, b = sorted((int(m.group(1)), int(m.group(2))))
        return (a, b, 0)
    y = parse_year(ds) or parse_year(p.get("year"))
    return (y, y, 0) if y else None


def fmt_window(w) -> str:
    if w is None:
        return "–"
    if isinstance(w, int):
        return str(w)
    lo, hi, q = w
    if hi >= SENTINEL_YEAR:
        return f"{lo}–open"
    if lo == hi:
        return f"{lo}" + (f" Q{q}" if q else "")
    return f"{lo}–{hi}"


def _window_points(w: tuple) -> tuple[float, float]:
    """(earliest, latest) delivery moment in fractional years. A bare year means 'during that
    year', i.e. [y, y+1); a quarter narrows it to that quarter."""
    lo, hi, q = w
    if q:
        return lo + (q - 1) / 4, hi + q / 4
    return float(lo), float(hi + 1)


def window_delta(a, b) -> int:
    """Signed shift in whole years, driven by the window's end, or its start if the end held."""
    if isinstance(a, int) or isinstance(b, int):
        return int(b) - int(a)
    (s0, e0), (s1, e1) = _window_points(a), _window_points(b)
    d = e1 - e0 if e1 != e0 else s1 - s0
    return int(round(d)) if abs(d) >= 1 else (1 if d > 0 else -1 if d < 0 else 0)


def classify_year(y: int | None, ref_year: int) -> str:
    """'ok' | 'withdrawn' (sentinel) | 'past' | 'none'."""
    if y is None:
        return "none"
    if y >= SENTINEL_YEAR:
        return "withdrawn"
    if y < ref_year:
        return "past"
    return "ok"


def project_key(area_id: str, p: dict) -> tuple:
    return (area_id.strip(), (p.get("gridOperator") or "").strip(), (p.get("name") or "").strip())


# ----------------------------------------------------------------------------- git loading
def _git(*args) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8",
                          cwd=ROOT).stdout


def _show(sha: str, path: str) -> str:
    return _git("show", f"{sha}:{path}")


def load_snapshots() -> list[dict]:
    """One entry per DISTINCT source ingest (deduped on dataUpdate.executedOn), oldest first:
    {ingest, captured, sha, areas: {id: serviceArea}, live_ids: set, meta}

    For each ingest the LAST commit carrying it is used, not the first: a later commit with the
    same ingest is either a no-op daily run (identical data) or a repair sweep (e.g. after an
    area-list refresh picked up areas the first sweep missed), so the last one is the most
    complete record of that publication."""
    last_for: dict[str, tuple[str, str]] = {}
    order: list[str] = []
    for line in _git("log", "--reverse", "--format=%H %cI", "--", "data/").splitlines():
        if not line.strip():
            continue
        sha, captured = line.split()
        m = _show(sha, "data/manifests.json")
        if not m.strip():
            continue
        ingest = (json.loads(m).get("dataUpdate") or {}).get("executedOn", "")[:10]
        if not ingest:
            continue
        if ingest not in last_for:
            order.append(ingest)
        last_for[ingest] = (sha, captured)
    out = []
    for ingest in order:
        sha, captured = last_for[ingest]
        areas = {}
        for b in BUCKETS:
            t = _show(sha, f"data/serviceareas/{b}.json")
            if t.strip():
                areas.update(json.loads(t))
        ids_txt = _show(sha, "data/area_ids.json")
        id_list = json.loads(ids_txt)["areas"] if ids_txt.strip() else []
        live = {a["id"].strip() for a in id_list} if id_list else set(areas)
        meta = {a["id"].strip(): {"operator": a.get("operator"), "province": a.get("province")}
                for a in id_list}
        if areas:
            out.append({"ingest": ingest, "captured": captured[:10], "sha": sha[:7],
                        "areas": areas, "live_ids": live, "meta": meta})
    return out


# ----------------------------------------------------------------------------- analysis
def is_tennet(aid: str, sa: dict, meta: dict) -> bool:
    """TenneT's high-voltage regions overlap the distribution operators' areas geographically and
    measure a different queue, so the two must never be summed into one 'national' figure."""
    op = (meta.get(aid.strip()) or {}).get("operator") or sa.get("rnb") or ""
    return "tennet" in op.lower()


def _queue_sums(areas: list[dict]) -> dict:
    return {
        "queue_withdrawal_mw": round(sum(parse_mw(a.get("queueWithdrawal")) or 0 for a in areas)),
        "queue_injection_mw": round(sum(parse_mw(a.get("queueInjection")) or 0 for a in areas)),
        "requests_withdrawal": sum(parse_count(a.get("uniqueRequestsWithdrawal")) or 0 for a in areas),
        "requests_injection": sum(parse_count(a.get("uniqueRequestsInjection")) or 0 for a in areas),
    }


def queue_trend(snaps: list[dict]) -> list[dict]:
    """Per publication: totals over live areas, split into the regional (distribution) grids and
    TenneT. The un-split fields are kept for backward compatibility but should not be headlined."""
    rows = []
    for s in snaps:
        meta = s.get("meta", {})
        live_pairs = [(aid, sa) for aid, sa in s["areas"].items() if aid.strip() in s["live_ids"]]
        live = [sa for _, sa in live_pairs]
        regional = [sa for aid, sa in live_pairs if not is_tennet(aid, sa, meta)]
        tennet = [sa for aid, sa in live_pairs if is_tennet(aid, sa, meta)]
        rows.append({
            "regional": {**_queue_sums(regional), "areas": len(regional)},
            "tennet": {**_queue_sums(tennet), "areas": len(tennet)},
            "ingest": s["ingest"],
            "live_areas": len(live),
            "queue_withdrawal_mw": round(sum(parse_mw(a.get("queueWithdrawal")) or 0 for a in live)),
            "queue_injection_mw": round(sum(parse_mw(a.get("queueInjection")) or 0 for a in live)),
            "requests_withdrawal": sum(parse_count(a.get("uniqueRequestsWithdrawal")) or 0 for a in live),
            "requests_injection": sum(parse_count(a.get("uniqueRequestsInjection")) or 0 for a in live),
            "areas_with_withdrawal_queue": sum(1 for a in live if (parse_mw(a.get("queueWithdrawal")) or 0) > 0),
        })
    return rows


def latest_like_for_like(snaps: list[dict]) -> dict | None:
    """Change between the last two publications over the areas live in BOTH, so inventory churn
    (areas retired/added) can't masquerade as a change in the queue."""
    if len(snaps) < 2:
        return None
    a, b = snaps[-2], snaps[-1]
    both = sorted(a["live_ids"] & b["live_ids"])
    out = {"from": a["ingest"], "to": b["ingest"], "areas": len(both)}
    for grid, pick in (("regional", False), ("tennet", True)):
        ids = [i for i in both if i in a["areas"] and i in b["areas"]
               and is_tennet(i, b["areas"][i], b.get("meta", {})) == pick]
        out[grid] = {"areas": len(ids),
                     "before": _queue_sums([a["areas"][i] for i in ids]),
                     "after": _queue_sums([b["areas"][i] for i in ids])}
    return out


def track_series(snaps: list[dict]):
    """Return (project_tracks, area_tracks).
    project_tracks: key -> [(ingest, window)]  published delivery window (see parse_window)
    area_tracks:    (area, direction) -> [(ingest, year)]  for yearSolvedWithdrawal/Injection"""
    proj, area = defaultdict(list), defaultdict(list)
    for s in snaps:
        for aid, sa in s["areas"].items():
            if aid.strip() not in s["live_ids"]:
                continue
            for p in (sa.get("projects") or []):
                proj[project_key(aid, p)].append((s["ingest"], parse_window(p)))
            for d, f in (("afname", "yearSolvedWithdrawal"), ("invoeding", "yearSolvedInjection")):
                area[(aid.strip(), d)].append((s["ingest"], parse_year(sa.get(f))))
    return proj, area


def classify_move(seq: list[tuple[str, int | None]], ref_year: int) -> dict:
    """Persistence classification of one year-series. Withdrawals (sentinel) are their own
    outcome; past-dated values are excluded from slip/pull arithmetic."""
    vals = [(i, y) for i, y in seq if y is not None]
    if len(vals) < 2:
        return {"status": "insufficient", "n": len(vals)}
    first_i, first = vals[0]
    last_i, last = vals[-1]
    if classify_year(last, ref_year) == "withdrawn" and classify_year(first, ref_year) != "withdrawn":
        return {"status": "withdrawn", "n": len(vals), "first": first, "since": last_i}
    if len({y for _, y in vals}) == 1:
        return {"status": "stable", "n": len(vals), "year": first}
    if last == first:
        return {"status": "reverted", "n": len(vals), "year": first,
                "excursion": sorted({y for _, y in vals} - {first})}
    confirmed = vals[-1][1] == vals[-2][1]
    kind = "slip" if last > first else "pull"
    # when did the current value first start holding?
    changed_at = last_i
    for i, y in reversed(vals):
        if y != last:
            break
        changed_at = i
    return {"status": "persisted", "kind": kind, "confirmed": confirmed, "n": len(vals),
            "first": first, "last": last, "delta": last - first, "changed_at": changed_at,
            "past_dated": any(classify_year(y, ref_year) == "past" for _, y in vals)}


def classify_window(seq: list[tuple[str, tuple | None]], ref_year: int) -> dict:
    """Persistence classification of a project's published-window series. Same statuses as
    classify_move. 'withdrawn' = the window lost its end date (end moved to the sentinel)."""
    vals = [(i, w) for i, w in seq if w is not None]
    if len(vals) < 2:
        return {"status": "insufficient", "n": len(vals)}
    first_i, first = vals[0]
    last_i, last = vals[-1]
    if last[1] >= SENTINEL_YEAR > first[1]:
        return {"status": "withdrawn", "n": len(vals), "first": first, "since": last_i,
                "first_s": fmt_window(first)}
    if len({w for _, w in vals}) == 1:
        return {"status": "stable", "n": len(vals), "year": first, "year_s": fmt_window(first)}
    if last == first:
        return {"status": "reverted", "n": len(vals), "year": first, "year_s": fmt_window(first),
                "excursion": sorted({fmt_window(w) for _, w in vals} - {fmt_window(first)})}
    confirmed = vals[-1][1] == vals[-2][1]
    (s0, e0), (s1, e1) = _window_points(first), _window_points(last)
    kind = "slip" if (e1, s1) > (e0, s0) else "pull"
    changed_at = last_i
    for i, w in reversed(vals):
        if w != last:
            break
        changed_at = i
    return {"status": "persisted", "kind": kind, "confirmed": confirmed, "n": len(vals),
            "first": first, "last": last, "delta": window_delta(first, last),
            "first_s": fmt_window(first), "last_s": fmt_window(last), "changed_at": changed_at,
            "past_dated": last[1] < ref_year}


def summarize_moves(tracks: dict, ref_year: int, latest_ingest: str, classify=None) -> dict:
    classify = classify or classify_move
    counts = Counter()
    confirmed, unconfirmed, reverted, withdrawn = [], [], [], []
    for key, seq in tracks.items():
        c = classify(seq, ref_year)
        if c["status"] == "persisted":
            label = ("confirmed_" if c["confirmed"] else "unconfirmed_") + c["kind"]
        else:
            label = c["status"]
        vals = [(i, y) for i, y in seq if y is not None]
        dropped = bool(vals) and vals[-1][0] != latest_ingest
        if c["status"] == "persisted" and not c["confirmed"] and dropped:
            # It moved in its final observation and then left the map (area retired/renamed or
            # project removed). It can never be confirmed, and it did NOT move "in the latest
            # publication" - count it separately instead of listing it as unconfirmed.
            label = "dropped_after_move"
        counts[label] += 1
        if label == "dropped_after_move":
            pass
        elif c["status"] == "persisted" and not c.get("past_dated"):
            (confirmed if c["confirmed"] else unconfirmed).append((key, c))
        elif c["status"] == "reverted":
            reverted.append((key, c))
        elif c["status"] == "withdrawn":
            withdrawn.append((key, c))
    # moves that happened IN the latest ingest specifically
    this_cycle = []
    for key, seq in tracks.items():
        vals = [(i, y) for i, y in seq if y is not None]
        if len(vals) >= 2 and vals[-1][0] == latest_ingest and vals[-1][1] != vals[-2][1]:
            this_cycle.append((key, vals[-2][1], vals[-1][1]))
    return {"counts": dict(counts), "confirmed": confirmed, "unconfirmed": unconfirmed,
            "reverted": reverted, "withdrawn": withdrawn, "this_cycle": this_cycle}


COHORT_ORDER = ("slipped", "slipped_unconfirmed", "withdrawn", "overdue", "earlier", "retired", "kept")


def promise_cohort(tracks: dict, year: int, first_ingest: str, ref_year: int,
                   latest_ingest: str | None = None) -> dict:
    """The promise ledger: everything that promised `year` at the FIRST publication in the
    archive, and what it says now. This is the receipt-keeping view: the source only ever shows
    the current promise, so the original one exists only here.

    status per entry:
      kept                - still promises `year` (including ones that wobbled and came back)
      slipped             - pushed later, confirmed (held for >= 2 publications)
      slipped_unconfirmed - pushed later in the latest publication only
      earlier             - pulled forward
      withdrawn           - date replaced by the 'no date' sentinel
      overdue             - `year` has passed and the source still shows it unresolved
      retired             - the area is no longer on the map (retired or renamed by the source);
                            its promise can no longer be checked. Renames can't be linked to the
                            new id, so these are reported separately, never as 'kept'.
    """
    rows = []
    for key, seq in tracks.items():
        vals = [(i, y) for i, y in seq if y is not None]
        if not vals or vals[0][0] != first_ingest or vals[0][1] != year:
            continue
        c = classify_move(seq, ref_year)
        last = vals[-1][1]
        if latest_ingest and vals[-1][0] != latest_ingest:
            status = "retired"
        elif c["status"] in ("stable", "reverted", "insufficient"):
            status = "overdue" if ref_year > year else "kept"
        elif c["status"] == "withdrawn":
            status = "withdrawn"
        elif c["kind"] == "slip":
            status = "slipped" if c["confirmed"] else "slipped_unconfirmed"
        else:
            status = "earlier"
        rows.append({"key": list(key), "promised": year, "now": last, "status": status})
    rows.sort(key=lambda r: (COHORT_ORDER.index(r["status"]), -(r["now"] or 0), r["key"]))
    return {"year": year, "since": first_ingest, "total": len(rows),
            "counts": dict(Counter(r["status"] for r in rows)), "rows": rows}


def reliability_by_operator(proj_tracks: dict, ref_year: int) -> list[dict]:
    stat = defaultdict(lambda: {"tracked": 0, "moved": 0, "reverted": 0, "confirmed": 0})
    for (aid, op, name), seq in proj_tracks.items():
        vals = [v for _, v in seq if v is not None
                and (not isinstance(v, int) or classify_year(v, ref_year) == "ok")]
        if len(vals) < MIN_TRACK_FOR_RELIABILITY:
            continue
        s = stat[op or "?"]
        s["tracked"] += 1
        if len(set(vals)) > 1:
            s["moved"] += 1
            if vals[-1] == vals[0]:
                s["reverted"] += 1
            elif vals[-1] == vals[-2]:
                s["confirmed"] += 1
    rows = []
    for op, s in stat.items():
        rows.append({"operator": op, **s,
                     "moved_pct": round(100 * s["moved"] / s["tracked"], 1) if s["tracked"] else None,
                     "reverted_pct_of_moved": round(100 * s["reverted"] / s["moved"], 1) if s["moved"] else None})
    return sorted(rows, key=lambda r: -(r["moved_pct"] or 0))


def inventory_changes(snaps: list[dict]) -> list[dict]:
    out = []
    for a, b in zip(snaps, snaps[1:]):
        added, retired = b["live_ids"] - a["live_ids"], a["live_ids"] - b["live_ids"]
        if added or retired:
            out.append({"ingest": b["ingest"], "added": len(added), "retired": len(retired),
                        "added_ids": sorted(added)[:12], "retired_ids": sorted(retired)[:12]})
    return out


# ----------------------------------------------------------------------------- rendering
def _pct(a, b):
    return f"{100 * (b - a) / a:+.1f}%" if a else "n/a"


def _area_table(rows):
    if not rows:
        return ["_none_", ""]
    out = ["| area | direction | was | now | change | held for |", "|---|---|---:|---:|---:|---:|"]
    for (aid, d), m in sorted(rows, key=lambda x: -abs(x[1]["delta"]))[:25]:
        out.append(f"| `{aid}` | {d} | {m['first']} | {m['last']} | {m['delta']:+d}y | {m['n']} cycles |")
    return out + [""]


def _proj_table(rows):
    if not rows:
        return ["_none_", ""]
    out = ["| area | operator | project | was | now | change |", "|---|---|---|---:|---:|---:|"]
    for (aid, op, name), m in sorted(rows, key=lambda x: -abs(x[1]["delta"]))[:25]:
        out.append(f"| `{aid}` | {op} | {name[:48]} | {m.get('first_s', m['first'])} | "
                   f"{m.get('last_s', m['last'])} | {m['delta']:+d}y |")
    return out + [""]


def _area_label(aid: str, meta: dict) -> str:
    m = meta.get(aid) or {}
    bits = [b for b in (m.get("operator"), m.get("province")) if b]
    return f"`{aid}`" + (f" ({', '.join(bits)})" if bits else "")


COHORT_LABELS_EN = {"slipped": "pushed later (confirmed)",
                    "slipped_unconfirmed": "pushed later (latest publication only)",
                    "earlier": "pulled forward", "withdrawn": "date withdrawn",
                    "retired": "area no longer on the map (retired or renamed)"}


def render(snaps, qt, area_mv, proj_mv, rel, inv, generated, cohorts=(), lfl=None) -> str:
    first, last = snaps[0], snaps[-1]
    q0, q1 = qt[0], qt[-1]
    days = (datetime.fromisoformat(last["ingest"]) - datetime.fromisoformat(first["ingest"])).days
    L = []
    L += ["# Netcongestie Monitor", "",
          f"*Data as of {generated}. Generated from the [gridwatch-nl](https://github.com/jeremy-graft/gridwatch-nl) "
          f"archive. Covers **{len(snaps)} source publications** from **{first['ingest']}** to "
          f"**{last['ingest']}** ({q1['live_areas']} live areas). Indicative only — see Methodology.*", ""]

    c = area_mv["counts"]
    cs, cp = c.get("confirmed_slip", 0), c.get("confirmed_pull", 0)
    rv, wd = c.get("reverted", 0), c.get("withdrawn", 0)
    uc = c.get("unconfirmed_slip", 0) + c.get("unconfirmed_pull", 0)
    dr = c.get("dropped_after_move", 0)
    r0, r1, t0, t1 = q0["regional"], q1["regional"], q0["tennet"], q1["tennet"]
    L += ["## Headline", "",
          f"- **Regional grids — requests waiting for withdrawal capacity: {r0['requests_withdrawal']:,} → "
          f"{r1['requests_withdrawal']:,} ({_pct(r0['requests_withdrawal'], r1['requests_withdrawal'])})** "
          f"since {first['ingest']}; withdrawal queue {r0['queue_withdrawal_mw']:,} → "
          f"{r1['queue_withdrawal_mw']:,} MW.",
          f"- **TenneT (high voltage) — withdrawal queue: {t0['queue_withdrawal_mw']:,} → "
          f"{t1['queue_withdrawal_mw']:,} MW ({_pct(t0['queue_withdrawal_mw'], t1['queue_withdrawal_mw'])})**; "
          f"injection {t0['queue_injection_mw']:,} → {t1['queue_injection_mw']:,} MW. Reported separately: "
          "TenneT's regions overlap the regional areas and measure a different queue.",
          f"- **{q1['areas_with_withdrawal_queue']} of {q1['live_areas']} areas** currently have a withdrawal queue."]
    if lfl:
        for grid, label in (("regional", "regional grids"), ("tennet", "TenneT")):
            g = lfl[grid]
            b0, b1 = g["before"], g["after"]
            if b0 != b1:
                L.append(f"- **Latest publication ({lfl['from']} → {lfl['to']}), like-for-like over the "
                         f"{g['areas']} {label} areas present in both:** withdrawal queue "
                         f"{b0['queue_withdrawal_mw']:,} → {b1['queue_withdrawal_mw']:,} MW "
                         f"({_pct(b0['queue_withdrawal_mw'], b1['queue_withdrawal_mw'])}), requests waiting "
                         f"{b0['requests_withdrawal']:,} → {b1['requests_withdrawal']:,}. "
                         "Single publication, so unconfirmed.")
    L += [
          f"- Area relief dates: **{cs} confirmed slips**, **{cp} confirmed pull-forwards**, "
          f"{uc} unconfirmed (latest publication only), **{rv} moved-then-reverted**, **{wd} withdrawn**"
          + (f", {dr} moved and then left the map" if dr else "") + "."]
    meta = snaps[-1].get("meta", {})
    for co in cohorts:
        cc = co["counts"]
        moved = cc.get("slipped", 0) + cc.get("slipped_unconfirmed", 0)
        L.append(f"- **{co['year']} promise ledger:** of **{co['total']}** area relief dates promised for "
                 f"{co['year']} on {co['since']}, {cc.get('kept', 0)} still say {co['year']}, **{moved} have been "
                 f"pushed later** ({cc.get('slipped', 0)} confirmed), {cc.get('withdrawn', 0)} withdrawn"
                 + (f", **{cc.get('overdue', 0)} overdue**" if cc.get("overdue") else "")
                 + (f", {cc.get('retired', 0)} no longer on the map" if cc.get("retired") else "") + ".")
    L.append("")

    for co in cohorts:
        cc = co["counts"]
        labels = dict(COHORT_LABELS_EN, kept=f"still {co['year']}",
                      overdue=f"{co['year']} passed, still unresolved")
        L += [f"## The {co['year']} promise ledger", "",
              f"On **{co['since']}**, the first publication in this archive, operators promised that "
              f"congestion would be resolved in **{co['year']}** for **{co['total']} area/direction pairs**. "
              "The source map only ever shows the *current* promise; this ledger keeps the original. "
              f"When {co['year']} ends, every entry still showing {co['year']} becomes *overdue*.", "",
              "| status | count |", "|---|---:|"]
        for st in COHORT_ORDER:
            if cc.get(st):
                L.append(f"| {labels[st]} | {cc[st]} |")
        changed = [r for r in co["rows"] if r["status"] not in ("kept", "retired")]
        if changed:
            L += ["", "| area | direction | promised | now | status |", "|---|---|---:|---:|---|"]
            for r in changed:
                aid, d = r["key"]
                now = "no date" if (r["now"] or 0) >= SENTINEL_YEAR else r["now"]
                L.append(f"| {_area_label(aid, meta)} | {d} | {r['promised']} | {now} | {labels[r['status']]} |")
        L.append("")

    L += ["## Queue trend", "",
          "Regional (distribution) grids and TenneT are shown separately and never added together.", "",
          "| source publication | regional areas | regional withdrawal queue (MW) | regional requests waiting | "
          "TenneT regions | TenneT withdrawal queue (MW) | TenneT injection queue (MW) |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for r in qt:
        g, t = r["regional"], r["tennet"]
        L.append(f"| {r['ingest']} | {g['areas']} | {g['queue_withdrawal_mw']:,} | {g['requests_withdrawal']:,} | "
                 f"{t['areas']} | {t['queue_withdrawal_mw']:,} | {t['queue_injection_mw']:,} |")
    tv = [r["tennet"]["queue_withdrawal_mw"] for r in qt]
    run = 1
    while run < len(tv) - 1 and tv[-2 - run] == tv[-2]:
        run += 1
    if len(tv) >= 3 and tv[-1] != tv[-2] and run >= 3:
        L += ["", f"> **TenneT's queue figures were identical in {run} consecutive publications "
              f"({qt[-1 - run]['ingest']} – {qt[-2]['ingest']}) before changing in {qt[-1]['ingest']}.** "
              "Treat TenneT queue values as possibly stale between its own updates."]
    L += ["", "> Sums over *live* areas at each publication. Inventory reorganisations (see below) can "
          "move these numbers without any change in real demand — read a step change that coincides "
          "with an inventory change with care.", ""]

    area_moved = sum(v for k, v in c.items() if k not in ("stable", "insufficient"))
    L += ["## Relief dates — what actually moved", "",
          "A move only counts as **slippage** once it has held for two consecutive publications. "
          "This guards against corrections and one-off publication glitches; single-publication moves "
          f"are listed separately as *unconfirmed*. So far {rv} of {area_moved} area-level moves have "
          "reverted.", "",
          "### Area-level relief year (`yearSolved*`)", "",
          "#### Confirmed slips (later)", ""]
    L += _area_table([x for x in area_mv["confirmed"] if x[1]["kind"] == "slip"])
    L += ["#### Confirmed pull-forwards (earlier)", ""]
    L += _area_table([x for x in area_mv["confirmed"] if x[1]["kind"] == "pull"])
    if area_mv["unconfirmed"]:
        L += ["#### Unconfirmed — moved in the latest publication only, may still revert", "",
              "| area | direction | was | now |", "|---|---|---:|---:|"]
        for (aid, d), m in area_mv["unconfirmed"][:25]:
            L.append(f"| `{aid}` | {d} | {m['first']} | {m['last']} |")
        L.append("")
    if area_mv["withdrawn"]:
        L += ["#### Relief date withdrawn (now 'no date')", "",
              "| area | direction | last date | since |", "|---|---|---:|---|"]
        for (aid, d), m in area_mv["withdrawn"]:
            L.append(f"| `{aid}` | {d} | {m['first']} | {m['since']} |")
        L.append("")
    L += [f"#### Moved, then reverted ({len(area_mv['reverted'])})", "",
          "These looked like slips or pull-forwards in one publication and were undone in a later one.", ""]
    if area_mv["reverted"]:
        L += ["| area | direction | stays at | excursion |", "|---|---|---:|---|"]
        for (aid, d), m in area_mv["reverted"][:20]:
            L.append(f"| `{aid}` | {d} | {m['year']} | {', '.join(map(str, m['excursion']))} |")
        L.append("")

    pc = proj_mv["counts"]
    L += ["### Planned-expansion projects (published delivery window)", "",
          "Tracked on the published window (`dateString`, e.g. *Tussen 2031 en 2033*), not on the "
          "source's `year` field, which alternates between a window's start and end without the "
          "window changing. See Methodology.", "", "#### Confirmed slips", ""]
    L += _proj_table([x for x in proj_mv["confirmed"] if x[1]["kind"] == "slip"])
    L += ["#### Confirmed pull-forwards", ""]
    L += _proj_table([x for x in proj_mv["confirmed"] if x[1]["kind"] == "pull"])
    if proj_mv["withdrawn"]:
        L += ["#### Project date withdrawn", "",
              "| area | operator | project | last date | since |", "|---|---|---|---:|---|"]
        for (aid, op, name), m in proj_mv["withdrawn"]:
            L.append(f"| `{aid}` | {op} | {name[:48]} | {m.get('first_s', m['first'])} | {m['since']} |")
        L.append("")
    L += [f"Projects: {pc.get('stable', 0):,} stable · {pc.get('reverted', 0)} reverted · "
          f"{pc.get('confirmed_slip', 0)} confirmed slips · {pc.get('confirmed_pull', 0)} confirmed "
          f"pull-forwards · {pc.get('unconfirmed_slip', 0) + pc.get('unconfirmed_pull', 0)} unconfirmed · "
          f"{pc.get('withdrawn', 0)} withdrawn.", ""]

    L += [f"## This publication ({last['ingest']})", ""]
    if proj_mv["this_cycle"]:
        L += [f"{len(proj_mv['this_cycle'])} project delivery windows changed in the latest publication "
              "(unconfirmed until they hold in the next one):", "",
              "| area | operator | project | was | now |", "|---|---|---|---:|---:|"]
        for (aid, op, name), a, b in sorted(proj_mv["this_cycle"],
                                            key=lambda x: -abs(window_delta(x[1], x[2])))[:30]:
            L.append(f"| `{aid}` | {op} | {name[:48]} | {fmt_window(a)} | {fmt_window(b)} |")
        L.append("")
    else:
        L += ["No project delivery windows changed in the latest publication.", ""]

    L += ["## Reliability of published relief dates, by operator", "",
          f"How often an operator's published project delivery windows changed across the archive "
          f"(projects seen in at least {MIN_TRACK_FOR_RELIABILITY} publications).", "",
          "| operator | projects tracked | moved | moved % | of which reverted | confirmed changes |",
          "|---|---:|---:|---:|---:|---:|"]
    for r in rel:
        rp = r["reverted_pct_of_moved"] if r["reverted_pct_of_moved"] is not None else 0
        L.append(f"| {r['operator']} | {r['tracked']:,} | {r['moved']} | {r['moved_pct']}% | "
                 f"{r['reverted']} ({rp}%) | {r['confirmed']} |")
    L.append("")

    L += ["## Area inventory changes", ""]
    if inv:
        for i in inv:
            ex = ", ".join(f"`{x}`" for x in i["retired_ids"][:6]) + ("…" if i["retired"] > 6 else "")
            L.append(f"- **{i['ingest']}**: {i['added']} areas added, {i['retired']} retired"
                     + (f" (e.g. {ex})" if i["retired"] else "") + ".")
        L.append("")
    else:
        L += ["No inventory changes.", ""]

    L += ["## Methodology & caveats", "",
          "- **Source:** Netbeheer Nederland's public capaciteitskaart (`data.partnersinenergie.nl/api`), "
          "archived verbatim by gridwatch-nl on every source publication. The source states its figures "
          "are *indicative*, a snapshot, and that no rights can be derived from them; the same applies here.",
          "- **Publications, not days:** one row per distinct source re-ingest (`dataUpdate.executedOn`), "
          "so the series is irregular — the source publishes every ~1–3 weeks.",
          "- **Persistence:** a move is *confirmed* only after holding for two consecutive publications, "
          "so that corrections and one-off publication glitches are not reported as slippage.",
          "- **Project dates are the published window, not `year`:** for projects with a range "
          "(*Tussen 2031 en 2033*) the source's `year` field alternates between the start and the end "
          "year from one publication to the next while the published range stays the same. Reading "
          "`year` makes such projects look like they slip and recover constantly (an earlier version "
          "of this report did exactly that). The report therefore compares the published window itself; "
          "a shift within the same year (e.g. Q2 → Q4) counts as a move.",
          "- **Identity:** projects are matched across publications on (area, operator, name); the "
          "source's numeric ids rotate on every ingest and are never used.",
          f"- **Sentinel:** a year ≥ {SENTINEL_YEAR} means *no date*. For an area relief year it is "
          "reported as *withdrawn*; for a project it means the window has no end date "
          "(*Tussen 2030 en 2099* is shown as *2030–open*). Never treated as a multi-decade slip.",
          "- **Past-dated** years occur in the source and are excluded from slip/pull arithmetic.",
          "- **Inventory churn:** areas are periodically retired or renamed; queue totals are summed over "
          "*live* areas only. Retired areas keep their last known values in the archive but are excluded here. "
          "A renamed area can't be linked to its new id, so in the promise ledger it is reported as *no longer "
          "on the map*, never as a kept promise. Inventory changes are dated by the publication in which the "
          "archive *detected* them: the area list is refreshed from the map about monthly, so a change may "
          "have happened up to a few publications earlier.",
          f"- **Short baseline:** {len(snaps)} publications over {days} days. Operator-level reliability "
          "figures in particular are early signal, not verdict.", ""]
    return "\n".join(L)


# ----------------------------------------------------------------------------- Dutch one-pager
REPO_URL = "https://github.com/jeremy-graft/gridwatch-nl"


def _nl_int(n) -> str:
    return f"{n:,}".replace(",", ".")


def _nl_pct(x) -> str:
    return f"{x:.1f}".replace(".", ",") if x is not None else "0"


def _nl_delta(a, b) -> str:
    return f"{100 * (b - a) / a:+.1f}%".replace(".", ",") if a else "n.v.t."


def render_nl(snaps, qt, cohorts, rel, generated, lfl=None) -> str:
    """One-page Dutch summary for forwarding. Same numbers as REPORT.md and regenerated with it,
    so it can never drift from the data."""
    first, last = snaps[0], snaps[-1]
    q0, q1 = qt[0], qt[-1]
    weeks = round((datetime.fromisoformat(last["ingest"]) - datetime.fromisoformat(first["ingest"])).days / 7)
    meta = last.get("meta", {})
    dir_nl = {"afname": "afname", "invoeding": "teruglevering"}
    L = ["# Netcongestie Monitor: samenvatting", "",
         f"*Stand: publicatie van {last['ingest']} · {len(snaps)} publicaties sinds {first['ingest']} · "
         f"automatisch gegenereerd · indicatief*", "",
         "## Waarom dit bestaat", "",
         "Netbeheerders publiceren op de landelijke capaciteitskaart per gebied **in welk jaar de "
         "netcongestie naar verwachting is opgelost**. Maar de kaart toont alleen de huidige stand: "
         "verschuift een jaartal, dan verdwijnt de oude belofte. **gridwatch-nl bewaart elke publicatie "
         f"sinds {first['ingest']}**, zodat verschuivingen zichtbaar en controleerbaar worden.", ""]

    for co in cohorts:
        cc = co["counts"]
        moved = cc.get("slipped", 0) + cc.get("slipped_unconfirmed", 0)
        L += [f"## De {co['year']}-beloftes", "",
              f"Op {co['since']} beloofden netbeheerders voor **{co['total']} gebieden** (per richting) "
              f"dat de congestie in **{co['year']}** zou zijn opgelost. De stand nu:", "",
              f"- **{cc.get('kept', 0)}** zeggen nog steeds {co['year']}",
              f"- **{moved}** zijn al naar later verschoven"
              + (f", allemaal bevestigd" if moved and not cc.get("slipped_unconfirmed") else
                 f": {cc.get('slipped', 0)} bevestigd, {cc.get('slipped_unconfirmed', 0)} alleen in de "
                 "laatste publicatie (kan nog terugdraaien)" if moved else "")]
        if cc.get("withdrawn"):
            L.append(f"- **{cc['withdrawn']}** hebben geen jaartal meer (ingetrokken)")
        if cc.get("overdue"):
            L.append(f"- **{cc['overdue']}** zijn over hun beloofde jaar heen en nog niet opgelost")
        if cc.get("retired"):
            L.append(f"- **{cc['retired']}** staan niet meer op de kaart (gebied opgeheven of hernoemd); "
                     "die belofte is niet meer te controleren")
        changed = [r for r in co["rows"] if r["status"] in ("slipped", "slipped_unconfirmed", "withdrawn")]
        if changed:
            L += ["", "| gebied | richting | beloofd | nu | |", "|---|---|---:|---:|---|"]
            for r in changed:
                aid, d = r["key"]
                now = "geen jaartal" if (r["now"] or 0) >= SENTINEL_YEAR else r["now"]
                tag = {"slipped": "bevestigd", "slipped_unconfirmed": "onbevestigd",
                       "withdrawn": "ingetrokken"}[r["status"]]
                L.append(f"| {_area_label(aid, meta)} | {dir_nl.get(d, d)} | {r['promised']} | {now} | {tag} |")
        L += ["", f"**Na afloop van {co['year']} rapporteert de Monitor welke van deze gebieden nog steeds "
              "als niet opgelost op de kaart staan.**", ""]

    shown = [r for r in rel if r["tracked"] >= 10]
    if shown:
        L += ["## Hoe vaak veranderen de geplande opleverdata?", "",
              f"Aandeel uitbreidingsprojecten waarvan de gepubliceerde opleverperiode in {weeks} weken "
              "minstens een keer veranderde, per netbeheerder:", "",
              "| netbeheerder | projecten gevolgd | veranderd | waarvan later teruggedraaid |",
              "|---|---:|---:|---:|"]
        for r in shown:
            rev = f"{_nl_pct(r['reverted_pct_of_moved'])}%" if r["moved"] else "–"
            L.append(f"| {r['operator']} | {_nl_int(r['tracked'])} | {_nl_pct(r['moved_pct'])}% | {rev} |")
        L += ["", "Wij vergelijken de gepubliceerde periode zelf (bijvoorbeeld *Tussen 2031 en 2033*). Het "
              "losse jaartal in de bron wisselt bij zulke projecten tussen begin- en eindjaar zonder dat de "
              "planning verandert, en is daarom niet bruikbaar om verschuivingen te meten.", ""]

    r0, r1, t0, t1 = q0["regional"], q1["regional"], q0["tennet"], q1["tennet"]
    L += ["## De wachtrij", "",
          f"- **Regionale netten:** aanvragen in de wachtrij voor afname {_nl_int(r0['requests_withdrawal'])} → "
          f"**{_nl_int(r1['requests_withdrawal'])}** "
          f"({_nl_delta(r0['requests_withdrawal'], r1['requests_withdrawal'])}) sinds {first['ingest']}; "
          f"gevraagd vermogen {_nl_int(r1['queue_withdrawal_mw'])} MW",
          f"- **TenneT (hoogspanning):** afname-wachtrij {_nl_int(t0['queue_withdrawal_mw'])} → "
          f"**{_nl_int(t1['queue_withdrawal_mw'])} MW** ({_nl_delta(t0['queue_withdrawal_mw'], t1['queue_withdrawal_mw'])}). "
          "Apart vermeld: de TenneT-regio's overlappen met de regionale gebieden en meten een andere wachtrij.",
          f"- **{q1['areas_with_withdrawal_queue']} van de {q1['live_areas']} gebieden** hebben een wachtrij voor afname", ""]
    if lfl and lfl["tennet"]["before"] != lfl["tennet"]["after"]:
        g = lfl["tennet"]
        L += [f"**Laatste publicatie ({lfl['from']} → {lfl['to']}):** de afname-wachtrij van TenneT ging in de "
              f"{g['areas']} regio's die in beide publicaties voorkomen van {_nl_int(g['before']['queue_withdrawal_mw'])} "
              f"naar **{_nl_int(g['after']['queue_withdrawal_mw'])} MW** "
              f"({_nl_delta(g['before']['queue_withdrawal_mw'], g['after']['queue_withdrawal_mw'])}). "
              "Eén publicatie, dus nog onbevestigd. De oorzaak (aansluitingen, intrekkingen of een "
              "administratieve opschoning) blijkt niet uit de data.", ""]
    L += [
          "## Methode, kort", "",
          "- Een verschuiving telt pas als **bevestigd** als ze twee opeenvolgende publicaties standhoudt, "
          "zodat correcties en eenmalige fouten in een publicatie niet als vertraging worden gemeld.",
          "- Bron: de openbare capaciteitskaart van Netbeheer Nederland. Die cijfers zijn indicatief en er "
          "kunnen geen rechten aan worden ontleend. Dat geldt ook voor deze samenvatting.",
          "- Netbeheerders heffen gebieden soms op of geven ze een nieuwe naam. Zo'n gebied telt niet mee als "
          "'nog steeds beloofd', omdat de oude belofte niet meer te volgen is.",
          f"- Korte reeks: {len(snaps)} publicaties in {weeks} weken. Lees de cijfers als vroeg signaal, "
          "niet als oordeel.",
          f"- Volledig rapport (Engels), methode en alle ruwe data: [{REPO_URL.replace('https://', '')}]({REPO_URL})", ""]
    return "\n".join(L)


# ----------------------------------------------------------------------------- main
def _ser(mv):
    return {"counts": mv["counts"],
            "confirmed": [{"key": list(k), **m} for k, m in mv["confirmed"]],
            "unconfirmed": [{"key": list(k), **m} for k, m in mv["unconfirmed"]],
            "reverted": [{"key": list(k), **m} for k, m in mv["reverted"]],
            "withdrawn": [{"key": list(k), **m} for k, m in mv["withdrawn"]],
            "this_cycle": [{"key": list(k), "was": a, "now": b} for k, a, b in mv["this_cycle"]]}


def main() -> int:
    snaps = load_snapshots()
    if len(snaps) < 2:
        print(f"need >=2 distinct source publications in git history, have {len(snaps)}")
        return 1
    ref_year = int(snaps[-1]["ingest"][:4])
    latest = snaps[-1]["ingest"]
    qt = queue_trend(snaps)
    proj_tracks, area_tracks = track_series(snaps)
    proj_mv = summarize_moves(proj_tracks, ref_year, latest, classify=classify_window)
    area_mv = summarize_moves(area_tracks, ref_year, latest)
    rel = reliability_by_operator(proj_tracks, ref_year)
    inv = inventory_changes(snaps)
    # Stamp with the data date, not the run date, so a re-run with no new publication produces a
    # byte-identical report (no empty commits from the weekly job).
    generated = latest
    first_year = int(snaps[0]["ingest"][:4])
    cohorts = [promise_cohort(area_tracks, y, snaps[0]["ingest"], ref_year, latest)
               for y in sorted({first_year, ref_year})]

    lfl = latest_like_for_like(snaps)
    REPORT_MD.write_text(render(snaps, qt, area_mv, proj_mv, rel, inv, generated, cohorts, lfl),
                         encoding="utf-8", newline="\n")
    SUMMARY_NL.write_text(render_nl(snaps, qt, cohorts, rel, generated, lfl), encoding="utf-8", newline="\n")
    REPORT_JSON.write_text(json.dumps({
        "generated": generated,
        "publications": [{"ingest": s["ingest"], "captured": s["captured"], "sha": s["sha"],
                          "live_areas": len(s["live_ids"])} for s in snaps],
        "queue_trend": qt,
        "area_relief": _ser(area_mv),
        "project_relief": _ser(proj_mv),
        "reliability_by_operator": rel,
        "inventory_changes": inv,
        "promise_ledgers": cohorts,
        "latest_like_for_like": lfl,
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {REPORT_MD.name}, {SUMMARY_NL.name} and {REPORT_JSON.relative_to(ROOT)} "
          f"({len(snaps)} publications, latest {latest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
