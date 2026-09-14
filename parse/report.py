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
  * Relief-date moves are classified by PERSISTENCE, because ~40% of observed moves revert:
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
    {ingest, captured, sha, areas: {id: serviceArea}, live_ids: set}"""
    out, seen = [], set()
    for line in _git("log", "--reverse", "--format=%H %cI", "--", "data/manifests.json").splitlines():
        if not line.strip():
            continue
        sha, captured = line.split()
        m = _show(sha, "data/manifests.json")
        if not m.strip():
            continue
        ingest = (json.loads(m).get("dataUpdate") or {}).get("executedOn", "")[:10]
        if not ingest or ingest in seen:
            continue
        seen.add(ingest)
        areas = {}
        for b in BUCKETS:
            t = _show(sha, f"data/serviceareas/{b}.json")
            if t.strip():
                areas.update(json.loads(t))
        ids_txt = _show(sha, "data/area_ids.json")
        live = {a["id"].strip() for a in json.loads(ids_txt)["areas"]} if ids_txt.strip() else set(areas)
        if areas:
            out.append({"ingest": ingest, "captured": captured[:10], "sha": sha[:7],
                        "areas": areas, "live_ids": live})
    return out


# ----------------------------------------------------------------------------- analysis
def queue_trend(snaps: list[dict]) -> list[dict]:
    rows = []
    for s in snaps:
        live = [sa for aid, sa in s["areas"].items() if aid.strip() in s["live_ids"]]
        rows.append({
            "ingest": s["ingest"],
            "live_areas": len(live),
            "queue_withdrawal_mw": round(sum(parse_mw(a.get("queueWithdrawal")) or 0 for a in live)),
            "queue_injection_mw": round(sum(parse_mw(a.get("queueInjection")) or 0 for a in live)),
            "requests_withdrawal": sum(parse_count(a.get("uniqueRequestsWithdrawal")) or 0 for a in live),
            "requests_injection": sum(parse_count(a.get("uniqueRequestsInjection")) or 0 for a in live),
            "areas_with_withdrawal_queue": sum(1 for a in live if (parse_mw(a.get("queueWithdrawal")) or 0) > 0),
        })
    return rows


def track_series(snaps: list[dict]):
    """Return (project_tracks, area_tracks).
    project_tracks: key -> [(ingest, year)]   for projects[].year
    area_tracks:    (area, direction) -> [(ingest, year)]  for yearSolvedWithdrawal/Injection"""
    proj, area = defaultdict(list), defaultdict(list)
    for s in snaps:
        for aid, sa in s["areas"].items():
            if aid.strip() not in s["live_ids"]:
                continue
            for p in (sa.get("projects") or []):
                proj[project_key(aid, p)].append((s["ingest"], parse_year(p.get("year"))))
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


def summarize_moves(tracks: dict, ref_year: int, latest_ingest: str) -> dict:
    counts = Counter()
    confirmed, unconfirmed, reverted, withdrawn = [], [], [], []
    for key, seq in tracks.items():
        c = classify_move(seq, ref_year)
        if c["status"] == "persisted":
            label = ("confirmed_" if c["confirmed"] else "unconfirmed_") + c["kind"]
        else:
            label = c["status"]
        counts[label] += 1
        if c["status"] == "persisted" and not c.get("past_dated"):
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


def reliability_by_operator(proj_tracks: dict, ref_year: int) -> list[dict]:
    stat = defaultdict(lambda: {"tracked": 0, "moved": 0, "reverted": 0, "confirmed": 0})
    for (aid, op, name), seq in proj_tracks.items():
        vals = [y for _, y in seq if y is not None and classify_year(y, ref_year) == "ok"]
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
        out.append(f"| `{aid}` | {op} | {name[:48]} | {m['first']} | {m['last']} | {m['delta']:+d}y |")
    return out + [""]


def render(snaps, qt, area_mv, proj_mv, rel, inv, generated) -> str:
    first, last = snaps[0], snaps[-1]
    q0, q1 = qt[0], qt[-1]
    days = (datetime.fromisoformat(last["ingest"]) - datetime.fromisoformat(first["ingest"])).days
    L = []
    L += ["# Netcongestie Monitor", "",
          f"*Auto-generated {generated} from the [gridwatch-nl](https://github.com/jeremy-graft/gridwatch-nl) "
          f"archive. Covers **{len(snaps)} source publications** from **{first['ingest']}** to "
          f"**{last['ingest']}** ({q1['live_areas']} live areas). Indicative only — see Methodology.*", ""]

    c = area_mv["counts"]
    cs, cp = c.get("confirmed_slip", 0), c.get("confirmed_pull", 0)
    rv, wd = c.get("reverted", 0), c.get("withdrawn", 0)
    uc = c.get("unconfirmed_slip", 0) + c.get("unconfirmed_pull", 0)
    L += ["## Headline", "",
          f"- **Companies waiting for withdrawal capacity: {q0['requests_withdrawal']:,} → "
          f"{q1['requests_withdrawal']:,} ({_pct(q0['requests_withdrawal'], q1['requests_withdrawal'])})** "
          f"since {first['ingest']}.",
          f"- Withdrawal queue: {q0['queue_withdrawal_mw']:,} → {q1['queue_withdrawal_mw']:,} MW "
          f"({_pct(q0['queue_withdrawal_mw'], q1['queue_withdrawal_mw'])}); injection queue: "
          f"{q0['queue_injection_mw']:,} → {q1['queue_injection_mw']:,} MW "
          f"({_pct(q0['queue_injection_mw'], q1['queue_injection_mw'])}).",
          f"- **{q1['areas_with_withdrawal_queue']} of {q1['live_areas']} areas** currently have a withdrawal queue.",
          f"- Area relief dates: **{cs} confirmed slips**, **{cp} confirmed pull-forwards**, "
          f"{uc} unconfirmed (latest publication only), **{rv} moved-then-reverted**, **{wd} withdrawn**.", ""]

    L += ["## National queue trend", "",
          "| source publication | live areas | withdrawal queue (MW) | injection queue (MW) | "
          "waiting (withdrawal) | waiting (injection) |",
          "|---|---:|---:|---:|---:|---:|"]
    for r in qt:
        L.append(f"| {r['ingest']} | {r['live_areas']} | {r['queue_withdrawal_mw']:,} | "
                 f"{r['queue_injection_mw']:,} | {r['requests_withdrawal']:,} | {r['requests_injection']:,} |")
    L += ["", "> Sums over *live* areas at each publication. Inventory reorganisations (see below) can "
          "move these numbers without any change in real demand — read a step change that coincides "
          "with an inventory change with care.", ""]

    L += ["## Relief dates — what actually moved", "",
          "A move only counts as **slippage** once it has held for two consecutive publications. "
          "Roughly 40% of observed moves revert, so single-publication moves are listed separately as "
          "*unconfirmed*.", "",
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
    L += ["### Planned-expansion projects (`projects[].year`)", "", "#### Confirmed slips", ""]
    L += _proj_table([x for x in proj_mv["confirmed"] if x[1]["kind"] == "slip"])
    L += ["#### Confirmed pull-forwards", ""]
    L += _proj_table([x for x in proj_mv["confirmed"] if x[1]["kind"] == "pull"])
    if proj_mv["withdrawn"]:
        L += ["#### Project date withdrawn", "",
              "| area | operator | project | last date | since |", "|---|---|---|---:|---|"]
        for (aid, op, name), m in proj_mv["withdrawn"]:
            L.append(f"| `{aid}` | {op} | {name[:48]} | {m['first']} | {m['since']} |")
        L.append("")
    L += [f"Projects: {pc.get('stable', 0):,} stable · {pc.get('reverted', 0)} reverted · "
          f"{pc.get('confirmed_slip', 0)} confirmed slips · {pc.get('confirmed_pull', 0)} confirmed "
          f"pull-forwards · {pc.get('unconfirmed_slip', 0) + pc.get('unconfirmed_pull', 0)} unconfirmed · "
          f"{pc.get('withdrawn', 0)} withdrawn.", ""]

    L += [f"## This publication ({last['ingest']})", ""]
    if proj_mv["this_cycle"]:
        L += [f"{len(proj_mv['this_cycle'])} project dates moved in the latest publication "
              "(unconfirmed until they hold in the next one):", "",
              "| area | operator | project | was | now |", "|---|---|---|---:|---:|"]
        for (aid, op, name), a, b in sorted(proj_mv["this_cycle"], key=lambda x: -abs(x[2] - x[1]))[:30]:
            L.append(f"| `{aid}` | {op} | {name[:48]} | {a} | {b} |")
        L.append("")
    else:
        L += ["No project dates moved in the latest publication.", ""]

    L += ["## Reliability of published relief dates, by operator", "",
          f"How often an operator's published project dates changed across the archive (projects seen "
          f"in at least {MIN_TRACK_FOR_RELIABILITY} publications). A high *moved* share together with a "
          "high *reverted* share means the dates are noisy rather than genuinely slipping.", "",
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
          "- **Persistence:** a move is *confirmed* only after holding for two consecutive publications. "
          "This is deliberate: a large share of moves revert, and calling a single-publication move "
          "'slippage' would be wrong roughly 40% of the time.",
          "- **Identity:** projects are matched across publications on (area, operator, name); the "
          "source's numeric ids rotate on every ingest and are never used.",
          f"- **Sentinel:** a year ≥ {SENTINEL_YEAR} means the source withdrew the date. It is reported "
          "as *withdrawn*, never as a multi-decade slip.",
          "- **Past-dated** years occur in the source and are excluded from slip/pull arithmetic.",
          "- **Inventory churn:** areas are periodically retired or renamed; queue totals are summed over "
          "*live* areas only. Retired areas keep their last known values in the archive but are excluded here.",
          f"- **Short baseline:** {len(snaps)} publications over {days} days. Operator-level reliability "
          "figures in particular are early signal, not verdict.", ""]
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
    proj_mv = summarize_moves(proj_tracks, ref_year, latest)
    area_mv = summarize_moves(area_tracks, ref_year, latest)
    rel = reliability_by_operator(proj_tracks, ref_year)
    inv = inventory_changes(snaps)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    REPORT_MD.write_text(render(snaps, qt, area_mv, proj_mv, rel, inv, generated),
                         encoding="utf-8", newline="\n")
    REPORT_JSON.write_text(json.dumps({
        "generated": generated,
        "publications": [{"ingest": s["ingest"], "captured": s["captured"], "sha": s["sha"],
                          "live_areas": len(s["live_ids"])} for s in snaps],
        "queue_trend": qt,
        "area_relief": _ser(area_mv),
        "project_relief": _ser(proj_mv),
        "reliability_by_operator": rel,
        "inventory_changes": inv,
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {REPORT_MD.name} and {REPORT_JSON.relative_to(ROOT)} "
          f"({len(snaps)} publications, latest {latest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
