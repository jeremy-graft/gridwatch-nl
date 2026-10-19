# Netcongestie Monitor

*Data as of 2026-10-12. Generated from the [gridwatch-nl](https://github.com/jeremy-graft/gridwatch-nl) archive. Covers **7 source publications** from **2026-07-17** to **2026-10-12** (305 live areas). Indicative only — see Methodology.*

## Headline

- **Companies waiting for withdrawal capacity: 10,507 → 11,857 (+12.8%)** since 2026-07-17.
- Withdrawal queue: 20,931 → 21,254 MW (+1.5%); injection queue: 16,915 → 14,889 MW (-12.0%).
- **278 of 305 areas** currently have a withdrawal queue.
- Area relief dates: **7 confirmed slips**, **6 confirmed pull-forwards**, 0 unconfirmed (latest publication only), **0 moved-then-reverted**, **0 withdrawn**, 1 moved and then left the map.
- **2026 promise ledger:** of **83** area relief dates promised for 2026 on 2026-07-17, 64 still say 2026, **4 have been pushed later** (4 confirmed), 0 withdrawn, 15 no longer on the map.

## The 2026 promise ledger

On **2026-07-17**, the first publication in this archive, operators promised that congestion would be resolved in **2026** for **83 area/direction pairs**. The source map only ever shows the *current* promise; this ledger keeps the original. When 2026 ends, every entry still showing 2026 becomes *overdue*.

| status | count |
|---|---:|
| pushed later (confirmed) | 4 |
| area no longer on the map (retired or renamed) | 15 |
| still 2026 | 64 |

| area | direction | promised | now | status |
|---|---|---:|---:|---|
| `OS ZALTBOMMEL 10-1i` (Liander, Gelderland) | afname | 2026 | 2035 | pushed later (confirmed) |
| `DVTB` (Enexis, Overijssel) | afname | 2026 | 2029 | pushed later (confirmed) |
| `MSBT` (Enexis, Limburg) | afname | 2026 | 2028 | pushed later (confirmed) |
| `OS DRUTEN 10-1i` (Liander, Gelderland) | invoeding | 2026 | 2027 | pushed later (confirmed) |

## National queue trend

| source publication | live areas | withdrawal queue (MW) | injection queue (MW) | waiting (withdrawal) | waiting (injection) |
|---|---:|---:|---:|---:|---:|
| 2026-07-17 | 301 | 20,931 | 16,915 | 10,507 | 7,251 |
| 2026-07-29 | 301 | 20,931 | 16,915 | 10,507 | 7,251 |
| 2026-08-10 | 301 | 21,120 | 17,058 | 11,292 | 7,296 |
| 2026-08-17 | 305 | 21,191 | 17,471 | 11,743 | 7,405 |
| 2026-09-07 | 305 | 21,254 | 14,907 | 11,823 | 7,395 |
| 2026-10-08 | 305 | 21,254 | 14,907 | 11,823 | 7,395 |
| 2026-10-12 | 305 | 21,254 | 14,889 | 11,857 | 7,364 |

> Sums over *live* areas at each publication. Inventory reorganisations (see below) can move these numbers without any change in real demand — read a step change that coincides with an inventory change with care.

## Relief dates — what actually moved

A move only counts as **slippage** once it has held for two consecutive publications. This guards against corrections and one-off publication glitches; single-publication moves are listed separately as *unconfirmed*. So far 0 of 14 area-level moves have reverted.

### Area-level relief year (`yearSolved*`)

#### Confirmed slips (later)

| area | direction | was | now | change | held for |
|---|---|---:|---:|---:|---:|
| `OS ZALTBOMMEL 10-1i` | afname | 2026 | 2035 | +9y | 7 cycles |
| `KELP` | invoeding | 2027 | 2033 | +6y | 7 cycles |
| `DVTB` | afname | 2026 | 2029 | +3y | 7 cycles |
| `OS ALKMAAR 10-1i` | afname | 2033 | 2035 | +2y | 7 cycles |
| `MSBT` | afname | 2026 | 2028 | +2y | 7 cycles |
| `OS CULEMBORG 10-1i` | invoeding | 2035 | 2036 | +1y | 7 cycles |
| `OS DRUTEN 10-1i` | invoeding | 2026 | 2027 | +1y | 7 cycles |

#### Confirmed pull-forwards (earlier)

| area | direction | was | now | change | held for |
|---|---|---:|---:|---:|---:|
| `OS MEDEMBLIK 10-2i` | afname | 2031 | 2027 | -4y | 7 cycles |
| `OS TEXEL 10-1i` | afname | 2032 | 2028 | -4y | 7 cycles |
| `OS OVERVEEN 10-2i` | afname | 2030 | 2028 | -2y | 7 cycles |
| `OS NUNSPEET 10-1i` | afname | 2030 | 2029 | -1y | 7 cycles |
| `OS NUNSPEET 10-2i` | afname | 2030 | 2029 | -1y | 7 cycles |
| `OS HOORN HOLENWEG 10-1i` | afname | 2031 | 2030 | -1y | 4 cycles |

#### Moved, then reverted (0)

These looked like slips or pull-forwards in one publication and were undone in a later one.

### Planned-expansion projects (published delivery window)

Tracked on the published window (`dateString`, e.g. *Tussen 2031 en 2033*), not on the source's `year` field, which alternates between a window's start and end without the window changing. See Methodology.

#### Confirmed slips

| area | operator | project | was | now | change |
|---|---|---|---:|---:|---:|
| `EHVZ` | Enexis | Extra capaciteit op Eindhoven Zuid | 2026 | 2030 | +4y |
| `NEDW` | Enexis | Extra capaciteit op Nederweert | 2029–open | 2032–open | +3y |
| `HPS` | Enexis | Extra capaciteit op Haps | 2028 | 2029 | +1y |

#### Confirmed pull-forwards

_none_

Projects: 6,148 stable · 0 reverted · 3 confirmed slips · 0 confirmed pull-forwards · 1 unconfirmed · 0 withdrawn.

## This publication (2026-10-12)

1 project delivery windows changed in the latest publication (unconfirmed until they hold in the next one):

| area | operator | project | was | now |
|---|---|---|---:|---:|
| `OS MARNEZIJL 20-3i` | Liander | Extra capaciteit op knooppunt OS MARNEZIJL SUB 1 | 2029 Q2 | 2029 Q4 |

## Reliability of published relief dates, by operator

How often an operator's published project delivery windows changed across the archive (projects seen in at least 3 publications).

| operator | projects tracked | moved | moved % | of which reverted | confirmed changes |
|---|---:|---:|---:|---:|---:|
| Enexis | 83 | 3 | 3.6% | 0 (0.0%) | 3 |
| Liander | 125 | 1 | 0.8% | 0 (0.0%) | 0 |
| TenneT | 5,817 | 0 | 0.0% | 0 (0%) | 0 |
| Rendo | 1 | 0 | 0.0% | 0 (0%) | 0 |
| Stedin | 126 | 0 | 0.0% | 0 (0%) | 0 |

## Area inventory changes

- **2026-08-17**: 61 areas added, 58 retired (e.g. `Amstelveen`, `BEEK`, `Bijlmer Noord 10kV totaal`, `CM08`, `CM10`, `CM20`…).

## Methodology & caveats

- **Source:** Netbeheer Nederland's public capaciteitskaart (`data.partnersinenergie.nl/api`), archived verbatim by gridwatch-nl on every source publication. The source states its figures are *indicative*, a snapshot, and that no rights can be derived from them; the same applies here.
- **Publications, not days:** one row per distinct source re-ingest (`dataUpdate.executedOn`), so the series is irregular — the source publishes every ~1–3 weeks.
- **Persistence:** a move is *confirmed* only after holding for two consecutive publications, so that corrections and one-off publication glitches are not reported as slippage.
- **Project dates are the published window, not `year`:** for projects with a range (*Tussen 2031 en 2033*) the source's `year` field alternates between the start and the end year from one publication to the next while the published range stays the same. Reading `year` makes such projects look like they slip and recover constantly (an earlier version of this report did exactly that). The report therefore compares the published window itself; a shift within the same year (e.g. Q2 → Q4) counts as a move.
- **Identity:** projects are matched across publications on (area, operator, name); the source's numeric ids rotate on every ingest and are never used.
- **Sentinel:** a year ≥ 2090 means *no date*. For an area relief year it is reported as *withdrawn*; for a project it means the window has no end date (*Tussen 2030 en 2099* is shown as *2030–open*). Never treated as a multi-decade slip.
- **Past-dated** years occur in the source and are excluded from slip/pull arithmetic.
- **Inventory churn:** areas are periodically retired or renamed; queue totals are summed over *live* areas only. Retired areas keep their last known values in the archive but are excluded here. A renamed area can't be linked to its new id, so in the promise ledger it is reported as *no longer on the map*, never as a kept promise.
- **Short baseline:** 7 publications over 87 days. Operator-level reliability figures in particular are early signal, not verdict.
