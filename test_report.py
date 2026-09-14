#!/usr/bin/env python3
"""
Tests for parse/report.py — the persistence-aware analysis layer. Pure logic, no git, no network.

The persistence classification is the product's core claim ("only confirmed moves are
slippage"), so it is pinned exhaustively here, along with every data-quality rule from
DATA_SOURCES.md §5.8 that would otherwise silently produce wrong numbers.
"""
from __future__ import annotations

import pytest

from parse import report as R

REF = 2026  # reference year for sentinel / past-dated classification


# ---------------------------------------------------------------- parsers (§5.8 string quirks)
@pytest.mark.parametrize("s,exp", [
    ("9.2 MW", 9.2), ("68 MW", 68.0), ("0 MW", 0.0), ("-", None), (None, None), ("", None),
    ("  12.4 MW ", 12.4), ("abc", None),
])
def test_parse_mw(s, exp):
    assert R.parse_mw(s) == exp


@pytest.mark.parametrize("s,exp", [("23", 23), ("-", None), (None, None), ("0", 0), ("1,5", 1)])
def test_parse_count(s, exp):
    assert R.parse_count(s) == exp


@pytest.mark.parametrize("y,exp", [("2029", 2029), (2029, 2029), ("-", None), (None, None),
                                   ("2029 - Q4", 2029), ("", None)])
def test_parse_year(y, exp):
    assert R.parse_year(y) == exp


def test_sentinel_and_past_classification():
    assert R.classify_year(2099, REF) == "withdrawn"
    assert R.classify_year(2090, REF) == "withdrawn"
    assert R.classify_year(2089, REF) == "ok"
    assert R.classify_year(2020, REF) == "past"
    assert R.classify_year(2026, REF) == "ok"
    assert R.classify_year(None, REF) == "none"


def test_project_key_strips_whitespace_and_never_uses_id():
    """Ids carry stray whitespace ('Groningen Oost ') and the numeric id rotates every ingest."""
    a = R.project_key("Groningen Oost ", {"id": 1, "name": "X ", "gridOperator": "TenneT"})
    b = R.project_key("Groningen Oost", {"id": 999, "name": "X", "gridOperator": "TenneT"})
    assert a == b


# ---------------------------------------------------------------- persistence classification
def _seq(*ys):
    return [(f"2026-0{i+1}-01", y) for i, y in enumerate(ys)]


def test_stable():
    assert R.classify_move(_seq(2029, 2029, 2029), REF)["status"] == "stable"


def test_single_observation_is_insufficient():
    assert R.classify_move(_seq(2029), REF)["status"] == "insufficient"


def test_move_then_revert_is_not_slippage():
    """Moerdijk 2032->2028->2032: the core false-alarm case."""
    c = R.classify_move(_seq(2032, 2028, 2032), REF)
    assert c["status"] == "reverted"
    assert c["year"] == 2032 and c["excursion"] == [2028]


def test_unconfirmed_slip_is_only_seen_once():
    c = R.classify_move(_seq(2026, 2029), REF)
    assert c["status"] == "persisted" and c["kind"] == "slip"
    assert c["confirmed"] is False, "a move seen in one publication must NOT be called confirmed"


def test_confirmed_slip_requires_two_consecutive_holds():
    """Oldenzaal 2026->2029->2029."""
    c = R.classify_move(_seq(2026, 2029, 2029), REF)
    assert c["status"] == "persisted" and c["kind"] == "slip" and c["confirmed"] is True
    assert c["delta"] == 3 and c["changed_at"] == "2026-02-01"


def test_confirmed_pull_forward():
    c = R.classify_move(_seq(2030, 2026, 2026), REF)
    assert c["kind"] == "pull" and c["confirmed"] and c["delta"] == -4


def test_flapping_ends_where_it_started_is_reverted_not_confirmed():
    """Buggenum 2033->2026->2033: two moves, net zero. Must be 'reverted', never a slip."""
    c = R.classify_move(_seq(2033, 2026, 2033), REF)
    assert c["status"] == "reverted"


def test_withdrawn_is_its_own_outcome_not_a_69_year_slip():
    c = R.classify_move(_seq(2030, 2099), REF)
    assert c["status"] == "withdrawn"
    assert "delta" not in c, "a sentinel must never enter slip arithmetic"
    assert c["first"] == 2030 and c["since"] == "2026-02-01"


def test_past_dated_is_flagged():
    c = R.classify_move(_seq(2018, 2028, 2028), REF)
    assert c["status"] == "persisted" and c["past_dated"] is True


def test_none_values_are_skipped_not_counted_as_moves():
    c = R.classify_move([("a", 2029), ("b", None), ("c", 2029)], REF)
    assert c["status"] == "stable"


