#!/usr/bin/env python3
"""
fetch.py — the ONLY script that touches the network for the daily archive.

Manifest-driven, event-based archiver for the Dutch grid congestion map
(capaciteitskaart). Design rationale in DATA_SOURCES.md §5.

Every run (cheap, ~2 requests):
  1. GET /api/status      — liveness pre-flight; abort loud if the API is down/blocked.
  2. GET /api/manifests   — archived verbatim to data/manifests.json. Its own history is a
     useful time-series (when each operator republished each category).

Full per-area sweep (~301 requests) runs ONLY when it's actually needed:
  - the manifest fingerprint changed since the last run, OR
  - --full was passed, OR
  - it's the monthly backstop (day-of-month == 1), OR
  - the per-operator output files don't exist yet (first run).

Operators update every few weeks, not daily, so most days do nothing expensive. This keeps
load — and the risk of the source's Cloudflare challenging our runner IP — minimal, which is
the real uptime threat (DATA_SOURCES.md §5.5).

RAW-FIRST: responses are archived verbatim (canonicalised JSON, sorted keys). Parsing is a
separate Phase-2 concern that reads data/ only. A parser bug must never cause data loss.

Exit codes: 0 = ok (with or without a sweep). Non-zero = hard failure (API down, blocked,
or a sweep that lost too many areas) — the workflow turns this into an alert.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

BASE = "https://data.partnersinenergie.nl/api"
# Placeholder contact: a GitHub noreply address isn't actually reachable, so the repo URL below
# carries the "be identifiable and contactable" duty (issues are open). Set GRIDWATCH_CONTACT
# (env var / Actions secret) to a real monitored address when there is one.
CONTACT = os.environ.get("GRIDWATCH_CONTACT", "jeremy-graft@users.noreply.github.com")
USER_AGENT = (
    f"gridwatch-nl archiver (contact: {CONTACT}; "
    "+https://github.com/jeremy-graft/gridwatch-nl)"
)
DELAY = float(os.environ.get("GRIDWATCH_DELAY", "2.0"))  # seconds between sweep requests
TIMEOUT = 30.0

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SA_DIR = DATA / "serviceareas"
AREA_IDS = DATA / "area_ids.json"
MANIFESTS = DATA / "manifests.json"
STATUS_OUT = DATA / "_status.json"

# Fraction of areas allowed to fail before the whole sweep is considered a hard failure.
MAX_SWEEP_FAILURE_RATE = 0.05
# Areas answering 200+empty are normally a handful of retired stations. A large jump means
# something systemic (source outage / id list badly stale) — refuse the sweep in that case.
MAX_MISSING_RATE = 0.15


class BlockedError(RuntimeError):
    """The source returned a bot-challenge / non-JSON where JSON was expected."""


class TransientError(RuntimeError):
    """A retryable network/5xx error."""


class EmptyAreaError(RuntimeError):
    """The source returned 200 with an empty body for one area.

    Observed 2026-08-20: four Liander areas (retired/renamed in the source's 2026-08-17
    republish) began answering 200 + zero-length body. This is the source saying "no such
    area", NOT a bot challenge — so it must be a per-area soft failure, never a systemic
    abort. Conflating the two took the archiver down for three days.
    """


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


# --- Volatile-field stripping (DATA_SOURCES.md §5.6) -------------------------------------
# The backend regenerates its database row ids on every ingest run. On 2026-07-30 this made
# all 5101 `projects[].id` values shift by +591, producing a ~5100-line diff that contained
# only 62 real changes. Array order is also non-deterministic. Both are stripped/sorted before
# commit so git diffs show real data changes only — as the brief requires. Nothing with
# information content is removed.
#
# Consequence for Phase 2: a project's identity across snapshots is (gridOperator, name),
# NOT `id` — the id is not stable and must never be used as a join key.

def normalize_area(sa: dict) -> dict:
    """Drop rotating project row ids and impose a deterministic project order."""
    sa = dict(sa)
    projects = sa.get("projects")
    if isinstance(projects, list):
        cleaned = [{k: v for k, v in p.items() if k != "id"} for p in projects]
        cleaned.sort(key=lambda p: (str(p.get("gridOperator") or ""),
                                    str(p.get("name") or ""),
                                    str(p.get("dateString") or "")))
        sa["projects"] = cleaned
    return sa


def normalize_manifest(m: dict) -> dict:
    """Drop rotating row ids and impose a deterministic order on the update rows.

    `dataUpdate` (executedOn + id) is deliberately KEPT: it is the only reliable
    change signal (see manifest_fingerprint) and is just two lines.
    """
    m = dict(m)
    ups = m.get("gridOperatorUpdates")
    if isinstance(ups, list):
        cleaned = [{k: v for k, v in u.items() if k != "id"} for u in ups]
        cleaned.sort(key=lambda u: (str(u.get("gridOperator") or ""),
                                    str(u.get("categoryShort") or "")))
        m["gridOperatorUpdates"] = cleaned
    return m


def operator_bucket(op: str | None) -> str:
    o = (op or "").lower()
    if "liander" in o:
        return "liander"
    if "stedin" in o:
        return "stedin"
    if "tennet" in o:
        return "tennet"
    if "enexis" in o or "coteq" in o or "rendo" in o:
        return "enexis"
    return "other"


def _guard_json(resp: httpx.Response) -> object:
    """Turn a response into JSON, treating blocks/HTML/empties as loud, specific errors."""
    if resp.status_code == 403:
        raise BlockedError(f"HTTP 403 (likely Cloudflare block) for {resp.request.url}")
    ctype = resp.headers.get("content-type", "") or ""
    body = resp.text
    # 200 + empty body = "this area no longer exists". Distinct from a block, which arrives
    # as 403 or an HTML challenge page with a non-empty body.
    if resp.status_code == 200 and not body.strip():
        raise EmptyAreaError(f"empty 200 body for {resp.request.url}")
    if "application/json" not in ctype:
        head = body[:80].replace("\n", " ")
        raise BlockedError(
            f"non-JSON response ({resp.status_code}, {ctype!r}) for {resp.request.url}: {head!r}"
        )
    if resp.status_code >= 500:
        raise TransientError(f"HTTP {resp.status_code} for {resp.request.url}")
    return resp.json()


@retry(
    retry=retry_if_exception_type((TransientError, httpx.TransportError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    reraise=True,
)
def _get_json(client: httpx.Client, path: str) -> object:
    return _guard_json(client.get(f"{BASE}{path}"))


@retry(
    retry=retry_if_exception_type((TransientError, httpx.TransportError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    reraise=True,
)
def _post_area(client: httpx.Client, area_id: str) -> object:
    resp = client.post(f"{BASE}/serviceArea/get", json={"id": area_id})
    # A 400 here means a bad id (client error) — do not retry, surface it.
    if resp.status_code == 400:
        raise ValueError(f"400 Bad Request for id {area_id!r}")
    return _guard_json(resp)


def manifest_fingerprint(manifest: dict) -> dict:
    """Signal for 'might the underlying data have changed' — decides whether to sweep.

    IMPORTANT (measured 2026-07-30, do not "simplify" this):
    `dataUpdate` is the RELIABLE trigger; the per-operator `updatedAt` values are NOT.
    On 2026-07-30 the ingest pipeline re-ran (executedOn 07-17 -> 07-29) and 62 real changes
    landed — including relief years moving (Oldenzaal 2026->2029) — while Enexis's and
    Liander's `updatedAt` stayed frozen at 07-15 / 05-29. Only Stedin/KI moved. Triggering on
    `updatedAt` alone would have missed all of it.

    So: include the pipeline version id (catches everything, at the cost of an occasional
    no-op sweep) AND the updatedAt set (belt and braces). Observed pipeline cadence is roughly
    every 12 days, so this still means ~2-3 sweeps a month, not daily.
    """
    du = manifest.get("dataUpdate") or {}
    updates = sorted(
        (u.get("gridOperator"), u.get("categoryShort"), u.get("updatedAt"))
        for u in (manifest.get("gridOperatorUpdates") or [])
    )
    return {"dataUpdateId": du.get("id"), "updates": updates}


def load_prev_fingerprint() -> dict | None:
    if not MANIFESTS.exists():
        return None
    try:
        return manifest_fingerprint(json.loads(MANIFESTS.read_text(encoding="utf-8")))
    except Exception:
        return None


def run(full: bool) -> int:
    if not AREA_IDS.exists():
        print(
            f"ERROR: {AREA_IDS} missing. Bootstrap it first:\n"
            "  python tools/enumerate_area_ids.py",
            file=sys.stderr,
        )
        return 2

    areas = json.loads(AREA_IDS.read_text(encoding="utf-8"))["areas"]
    status: dict = {
        "run_at": now_utc(),
        "api_up": False,
        "manifest_changed": None,
        "swept": False,
        "sweep_reason": None,
        "areas_expected": len(areas),
        "areas_ok": 0,
        "areas_failed": 0,
        "areas_missing": 0,
        "missing": [],
        "failures": [],
        "per_bucket": {},
        "ok": False,
    }

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    with httpx.Client(timeout=TIMEOUT, headers=headers, follow_redirects=True) as client:
        # 1. liveness
        try:
            st = _get_json(client, "/status")
        except Exception as e:
            _write_status(status, hard_error=f"status check failed: {e}")
            print(f"HARD FAIL: {e}", file=sys.stderr)
            return 1
        status["api_up"] = isinstance(st, dict) and st.get("status") == "OK"
        if not status["api_up"]:
            _write_status(status, hard_error=f"unexpected /status body: {st!r}")
            print(f"HARD FAIL: unexpected /status body: {st!r}", file=sys.stderr)
            return 1

        # 2. manifests — always archived
        try:
            manifest = _get_json(client, "/manifests")
        except Exception as e:
            _write_status(status, hard_error=f"manifests fetch failed: {e}")
            print(f"HARD FAIL: {e}", file=sys.stderr)
            return 1

        prev_fp = load_prev_fingerprint()
        new_fp = manifest_fingerprint(manifest)
        changed = prev_fp is None or prev_fp != new_fp
        status["manifest_changed"] = changed
        MANIFESTS.write_text(canonical(normalize_manifest(manifest)), encoding="utf-8")

        # 3. decide whether to sweep
        first_run = not any(
            (SA_DIR / f"{b}.json").exists()
            for b in ("liander", "enexis", "stedin", "tennet", "other")
        )
        monthly_backstop = datetime.now(timezone.utc).day == 1
        reason = None
        if full:
            reason = "manual --full"
        elif first_run:
            reason = "first run (no output files yet)"
        elif changed:
            reason = "manifest changed"
        elif monthly_backstop:
            reason = "monthly backstop"
        status["sweep_reason"] = reason

        if reason is None:
            print("No change since last run; skipped per-area sweep.")
            status["ok"] = True
            _write_status(status)
            return 0

        # 4. sweep
        print(f"Sweeping {len(areas)} areas (reason: {reason}) at {DELAY}s spacing…")
        status["swept"] = True
        # Pre-load existing per-operator files and merge fresh results over them, so a
        # transient failure on a few areas keeps their prior value instead of dropping them
        # from the archive. (A systemic failure is caught by the failure-rate gate below.)
        buckets: dict[str, dict] = {}
        for b in ("liander", "enexis", "stedin", "tennet", "other"):
            fp = SA_DIR / f"{b}.json"
            if fp.exists():
                try:
                    buckets[b] = json.loads(fp.read_text(encoding="utf-8"))
                except Exception:
                    buckets[b] = {}
        for i, area in enumerate(areas, 1):
            aid = area["id"]
            bucket = operator_bucket(area.get("operator"))
            try:
                data = _post_area(client, aid)
                sa = data.get("serviceArea") if isinstance(data, dict) else None
                if not sa:
                    raise ValueError("empty serviceArea in response")
                buckets.setdefault(bucket, {})[aid] = normalize_area(sa)
                status["areas_ok"] += 1
            except EmptyAreaError:
                # The source no longer serves this id (retired/renamed area). Soft, per-area:
                # keep whatever we last archived for it and carry on. NOT a systemic block.
                status["areas_missing"] += 1
                status["missing"].append(aid)
                print(f"  - {aid}: empty response (area retired?); keeping last known value")
            except BlockedError as e:
                # A block is systemic — stop immediately and fail loud rather than
                # committing a half-empty sweep over good data.
                _write_status(status, hard_error=f"blocked mid-sweep: {e}")
                print(f"HARD FAIL (blocked): {e}", file=sys.stderr)
                return 1
            except Exception as e:
                status["areas_failed"] += 1
                status["failures"].append({"id": aid, "error": str(e)})
                print(f"  ! {aid}: {e}", file=sys.stderr)
            if i < len(areas):
                time.sleep(DELAY)

        # 5. gate on health BEFORE writing — never commit a suspicious partial sweep.
        missing_rate = status["areas_missing"] / max(1, status["areas_expected"])
        if missing_rate > MAX_MISSING_RATE:
            _write_status(
                status,
                hard_error=f"{status['areas_missing']}/{status['areas_expected']} areas returned "
                f"empty — too many to be routine retirements; refusing to trust this sweep",
            )
            print("HARD FAIL: too many empty areas", file=sys.stderr)
            return 1

        failure_rate = status["areas_failed"] / max(1, status["areas_expected"])
        if status["areas_ok"] == 0 or failure_rate > MAX_SWEEP_FAILURE_RATE:
            _write_status(
                status,
                hard_error=f"sweep lost too many areas "
                f"({status['areas_failed']}/{status['areas_expected']}) — not writing",
            )
            print("HARD FAIL: sweep failure rate too high", file=sys.stderr)
            return 1

        # 6. write per-operator files (merged: fresh over prior)
        for bucket, obj in buckets.items():
            if obj:
                (SA_DIR / f"{bucket}.json").write_text(canonical(obj), encoding="utf-8")
            status["per_bucket"][bucket] = len(obj)

        status["ok"] = True
        _write_status(status)
        print(
            f"Done. {status['areas_ok']} ok, {status['areas_failed']} failed. "
            f"Buckets: {status['per_bucket']}"
        )
        return 0


def _write_status(status: dict, hard_error: str | None = None) -> None:
    if hard_error:
        status["hard_error"] = hard_error
        status["ok"] = False
    DATA.mkdir(exist_ok=True)
    STATUS_OUT.write_text(canonical(status), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="gridwatch-nl daily archiver")
    ap.add_argument(
        "--full",
        action="store_true",
        help="force a full per-area sweep regardless of manifest change",
    )
    args = ap.parse_args()
    SA_DIR.mkdir(parents=True, exist_ok=True)
    return run(full=args.full)


if __name__ == "__main__":
    raise SystemExit(main())
