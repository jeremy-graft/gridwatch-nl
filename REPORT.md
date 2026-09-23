# Netcongestie Monitor

*Auto-generated 2026-09-23 from the [gridwatch-nl](https://github.com/jeremy-graft/gridwatch-nl) archive. Covers **5 source publications** from **2026-07-17** to **2026-09-07** (305 live areas). Indicative only — see Methodology.*

## Headline

- **Companies waiting for withdrawal capacity: 10,507 → 11,823 (+12.5%)** since 2026-07-17.
- Withdrawal queue: 20,931 → 21,254 MW (+1.5%); injection queue: 16,915 → 14,907 MW (-11.9%).
- **279 of 305 areas** currently have a withdrawal queue.
- Area relief dates: **3 confirmed slips**, **0 confirmed pull-forwards**, 10 unconfirmed (latest publication only), **0 moved-then-reverted**, **0 withdrawn**, 1 moved and then left the map.
- **2026 promise ledger:** of **83** area relief dates promised for 2026 on 2026-07-17, 64 still say 2026, **4 have been pushed later** (2 confirmed), 0 withdrawn, 15 no longer on the map.

## The 2026 promise ledger

On **2026-07-17**, the first publication in this archive, operators promised that congestion would be resolved in **2026** for **83 area/direction pairs**. The source map only ever shows the *current* promise; this ledger keeps the original. When 2026 ends, every entry still showing 2026 becomes *overdue*.

| status | count |
|---|---:|
| pushed later (confirmed) | 2 |
| pushed later (latest publication only) | 2 |
| area no longer on the map (retired or renamed) | 15 |
| still 2026 | 64 |

| area | direction | promised | now | status |
|---|---|---:|---:|---|
| `DVTB` (Enexis, Overijssel) | afname | 2026 | 2029 | pushed later (confirmed) |
| `MSBT` (Enexis, Limburg) | afname | 2026 | 2028 | pushed later (confirmed) |
| `OS ZALTBOMMEL 10-1i` (Liander, Gelderland) | afname | 2026 | 2035 | pushed later (latest publication only) |
| `OS DRUTEN 10-1i` (Liander, Gelderland) | invoeding | 2026 | 2027 | pushed later (latest publication only) |

## National queue trend

| source publication | live areas | withdrawal queue (MW) | injection queue (MW) | waiting (withdrawal) | waiting (injection) |
|---|---:|---:|---:|---:|---:|
| 2026-07-17 | 301 | 20,931 | 16,915 | 10,507 | 7,251 |
| 2026-07-29 | 301 | 20,931 | 16,915 | 10,507 | 7,251 |
| 2026-08-10 | 301 | 21,120 | 17,058 | 11,292 | 7,296 |
| 2026-08-17 | 305 | 21,191 | 17,471 | 11,743 | 7,405 |
| 2026-09-07 | 305 | 21,254 | 14,907 | 11,823 | 7,395 |

> Sums over *live* areas at each publication. Inventory reorganisations (see below) can move these numbers without any change in real demand — read a step change that coincides with an inventory change with care.

## Relief dates — what actually moved

A move only counts as **slippage** once it has held for two consecutive publications. Roughly 40% of observed moves revert, so single-publication moves are listed separately as *unconfirmed*.

### Area-level relief year (`yearSolved*`)

#### Confirmed slips (later)

| area | direction | was | now | change | held for |
|---|---|---:|---:|---:|---:|
| `KELP` | invoeding | 2027 | 2033 | +6y | 5 cycles |
| `DVTB` | afname | 2026 | 2029 | +3y | 5 cycles |
| `MSBT` | afname | 2026 | 2028 | +2y | 5 cycles |

#### Confirmed pull-forwards (earlier)

_none_

#### Unconfirmed — moved in the latest publication only, may still revert

| area | direction | was | now |
|---|---|---:|---:|
| `OS ALKMAAR 10-1i` | afname | 2033 | 2035 |
| `OS CULEMBORG 10-1i` | invoeding | 2035 | 2036 |
| `OS DRUTEN 10-1i` | invoeding | 2026 | 2027 |
| `OS MEDEMBLIK 10-2i` | afname | 2031 | 2027 |
| `OS NUNSPEET 10-1i` | afname | 2030 | 2029 |
| `OS NUNSPEET 10-2i` | afname | 2030 | 2029 |
| `OS OVERVEEN 10-2i` | afname | 2030 | 2028 |
| `OS TEXEL 10-1i` | afname | 2032 | 2028 |
| `OS ZALTBOMMEL 10-1i` | afname | 2026 | 2035 |
| `OS HOORN HOLENWEG 10-1i` | afname | 2031 | 2030 |

#### Moved, then reverted (0)

These looked like slips or pull-forwards in one publication and were undone in a later one.

### Planned-expansion projects (`projects[].year`)

#### Confirmed slips

| area | operator | project | was | now | change |
|---|---|---|---:|---:|---:|
| `EHVZ` | Enexis | Extra capaciteit op Eindhoven Zuid | 2026 | 2030 | +4y |
| `ODZ` | Enexis | Extra capaciteit op Oldenzaal | 2026 | 2029 | +3y |
| `CM20` | Stedin | Nieuw Transformatorstation - Bleiswijk | 2031 | 2033 | +2y |
| `CM22` | Stedin | Nieuw Transformatorstation - Leerdam Oost | 2032 | 2034 | +2y |
| `CM29/64` | Stedin | Transformatorstation Uitbreiden - Sterrenburg | 2032 | 2034 | +2y |
| `HPS` | Enexis | Extra capaciteit op Haps | 2028 | 2029 | +1y |

#### Confirmed pull-forwards

| area | operator | project | was | now | change |
|---|---|---|---:|---:|---:|
| `BLER` | Enexis | Extra capaciteit op Blerick | 2030 | 2026 | -4y |
| `EHVW` | Enexis | Extra capaciteit op Eindhoven West | 2030 | 2027 | -3y |
| `CM00` | Stedin | Transformatorstation Uitbreiden - Oosterland | 2033 | 2031 | -2y |
| `CM13` | Stedin | Nieuw transformatorstation - De Bocht | 2034 | 2032 | -2y |
| `CM31` | Stedin | Nieuw Transformatorstation - Reeuwijk | 2030 | 2029 | -1y |
| `CM63` | Stedin | Verbindingen Verzwaren - Hardinxveld | 2030 | 2029 | -1y |
| `CM84` | Stedin | Nieuw transformatorstation - Hellevoetsluis 2 | 2030 | 2029 | -1y |
| `TS073_10` | Stedin | Transformatorstation Uitbreiden - Zeist | 2030 | 2029 | -1y |

#### Project date withdrawn

| area | operator | project | last date | since |
|---|---|---|---:|---|
| `EHVO` | Enexis | Extra capaciteit op Eindhoven Oost | 2030 | 2026-09-07 |
| `NEDW` | Enexis | Extra capaciteit op Nederweert | 2029 | 2026-09-07 |

Projects: 6,109 stable · 17 reverted · 7 confirmed slips · 9 confirmed pull-forwards · 8 unconfirmed · 2 withdrawn.

## This publication (2026-09-07)

17 project dates moved in the latest publication (unconfirmed until they hold in the next one):

| area | operator | project | was | now |
|---|---|---|---:|---:|
| `BUGG` | Enexis | Extra capaciteit op Buggenum | 2026 | 2033 |
| `CM22` | Stedin | Transformatorstation Uitbreiden - Arkel | 2031 | 2035 |
| `CM29/64` | Stedin | Transformatorstation Uitbreiden - Klaaswaal | 2030 | 2033 |
| `TBN` | Enexis | Extra capaciteit op Tilburg Noord | 2030 | 2028 |
| `CM12` | Stedin | Nieuw Transformatorstation - Bilthoven 2 | 2034 | 2032 |
| `CM12` | Stedin | Nieuw transformatorstation - De Bilt | 2034 | 2032 |
| `CM14` | Stedin | Nieuw Transformatorstation - Utrecht Noord | 2035 | 2033 |
| `CM14` | Stedin | Nieuw Transformatorstation - Maarssenbroek 2 | 2035 | 2033 |
| `CM15` | Stedin | Nieuw Transformatorstation - Soest/Baarn | 2033 | 2031 |
| `CM22` | Stedin | Transformatorstation Uitbreiden - Gorinchem | 2033 | 2031 |
| `CM22` | Stedin | Verbindingen Verzwaren - Vianen | 2032 | 2034 |
| `CM29/64` | Stedin | Nieuw transformatorstation - Heinenoord | 2031 | 2033 |
| `CM29/64` | Stedin | Verbindingen Aanleggen - Klaaswaal | 2033 | 2031 |
| `CM29/64` | Stedin | Transformatorstation Uitbreiden - Dordtse Kil | 2037 | 2035 |
| `CM48` | Stedin | Nieuw transformatorstation - Ridderkerk 2 | 2033 | 2035 |
| `ZLW` | Enexis | Extra capaciteit op Zwolle Weteringkade | 2030 | 2031 |
| `CM29/64` | Stedin | Transformatorstation Uitbreiden - Oud Beijerland | 2030 | 2029 |

## Reliability of published relief dates, by operator

How often an operator's published project dates changed across the archive (projects seen in at least 3 publications). A high *moved* share together with a high *reverted* share means the dates are noisy rather than genuinely slipping.

| operator | projects tracked | moved | moved % | of which reverted | confirmed changes |
|---|---:|---:|---:|---:|---:|
| Stedin | 104 | 30 | 28.8% | 13 (43.3%) | 9 |
| Enexis | 72 | 10 | 13.9% | 4 (40.0%) | 5 |
| Liander | 98 | 0 | 0.0% | 0 (0%) | 0 |
| TenneT | 4,751 | 0 | 0.0% | 0 (0%) | 0 |
| Rendo | 1 | 0 | 0.0% | 0 (0%) | 0 |

## Area inventory changes

- **2026-08-17**: 61 areas added, 58 retired (e.g. `Amstelveen`, `BEEK`, `Bijlmer Noord 10kV totaal`, `CM08`, `CM10`, `CM20`…).

## Methodology & caveats

- **Source:** Netbeheer Nederland's public capaciteitskaart (`data.partnersinenergie.nl/api`), archived verbatim by gridwatch-nl on every source publication. The source states its figures are *indicative*, a snapshot, and that no rights can be derived from them; the same applies here.
- **Publications, not days:** one row per distinct source re-ingest (`dataUpdate.executedOn`), so the series is irregular — the source publishes every ~1–3 weeks.
- **Persistence:** a move is *confirmed* only after holding for two consecutive publications. This is deliberate: a large share of moves revert, and calling a single-publication move 'slippage' would be wrong roughly 40% of the time.
- **Identity:** projects are matched across publications on (area, operator, name); the source's numeric ids rotate on every ingest and are never used.
- **Sentinel:** a year ≥ 2090 means the source withdrew the date. It is reported as *withdrawn*, never as a multi-decade slip.
- **Past-dated** years occur in the source and are excluded from slip/pull arithmetic.
- **Inventory churn:** areas are periodically retired or renamed; queue totals are summed over *live* areas only. Retired areas keep their last known values in the archive but are excluded here. A renamed area can't be linked to its new id, so in the promise ledger it is reported as *no longer on the map*, never as a kept promise.
- **Short baseline:** 5 publications over 52 days. Operator-level reliability figures in particular are early signal, not verdict.