# ---------------------------------------------------------------- summarize_moves
def test_summarize_separates_confirmed_unconfirmed_reverted_withdrawn_and_this_cycle():
    tracks = {
        ("A", "x"): _seq(2026, 2029, 2029),   # confirmed slip
        ("B", "x"): _seq(2030, 2030, 2028),   # unconfirmed pull (moved in latest)
        ("C", "x"): _seq(2032, 2028, 2032),   # reverted
        ("D", "x"): _seq(2030, 2030, 2099),   # withdrawn (moved in latest)
        ("E", "x"): _seq(2031, 2031, 2031),   # stable
        ("F", "x"): _seq(2018, 2028, 2028),   # persisted but past-dated -> excluded from lists
    }
    latest = "2026-03-01"
    s = R.summarize_moves(tracks, REF, latest)
    assert s["counts"] == {"confirmed_slip": 2, "unconfirmed_pull": 1, "reverted": 1,
                           "withdrawn": 1, "stable": 1}
    assert [k for k, _ in s["confirmed"]] == [("A", "x")], "past-dated F must not be listed"
    assert [k for k, _ in s["unconfirmed"]] == [("B", "x")]
    assert [k for k, _ in s["reverted"]] == [("C", "x")]
    assert [k for k, _ in s["withdrawn"]] == [("D", "x")]
    # this_cycle = moves whose latest observation is in the latest ingest
    tc = {k: (a, b) for k, a, b in s["this_cycle"]}
    assert ("A", "x") not in tc, "A's move happened a cycle ago and has held"
    assert tc[("D", "x")] == (2030, 2099)


# ---------------------------------------------------------------- reliability by operator
def test_reliability_by_operator_scores_moved_and_reverted():
    tracks = {
        ("a1", "Stedin", "p1"): _seq(2030, 2032, 2030),  # moved, reverted
        ("a2", "Stedin", "p2"): _seq(2030, 2032, 2032),  # moved, confirmed
        ("a3", "Stedin", "p3"): _seq(2030, 2030, 2030),  # stable
        ("b1", "Liander", "q"): _seq(2029, 2029, 2029),  # stable
        ("c1", "Enexis", "r"): _seq(2029, 2031),         # only 2 obs -> not scored
        ("d1", "Enexis", "s"): _seq(2030, 2099, 2099),   # sentinel-only moves -> not scored as a move
    }
    rows = {r["operator"]: r for r in R.reliability_by_operator(tracks, REF)}
    st = rows["Stedin"]
    assert (st["tracked"], st["moved"], st["reverted"], st["confirmed"]) == (3, 2, 1, 1)
    assert st["moved_pct"] == 66.7 and st["reverted_pct_of_moved"] == 50.0
    assert rows["Liander"]["moved"] == 0 and rows["Liander"]["moved_pct"] == 0.0
    assert "Enexis" not in rows or rows["Enexis"]["tracked"] == 0 or rows["Enexis"]["moved"] == 0


def test_reliability_sorted_most_volatile_first():
    tracks = {
        ("a", "Calm", "p"): _seq(1, 1, 1) and _seq(2030, 2030, 2030),
        ("b", "Wild", "p"): _seq(2030, 2031, 2031),
    }
    rows = R.reliability_by_operator(tracks, REF)
    assert rows[0]["operator"] == "Wild"


# ---------------------------------------------------------------- queue trend & inventory
def _snap(ingest, areas, live=None):
    return {"ingest": ingest, "captured": ingest, "sha": "abc",
            "areas": areas, "live_ids": set(live if live is not None else areas)}


def test_queue_trend_sums_live_areas_only_and_parses_strings():
    areas = {
        "A": {"queueWithdrawal": "10 MW", "queueInjection": "-", "uniqueRequestsWithdrawal": "3",
              "uniqueRequestsInjection": "-"},
        "B": {"queueWithdrawal": "2.5 MW", "queueInjection": "1 MW", "uniqueRequestsWithdrawal": "1",
              "uniqueRequestsInjection": "2"},
        "RETIRED": {"queueWithdrawal": "999 MW", "uniqueRequestsWithdrawal": "999"},
    }
    r = R.queue_trend([_snap("2026-09-07", areas, live={"A", "B"})])[0]
    assert r["live_areas"] == 2
    assert r["queue_withdrawal_mw"] == 12 and r["queue_injection_mw"] == 1
    assert r["requests_withdrawal"] == 4 and r["requests_injection"] == 2
    assert r["areas_with_withdrawal_queue"] == 2


def test_inventory_changes_detects_added_and_retired():
    s1 = _snap("2026-08-10", {"A": {}, "B": {}})
    s2 = _snap("2026-08-17", {"A": {}, "C": {}})
    inv = R.inventory_changes([s1, s2])
    assert inv == [{"ingest": "2026-08-17", "added": 1, "retired": 1,
                    "added_ids": ["C"], "retired_ids": ["B"]}]


def test_track_series_excludes_retired_areas_and_keys_by_stable_identity():
    areas = {"A": {"projects": [{"id": 1, "name": "P", "gridOperator": "Op", "year": "2029"}],
                   "yearSolvedWithdrawal": "2029", "yearSolvedInjection": "-"},
             "GONE": {"projects": [{"id": 2, "name": "Q", "gridOperator": "Op", "year": "2030"}]}}
    proj, area = R.track_series([_snap("2026-09-07", areas, live={"A"})])
    assert list(proj) == [("A", "Op", "P")]
    assert proj[("A", "Op", "P")] == [("2026-09-07", 2029)]
    assert area[("A", "afname")] == [("2026-09-07", 2029)]
    assert area[("A", "invoeding")] == [("2026-09-07", None)]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
