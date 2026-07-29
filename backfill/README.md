# backfill/ — historical data (external, one-off)

This folder is **not** part of the daily archiver and is **not** written by `fetch.py`. It's a
one-time reconstruction of *pre-archive* history from the **Internet Archive**, kept separate
because it comes from a different source, a different (older) schema, and is partial.

## What's here

- `raw/capaciteitskaart_YYYY-MM-DD.csv` — the old map's `/dashboard/download` CSV export
  (`postcode,invoeding,afname[,congestiemanagement invoeding,congestiemanagement afname]`),
  as captured by the Wayback Machine. Postcode-level congestion **colour** (0=white/available,
  1=yellow/limited, 2=orange/investigation+queue, 3=red/shortage), both directions, plus (from
  2023-09) whether congestion management is active.
- `build_pc_area_map.py` — builds `pc_area_map.json`: an authoritative postcode→area mapping
  using the live `/api/serviceArea/find` endpoint, so the postcode CSVs can be expressed in the
  **same 301 areas** the live archive uses. ("Resonates with current data" = it uses the current
  backend's own mapping.)
- `build_area_history.py` — aggregates the CSVs to area level → `area_status_history.json`.

## Provenance & honest limitations

- **Source:** `web.archive.org` captures of `capaciteitskaart.netbeheernederland.nl/dashboard/download`
  (the map's old version; the endpoint no longer exists). Capture dates below.
- **Only 2 of 7 snapshots are full-national** (2024-01-11, 2024-03-03, ~465k postcodes). The
  other 5 (2023-03-27, 2023-06-11, 2023-09-28, 2023-12-07, 2024-05-26) were **truncated by the
  Archive at ~1 MB** — they cover only postcodes up to ~2585 (Noord-Holland + northern
  Zuid-Holland). Areas outside that range have no value in those snapshots.
- **Colour only.** These old exports do **not** contain queue volumes, unique requests,
  expected-relief years, or planned projects. Those richer fields — the crown jewel, especially
  relief dates — have **no historical source** and exist only from the live archive forward.
- **Mapping is RNB-level** (280 of 301 areas); the 21 TenneT regions aren't mapped in this pass.
- Colour semantics of the old export may not be a perfect 1:1 with today's per-area status; treat
  this as an indicative historical trend, not an exact continuation of the live series.

## Rebuild

```bash
python backfill/build_pc_area_map.py     # ~12 min, live find calls (one-off)
python backfill/build_area_history.py    # instant, offline
```
