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


class BlockedError(RuntimeError):
    """The source returned a bot-challenge / non-JSON where JSON was expected."""


class TransientError(RuntimeError):
    """A retryable network/5xx error."""


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


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
    ctype = resp.headers.get("content-type", "")
    body = resp.text
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
    """Stable signal for 'did the underlying data change'. Uses the pipeline version id and
    the authoritative per-operator/category updatedAt set (DATA_SOURCES.md §5.6)."""
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
        MANIFESTS.write_text(canonical(manifest), encoding="utf-8")

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
                buckets.setdefault(bucket, {})[aid] = sa
                status["areas_ok"] += 1
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
