# gridwatch-nl

A daily, immutable **archive of the Dutch grid congestion map** (capaciteitskaart,
published by Netbeheer Nederland / TenneT). The archive is the product; alerts, a slippage
index, and any frontend come later, once there is enough history to be worth analysing.

**Design principle: raw-first.** Fetch responses and commit them verbatim (canonicalised
JSON). Parsing and change-detection run later, over the archived files — never over live
requests. A parser bug must never be able to destroy data. Git history *is* the archive.

See **[DATA_SOURCES.md](DATA_SOURCES.md)** for the full Phase-0 discovery: verified
endpoints, the data model, the legal check, and the reasoning behind the strategy below.

## How it works

The map is a MapLibre app backed by a small Spring Boot API on Netbeheer's own domain.
There is **no bulk "all areas" endpoint** — per-area detail comes one id at a time. But the
API also exposes `GET /api/manifests`, which reports **when each operator last updated each
category of data**. Operators republish every few weeks, not daily. So the archiver is
manifest-driven:

- **Every day (~2 requests):** check `/api/status`, archive `/api/manifests`. Cheap.
- **Only when the manifest changes** (or `--full`, or the monthly backstop): sweep all
  ~301 service areas via `POST /api/serviceArea/get` and archive the raw detail per operator.

This captures every change with its official date while keeping daily load — and the risk of
the source's Cloudflare challenging the runner — near zero.

```
gridwatch-nl/
  fetch.py                     # the ONLY script that touches the network for the daily job
  tools/
    enumerate_area_ids.py      # manual/monthly: rebuild data/area_ids.json from the map tiles
  data/
    area_ids.json              # the 301 area ids + operator/province (input to fetch.py)
    manifests.json             # archived /api/manifests (per-operator update timestamps)
    serviceareas/
      liander.json             # raw serviceArea detail, keyed by id, per operator
      enexis.json
      stedin.json
      tennet.json
      other.json
    _status.json               # last run: what happened, counts, any failures
  parse/                       # Phase 2 (not built yet): loads data/ into Postgres, writes CHANGES.md
  .github/workflows/
    daily.yml                  # cron 05:00 UTC + manual; commits changes; alerts on failure
    heartbeat.yml              # Mon/Thu: alert if no snapshot in 48h (catches a silently-stopped cron)
```

## Running it

```bash
pip install -r requirements.txt

# one-time (and ~monthly) bootstrap of the area-id list from the map tiles:
python tools/enumerate_area_ids.py

# a snapshot (sweeps only if the manifest changed since last run):
python fetch.py

# force a full sweep regardless:
python fetch.py --full
```

Environment:
- `GRIDWATCH_CONTACT` — email put in the User-Agent (default `jeremy-graft@users.noreply.github.com`).
- `GRIDWATCH_DELAY` — seconds between sweep requests (default `2.0`).

## Alerting — zero-config, GitHub-native

No external alerting service. `fetch.py` exits non-zero on any hard failure (Cloudflare
block, API down, too many area errors), which **fails the job**, and GitHub emails you for
failed runs on your own repos (make sure Actions failure notifications are on in your GitHub
notification settings). `heartbeat.yml` fails the same way if no snapshot has landed in 48h,
catching a silently-stopped daily cron.

The one thing GitHub's own emails can't catch is a scheduled run that *never fires at all*
(e.g. GitHub disables schedules after ~60 days of repo inactivity). Backstop that with an
**external weekly self-check** — a scheduled routine that reads this repo's `_status.json` and
last-commit date and pings you only if it's stale or failed. (Set up separately from the repo.)

> ⚠️ Before trusting the cron: run `daily.yml` once via **workflow_dispatch** and confirm the
> sweep isn't 403/challenged from GitHub's IP ranges. If it is, move to a self-hosted runner.

## Status

- **Phase 0 — discovery & legality:** ✅ done. GO decision in [DATA_SOURCES.md](DATA_SOURCES.md).
- **Phase 1 — the archiver:** ✅ built (this repo). Needs 14 consecutive clean daily snapshots.
- **Phase 2 — parser + Postgres + CHANGES.md:** not started; build after ≥14 clean days.

## Notes

- Never edit files under `data/` by hand — `fetch.py` (and the enumerate tool) are the only
  writers. If the source changes its schema, the raw commit still lands; record a TODO rather
  than "fixing" archived data.
- This is public infrastructure data published "voor publiek inzicht." The map itself states
  its figures are indicative, a snapshot, with no rights derived — any downstream product must
  carry the same framing.
