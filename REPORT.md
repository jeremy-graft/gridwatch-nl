# Netcongestie Monitor

*Data as of 2026-11-16. Generated from the [gridwatch-nl](https://github.com/jeremy-graft/gridwatch-nl) archive. Covers **10 source publications** from **2026-07-17** to **2026-11-16** (590 live areas). Indicative only — see Methodology.*

## Headline

- **Requests waiting for withdrawal capacity, like-for-like since 2026-07-17:** Liander +8.9%, Enexis +13.1%. **Stedin is not comparable across 2026-10-30**: its count went ×5.1 in that one publication (706 → 3,620 on the same areas) while its queue went 917 → 805 MW — the signature of a change in what is counted, not of new demand.
- Across all 567 regional areas now covered: 21,370 requests waiting, 7,900 MW (per-operator definitions differ; see Queue by operator).
- **TenneT (high voltage) — withdrawal queue: 14,209 → 8,360 MW (-41.2%)**; injection 9,842 → 6,038 MW. Reported separately: TenneT's regions overlap the regional areas and measure a different queue.
- **441 of 590 areas** currently have a withdrawal queue.
- **Enexis's figures were last updated 2026-08-01** — 107 days before the latest publication. Its areas show that date's state.
- **Coverage:** the archive covers all 590 areas on the map since 2026-11-17; before that it covered roughly half (see Methodology), so earlier-period figures are partial and trends are given like-for-like.
- **Latest publication (2026-10-30 → 2026-11-16), like-for-like over the 273 regional areas present in both:** withdrawal queue 5,688 → 5,743 MW (+1.0%), requests waiting 15,022 → 15,117. Single publication, so unconfirmed.
- Area relief dates: **10 confirmed slips**, **7 confirmed pull-forwards**, 3 unconfirmed (latest publication only), **0 moved-then-reverted**, **0 withdrawn**.
- **2026 promise ledger:** of **83** area relief dates promised for 2026 on 2026-07-17, 75 still say 2026, **5 have been pushed later** (5 confirmed), 0 withdrawn, 3 no longer on the map.

## The 2026 promise ledger

On **2026-07-17**, the first publication in this archive, operators promised that congestion would be resolved in **2026** for **83 area/direction pairs** (of the areas the archive covered then — about half the map; see Methodology). The source map only ever shows the *current* promise; this ledger keeps the original. When 2026 ends, every entry still showing 2026 becomes *overdue*.

| status | count |
|---|---:|
| pushed later (confirmed) | 5 |
| area no longer on the map (retired or renamed) | 3 |
| still 2026 | 75 |

| area | direction | promised | now | status |
|---|---|---:|---:|---|
| `OS ZALTBOMMEL 10-1i` (Liander, Gelderland) | afname | 2026 | 2035 | pushed later (confirmed) |
| `ESDH` (Enexis, Overijssel) | afname | 2026 | 2030 | pushed later (confirmed) |
| `DVTB` (Enexis, Overijssel) | afname | 2026 | 2029 | pushed later (confirmed) |
| `MSBT` (Enexis, Noord-Brabant) | afname | 2026 | 2028 | pushed later (confirmed) |
| `OS DRUTEN 10-1i` (Liander, Gelderland) | invoeding | 2026 | 2027 | pushed later (confirmed) |

## Queue by operator (like-for-like)

Requests waiting and queue size for withdrawal capacity, over the areas each operator had in both the first (2026-07-17) and the latest (2026-11-16) publication. Operators are never summed: they count requests differently, and a single operator's definition can change.

| operator | areas | requests waiting | change | queue (MW) | step changes |
|---|---:|---:|---:|---:|---|
| Liander | 116 | 3,324 → 3,621 | +8.9% | 1,691 → 1,912 | — |
| Enexis | 101 | 5,985 → 6,770 | +13.1% | 2,840 → 3,028 | — |
| Stedin | 55 | 952 → 4,714 | n/a (step change) | 994 → 883 | 2026-10-30: 706 → 3,620 requests, avg 1.3 → 0.22 MW/request |
| Westland | 2 | 0 → 0 | n/a | 0 → 0 | — |

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
| 2026-10-30 | 274 | 5,692 | 15,046 | 23 | 8,560 | 6,038 |
| 2026-11-16 | 567 | 7,900 | 21,370 | 23 | 8,560 | 6,038 |

> Per-publication sums over the areas archived at that publication. They mix operators that count requests differently and, before 2026-11-17, covered only about half the areas — use *Queue by operator* above for trends.

> Sums over *live* areas at each publication. Inventory reorganisations (see below) can move these numbers without any change in real demand — read a step change that coincides with an inventory change with care.

## Relief dates — what actually moved

A move only counts as **slippage** once it has held for two consecutive publications. This guards against corrections and one-off publication glitches; single-publication moves are listed separately as *unconfirmed*. So far 0 of 20 area-level moves have reverted.

### Area-level relief year (`yearSolved*`)

#### Confirmed slips (later)

| area | direction | was | now | change | held for |
|---|---|---:|---:|---:|---:|
| `OS ZALTBOMMEL 10-1i` | afname | 2026 | 2035 | +9y | 10 cycles |
| `OS HOOFDDORP 10-2i` | afname | 2032 | 2038 | +6y | 5 cycles |
| `KELP` | invoeding | 2027 | 2033 | +6y | 10 cycles |
| `ESDH` | afname | 2026 | 2030 | +4y | 4 cycles |
| `DVTB` | afname | 2026 | 2029 | +3y | 10 cycles |
| `OS ALKMAAR 10-1i` | afname | 2033 | 2035 | +2y | 8 cycles |
| `MSBT` | afname | 2026 | 2028 | +2y | 10 cycles |
| `CM79` | afname | 2031 | 2033 | +2y | 10 cycles |
| `OS CULEMBORG 10-1i` | invoeding | 2035 | 2036 | +1y | 10 cycles |
| `OS DRUTEN 10-1i` | invoeding | 2026 | 2027 | +1y | 10 cycles |

#### Confirmed pull-forwards (earlier)

| area | direction | was | now | change | held for |
|---|---|---:|---:|---:|---:|
| `OS MEDEMBLIK 10-2i` | afname | 2031 | 2027 | -4y | 10 cycles |
| `OS TEXEL 10-1i` | afname | 2032 | 2028 | -4y | 10 cycles |
| `OS OVERVEEN 10-2i` | afname | 2030 | 2028 | -2y | 10 cycles |
| `OS EDAM 10-2i` | afname | 2027 | 2026 | -1y | 6 cycles |
| `OS NUNSPEET 10-1i` | afname | 2030 | 2029 | -1y | 10 cycles |
| `OS NUNSPEET 10-2i` | afname | 2030 | 2029 | -1y | 10 cycles |
| `OS HOORN HOLENWEG 10-1i` | afname | 2031 | 2030 | -1y | 5 cycles |

#### Unconfirmed — moved in the latest publication only, may still revert

| area | direction | was | now |
|---|---|---:|---:|
| `OS ENKHUIZEN 10-1i` | afname | 2031 | 2034 |
| `OS VLIEGENBOS 10-1i` | afname | 2027 | 2032 |
| `OS NOORD PAPAVERWEG 10-1i` | afname | 2027 | 2031 |

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

Projects: 7,018 stable · 0 reverted · 4 confirmed slips · 0 confirmed pull-forwards · 3 unconfirmed · 0 withdrawn.

## This publication (2026-11-16)

3 project delivery windows changed in the latest publication (unconfirmed until they hold in the next one):

| area | operator | project | was | now |
|---|---|---|---:|---:|
| `OS VLIEGENBOS 10-1i` | Liander | Extra capaciteit op knooppunt OS VLIEGENBOS 10-1 | 2027 Q2 | 2032 Q2 |
| `OS NOORD PAPAVERWEG 10-1i` | Liander | Extra capaciteit op knooppunt OS NOORD PAPAVERWE | 2027 Q2 | 2031 Q1 |
| `OS SCHENKENSCHANS 10-1i` | Liander | Extra capaciteit op knooppunt OS SCHENKENSCHANS  | 2032 Q1 | 2031 Q4 |

## Reliability of published relief dates, by operator

How often an operator's published project delivery windows changed across the archive (projects seen in at least 3 publications).

| operator | projects tracked | moved | moved % | of which reverted | confirmed changes |
|---|---:|---:|---:|---:|---:|
| Enexis | 85 | 3 | 3.5% | 0 (0.0%) | 3 |
| Liander | 136 | 4 | 2.9% | 0 (0.0%) | 1 |
| TenneT | 5,997 | 0 | 0.0% | 0 (0%) | 0 |
| Rendo | 1 | 0 | 0.0% | 0 (0%) | 0 |
| Stedin | 126 | 0 | 0.0% | 0 (0%) | 0 |

## Data freshness by operator

When each operator last updated its figures on the map, as of the latest publication (2026-11-16). Read from the source's own per-operator update stamps, which match every observed change in the archive.

| operator | last update | days before latest publication | oldest category |
|---|---|---:|---|
| Enexis | 2026-08-01 | 107 ⚠️ | available capacity (2026-08-01) |
| TenneT | 2026-10-19 | 28 | available capacity (2026-10-19) |
| Liander | 2026-10-30 | 17 | available capacity (2026-10-30) |
| Stedin | 2026-10-30 | 17 | available capacity (2026-10-30) |

## Area inventory changes

Not reported before 2026-11-17: area lists before then were read from a low-zoom map tile that omits about half the areas, so list-to-list differences measured the tile, not the map (148 of 155 'retirements' reported Aug–Nov 2026 are still on the map). Real changes are reported from the next full-coverage refresh on.

## Methodology & caveats

- **Coverage:** until 2026-11-17 the archive read its area list from the zoom-0 map tile, in which the whole world is one 4096-unit tile (~10 km per unit). Small, mostly urban areas become sub-pixel there and are silently dropped — a different set after each tileset rebuild. The archive therefore covered roughly 300 of ~590 areas (Stedin and Liander's urban areas worst), and what looked like area reorganisations were this artifact. Since 2026-11-17 the list is read at zoom 7, which matches zoom 8 exactly (590 areas). Totals from before that date are partial; long-run trends are reported like-for-like.
- **Source:** Netbeheer Nederland's public capaciteitskaart (`data.partnersinenergie.nl/api`), archived verbatim by gridwatch-nl on every source publication. The source states its figures are *indicative*, a snapshot, and that no rights can be derived from them; the same applies here.
- **Publications, not days:** one row per distinct source re-ingest (`dataUpdate.executedOn`), so the series is irregular — the source publishes every ~1–3 weeks.
- **Persistence:** a move is *confirmed* only after holding for two consecutive publications, so that corrections and one-off publication glitches are not reported as slippage.
- **Project dates are the published window, not `year`:** for projects with a range (*Tussen 2031 en 2033*) the source's `year` field alternates between the start and the end year from one publication to the next while the published range stays the same. Reading `year` makes such projects look like they slip and recover constantly (an earlier version of this report did exactly that). The report therefore compares the published window itself; a shift within the same year (e.g. Q2 → Q4) counts as a move.
- **Identity:** projects are matched across publications on (area, operator, name); the source's numeric ids rotate on every ingest and are never used.
- **Sentinel:** a year ≥ 2090 means *no date*. For an area relief year it is reported as *withdrawn*; for a project it means the window has no end date (*Tussen 2030 en 2099* is shown as *2030–open*). Never treated as a multi-decade slip.
- **Past-dated** years occur in the source and are excluded from slip/pull arithmetic.
- **Inventory churn:** areas are periodically retired or renamed; queue totals are summed over *live* areas only. Retired areas keep their last known values in the archive but are excluded here. A renamed area can't be linked to its new id, so in the promise ledger it is reported as *no longer on the map*, never as a kept promise. Inventory changes are dated by the publication in which the archive *detected* them: the area list is refreshed from the map about monthly, so a change may have happened up to a few publications earlier.
- **Short baseline:** 10 publications over 122 days. Operator-level reliability figures in particular are early signal, not verdict.
