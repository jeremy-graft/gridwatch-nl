# Netcongestie Monitor

*Data as of 2026-10-19. Generated from the [gridwatch-nl](https://github.com/jeremy-graft/gridwatch-nl) archive. Covers **8 source publications** from **2026-07-17** to **2026-10-19** (296 live areas). Indicative only — see Methodology.*

## Headline

- **Regional grids — requests waiting for withdrawal capacity: 10,388 → 11,367 (+9.4%)** since 2026-07-17; withdrawal queue 5,558 → 5,793 MW.
- **TenneT (high voltage) — withdrawal queue: 15,373 → 8,560 MW (-44.3%)**; injection 9,842 → 6,038 MW. Reported separately: TenneT's regions overlap the regional areas and measure a different queue.
- **270 of 296 areas** currently have a withdrawal queue.
- **Latest publication (2026-10-12 → 2026-10-19), like-for-like over the 20 TenneT areas present in both:** withdrawal queue 14,209 → 8,360 MW (-41.2%), requests waiting 110 → 75. Single publication, so unconfirmed.
- Area relief dates: **7 confirmed slips**, **6 confirmed pull-forwards**, 1 unconfirmed (latest publication only), **0 moved-then-reverted**, **0 withdrawn**, 1 moved and then left the map.
- **2026 promise ledger:** of **83** area relief dates promised for 2026 on 2026-07-17, 66 still say 2026, **4 have been pushed later** (4 confirmed), 0 withdrawn, 13 no longer on the map.

## The 2026 promise ledger

On **2026-07-17**, the first publication in this archive, operators promised that congestion would be resolved in **2026** for **83 area/direction pairs**. The source map only ever shows the *current* promise; this ledger keeps the original. When 2026 ends, every entry still showing 2026 becomes *overdue*.

| status | count |
|---|---:|
| pushed later (confirmed) | 4 |
| area no longer on the map (retired or renamed) | 13 |
| still 2026 | 66 |

| area | direction | promised | now | status |
|---|---|---:|---:|---|
| `OS ZALTBOMMEL 10-1i` (Liander, Gelderland) | afname | 2026 | 2035 | pushed later (confirmed) |
| `DVTB` (Enexis, Overijssel) | afname | 2026 | 2029 | pushed later (confirmed) |
| `MSBT` (Enexis, Limburg) | afname | 2026 | 2028 | pushed later (confirmed) |
| `OS DRUTEN 10-1i` (Liander, Gelderland) | invoeding | 2026 | 2027 | pushed later (confirmed) |

## Queue trend

Regional (distribution) grids and TenneT are shown separately and never added together.

| source publication | regional areas | regional withdrawal queue (MW) | regional requests waiting | TenneT regions | TenneT withdrawal queue (MW) | TenneT injection queue (MW) |
|---|---:|---:|---:|---:|---:|---:|
| 2026-07-17 | 280 | 5,558 | 10,388 | 21 | 15,373 | 9,842 |
| 2026-07-29 | 280 | 5,558 | 10,388 | 21 | 15,373 | 9,842 |
| 2026-08-10 | 280 | 5,747 | 11,173 | 21 | 15,373 | 9,842 |
| 2026-08-17 | 283 | 5,818 | 11,624 | 22 | 15,373 | 9,842 |
| 2026-09-07 | 283 | 5,880 | 11,704 | 22 | 15,373 | 9,842 |
| 2026-10-08 | 283 | 5,880 | 11,704 | 22 | 15,373 | 9,842 |
| 2026-10-12 | 283 | 5,881 | 11,738 | 22 | 15,373 | 9,842 |
| 2026-10-19 | 273 | 5,793 | 11,367 | 23 | 8,560 | 6,038 |

> **TenneT's queue figures were identical in 7 consecutive publications (2026-07-17 – 2026-10-12) before changing in 2026-10-19.** Treat TenneT queue values as possibly stale between its own updates.

> Sums over *live* areas at each publication. Inventory reorganisations (see below) can move these numbers without any change in real demand — read a step change that coincides with an inventory change with care.

## Relief dates — what actually moved

A move only counts as **slippage** once it has held for two consecutive publications. This guards against corrections and one-off publication glitches; single-publication moves are listed separately as *unconfirmed*. So far 0 of 15 area-level moves have reverted.

### Area-level relief year (`yearSolved*`)

#### Confirmed slips (later)

| area | direction | was | now | change | held for |
|---|---|---:|---:|---:|---:|
| `OS ZALTBOMMEL 10-1i` | afname | 2026 | 2035 | +9y | 8 cycles |
| `KELP` | invoeding | 2027 | 2033 | +6y | 8 cycles |
| `DVTB` | afname | 2026 | 2029 | +3y | 8 cycles |
| `OS ALKMAAR 10-1i` | afname | 2033 | 2035 | +2y | 7 cycles |
| `MSBT` | afname | 2026 | 2028 | +2y | 8 cycles |
| `OS CULEMBORG 10-1i` | invoeding | 2035 | 2036 | +1y | 8 cycles |
| `OS DRUTEN 10-1i` | invoeding | 2026 | 2027 | +1y | 8 cycles |

#### Confirmed pull-forwards (earlier)

| area | direction | was | now | change | held for |
|---|---|---:|---:|---:|---:|
| `OS MEDEMBLIK 10-2i` | afname | 2031 | 2027 | -4y | 8 cycles |
| `OS TEXEL 10-1i` | afname | 2032 | 2028 | -4y | 8 cycles |
| `OS OVERVEEN 10-2i` | afname | 2030 | 2028 | -2y | 8 cycles |
| `OS NUNSPEET 10-1i` | afname | 2030 | 2029 | -1y | 8 cycles |
| `OS NUNSPEET 10-2i` | afname | 2030 | 2029 | -1y | 8 cycles |
| `OS HOORN HOLENWEG 10-1i` | afname | 2031 | 2030 | -1y | 4 cycles |

#### Unconfirmed — moved in the latest publication only, may still revert

| area | direction | was | now |
|---|---|---:|---:|
| `OS EDAM 10-2i` | afname | 2027 | 2026 |

#### Moved, then reverted (0)

These looked like slips or pull-forwards in one publication and were undone in a later one.

### Planned-expansion projects (published delivery window)

Tracked on the published window (`dateString`, e.g. *Tussen 2031 en 2033*), not on the source's `year` field, which alternates between a window's start and end without the window changing. See Methodology.

#### Confirmed slips

| area | operator | project | was | now | change |
|---|---|---|---:|---:|---:|
| `EHVZ` | Enexis | Extra capaciteit op Eindhoven Zuid | 2026 | 2030 | +4y |
| `NEDW` | Enexis | Extra capaciteit op Nederweert | 2029–open | 2032–open | +3y |
| `OS MARNEZIJL 20-3i` | Liander | Extra capaciteit op knooppunt OS MARNEZIJL SUB 1 | 2029 Q2 | 2029 Q4 | +1y |
| `HPS` | Enexis | Extra capaciteit op Haps | 2028 | 2029 | +1y |

#### Confirmed pull-forwards

_none_

Projects: 6,156 stable · 0 reverted · 4 confirmed slips · 0 confirmed pull-forwards · 0 unconfirmed · 0 withdrawn.

## This publication (2026-10-19)

No project delivery windows changed in the latest publication.

## Reliability of published relief dates, by operator

How often an operator's published project delivery windows changed across the archive (projects seen in at least 3 publications).

| operator | projects tracked | moved | moved % | of which reverted | confirmed changes |
|---|---:|---:|---:|---:|---:|
| Enexis | 83 | 3 | 3.6% | 0 (0.0%) | 3 |
| Liander | 125 | 1 | 0.8% | 0 (0.0%) | 1 |
| TenneT | 5,817 | 0 | 0.0% | 0 (0%) | 0 |
| Rendo | 1 | 0 | 0.0% | 0 (0%) | 0 |
| Stedin | 126 | 0 | 0.0% | 0 (0%) | 0 |

## Area inventory changes

- **2026-08-17**: 61 areas added, 58 retired (e.g. `Amstelveen`, `BEEK`, `Bijlmer Noord 10kV totaal`, `CM08`, `CM10`, `CM20`…).
- **2026-10-19**: 44 areas added, 53 retired (e.g. `BLER`, `CM23`, `CM35/72`, `CM56`, `CM59`, `CM66`…).

## Methodology & caveats

- **Source:** Netbeheer Nederland's public capaciteitskaart (`data.partnersinenergie.nl/api`), archived verbatim by gridwatch-nl on every source publication. The source states its figures are *indicative*, a snapshot, and that no rights can be derived from them; the same applies here.
- **Publications, not days:** one row per distinct source re-ingest (`dataUpdate.executedOn`), so the series is irregular — the source publishes every ~1–3 weeks.
- **Persistence:** a move is *confirmed* only after holding for two consecutive publications, so that corrections and one-off publication glitches are not reported as slippage.
- **Project dates are the published window, not `year`:** for projects with a range (*Tussen 2031 en 2033*) the source's `year` field alternates between the start and the end year from one publication to the next while the published range stays the same. Reading `year` makes such projects look like they slip and recover constantly (an earlier version of this report did exactly that). The report therefore compares the published window itself; a shift within the same year (e.g. Q2 → Q4) counts as a move.
- **Identity:** projects are matched across publications on (area, operator, name); the source's numeric ids rotate on every ingest and are never used.
- **Sentinel:** a year ≥ 2090 means *no date*. For an area relief year it is reported as *withdrawn*; for a project it means the window has no end date (*Tussen 2030 en 2099* is shown as *2030–open*). Never treated as a multi-decade slip.
- **Past-dated** years occur in the source and are excluded from slip/pull arithmetic.
- **Inventory churn:** areas are periodically retired or renamed; queue totals are summed over *live* areas only. Retired areas keep their last known values in the archive but are excluded here. A renamed area can't be linked to its new id, so in the promise ledger it is reported as *no longer on the map*, never as a kept promise. Inventory changes are dated by the publication in which the archive *detected* them: the area list is refreshed from the map about monthly, so a change may have happened up to a few publications earlier.
- **Short baseline:** 8 publications over 94 days. Operator-level reliability figures in particular are early signal, not verdict.
