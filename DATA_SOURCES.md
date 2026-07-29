# DATA_SOURCES.md — gridwatch-nl (Netcongestie Archiver)

**Phase 0 discovery — completed 2026-07-28 (Europe/Amsterdam).**
All findings below were verified live against the running application, not guessed.

---

## 0. Go / No-Go decision

**GO.** ✅

The Dutch grid congestion map is served by a small set of stable, public HTTP(S)
endpoints on Netbeheer Nederland's own infrastructure. The mutable, product-critical
data (queue volumes, expected-relief years, planned expansion projects) is available
as clean JSON with **no authentication**. No robots.txt disallows the target paths;
the only published terms are an indemnifying disclaimer ("no rights can be derived"),
not an access or reuse prohibition. This is public infrastructure data published by
regulated monopolies expressly "voor publiek inzicht."

**The backend publishes its own OpenAPI spec** at `/api/v3/api-docs` (+ Swagger UI at
`/api/swagger-ui/index.html`). It is a Spring Boot service under context path `/api`,
and the spec is the authoritative, complete endpoint list — see §2. This is what makes
the strategy below safe to commit to: we are not guessing the surface, we have it.

**Two constraints / two gifts shaped the recommended design (§5):**

- *Gift:* `GET /api/manifests` returns per-operator, per-category **last-updated
  timestamps** plus a global dataset-version id. This is a 1-request **change-detection
  oracle** → we do NOT need to sweep every area every day. See §5.
- *Constraint:* geometry/tiles are hosted on MapTiler under a key belonging to
  Netbeheer's account; MapTiler ToS forbids using another party's key as your own. We
  keep the archiver's recurring job entirely on Netbeheer's own API and touch MapTiler
  only for a rare area-id enumeration. See §5.2.

**Corrected rate reality:** the brief's "< 50 requests per snapshot" target assumed an
ArcGIS whole-layer GeoJSON endpoint. That does not exist, and there is **no bulk
endpoint** (confirmed against the OpenAPI spec, not guessed). A *full* detail sweep is
**~301 sequential `serviceArea/get` calls** (one per unique area id — the true count,
not the earlier ~225 estimate). **But that sweep should run only when `manifests` shows
the data changed** (operators update every few weeks, not daily), not every morning.
The daily job is ~2 cheap requests. See §5 for the full strategy — this supersedes the
"sweep everything daily" reading of the brief.

---

## 1. Source application — how the map actually works

- Public URL: `https://capaciteitskaart.netbeheernederland.nl/`
  → serves the SPA hosted at `https://data.partnersinenergie.nl/capaciteitskaart/`.
- Stack: **React Router v7 (SSR) + MapLibre GL**, fronted by **Cloudflare**.
  Analytics: Matomo (`analytics.mijnenergiedata.nl`). Error tracking: Sentry.
- The map is drawn from **MapTiler-hosted vector tiles** (geometry + congestion colour).
  Per-area detail is fetched on demand from Netbeheer's **`/api/servicearea/*`** JSON API.
- Route pages (`/capaciteitskaart/{layer}/{direction}`) return **only the HTML shell**.
  Their `.data` sibling (`…/{layer}/{direction}.data`, React-Router turbo-stream format)
  returns **only client config** — notably `CAPACITEITSKAART_TILES_URL`. It does **not**
  contain feature data. Do not archive `.data`; it is config, not data.

There are two logical map "layers" × two "directions":

| layer (`mapName`) | meaning              | direction (`layerId`) | meaning                       |
|-------------------|----------------------|-----------------------|-------------------------------|
| `rnb`             | Regional netbeheerders (Liander/Enexis/Stedin/…) | `afname`    | consumption / withdrawal      |
| `tennet`          | TenneT (national HV grid) | `invoeding`      | feed-in / injection           |
| `totaal`          | combined overview    |                       |                               |

Note: a single unified source (this map) covers **both** RNB and TenneT. The standalone
TenneT `netcapaciteitskaart` on tennet.eu is **not needed** — TenneT areas are included
here as their own tile layers and `servicearea/get` returns TenneT fields inline.

---

## 2. Verified endpoints

Base: `https://data.partnersinenergie.nl`

### 2.1 `POST /api/servicearea/get`  ← PRIMARY DAILY DATA SOURCE
Returns the full detail record for one service area (both directions in one response).

- Request body: `{"id": "<serviceAreaId>"}` — e.g. `{"id":"OS WESTZAANSTRAAT 10-1i"}`
- `{}` or an unknown shape → HTTP 400. `{"id":""}` → 200 with empty area.
- Response: `{"serviceArea": { …see field dictionary §3… }}`
- Content-Type: `application/json`; gzipped; `cf-cache-status: DYNAMIC` (not cached).
- Auth: none. CORS: same-origin app; server sets `Vary: Origin`.

### 2.2 `POST /api/servicearea/find`  ← id lookup by postcode (enumeration aid)
Maps a postcode to a service-area id.

- Request body:
  `{"postalCode6":"1012AB","gridOperatorType":"RNB","energyFlowDirection":"WITHDRAWAL"}`
- Enums (decoded from the client bundle):
  - `gridOperatorType`: `RNB` | `TENNET` | `TOTAAL`
  - `energyFlowDirection`: `WITHDRAWAL` (=afname) | `INJECTION` (=invoeding)
- Response: `{"serviceArea":{"id":"OS WESTZAANSTRAAT 10-1i"}}`
- Error names surfaced by the client: `Postcode niet gevonden` (404),
  `Postcode incorrect` (400).

### 2.3 Vector tiles (MapTiler — geometry + congestion status)  ← BOOTSTRAP ONLY
TileJSON: `https://api.maptiler.com/tiles/105ba28a-afb8-4232-ac3d-0b40bf3fc76c/tiles.json?key=LsAKfag3t3bTv3H1zlTP`
Tile URL:  `https://api.maptiler.com/tiles/105ba28a-afb8-4232-ac3d-0b40bf3fc76c/{z}/{x}/{y}.pbf?key=…`

- Tileset name `Capaciteitskaart`, `minzoom 0`, `maxzoom 14`, bounds = NL
  `[3.358, 50.750, 7.227, 53.517]`. Content-Type `application/x-protobuf` (MVT).
- Because `minzoom` is 0, **the single tile `0/0/0.pbf` (~26 KB) contains every
  feature of every layer** — including each area's `id` and `color_code`. That one
  tile is enough to enumerate all area ids and read all congestion statuses.
- **The key `LsAKfag3t3bTv3H1zlTP` is Netbeheer's, embedded client-side. Under MapTiler
  ToS it may not be used as our own.** Treat tile access as a rare bootstrap, not a
  daily automated call. See §4 (Legal) and §5.2.

### 2.4 The current tileset URL is discoverable at runtime
`GET /capaciteitskaart/totaal/afname.data` → turbo-stream config containing
`CAPACITEITSKAART_TILES_URL` = the MapTiler tiles.json above. If Netbeheer republishes to
a new tileset id, read it from here rather than hard-coding. (Config only — not archived.)

### 2.5 `GET /api/manifests`  ← THE CHANGE-DETECTION ORACLE (cheapest, most important)
Returns dataset version + per-operator/per-category last-updated timestamps. One request.

- `dataUpdate`: `{ "executedOn": "2026-07-17T11:30:04Z", "id": "<uuid>" }` — the ingest
  pipeline run. **`id` (a UUID) changes on every republish → use it as the content
  fingerprint.**
- `gridOperatorUpdates[]`: one row per `(gridOperator × category)` with `updatedAt`
  (nullable ISO datetime, Europe/Amsterdam offset). Operators: **Liander, Enexis, Stedin,
  TenneT**. Categories (`categoryShort` → field it governs):
  - `ATC` Aanwezige transportcapaciteit → `existingTransportCapacity*`
  - `BTC` Benodigde transportcapaciteit → `requiredTransportCapacity*`
  - `WR`  Wachtrij → `queue*`, `uniqueRequests*`
  - `JC`  Jaartal congestie opgelost → `yearSolved*`
  - `KI`  Kleurinformatie → tile `color_code` (status)
  - `NU`  Netuitbreidingen → `projects[]`
- Live example (2026-07-28): Enexis 2026-07-15, Stedin 2026-06-25, Liander 2026-05-29,
  TenneT 2026-04-23 (TenneT `WR` 2026-07-01). → updates are **weekly-to-monthly per
  operator**, never daily. This is the empirical basis for event-driven fetching (§5).
- **Archive this every day** — it is tiny, and its own time-series ("when did each
  operator publish each category") is directly useful for the future slippage index.

### 2.6 `GET /api/status`  ← liveness/health
Returns `{"status":"OK"}` (schema `StatusApiModel`). Use as a pre-flight "is the API up"
check in fetch.py and in the weekly heartbeat. Not data.

### 2.7 Other endpoints in the spec (noted, mostly out of scope)
- `GET /api/download/{file}` — a download controller taking an opaque file name. Not
  referenced by the map bundle; candidate filenames probed did not resolve (throws/CORS).
  **Unexplored lead** — could be report/export files. Revisit only if a bulk export is
  wanted; not needed for the archive.
- `POST /api/green-gas/serviceArea/get` — a **parallel groen-gas (green gas) capacity
  map** exists with the same shape. Out of scope now; note for a possible sister archive.

### 2.8 Confirmed COMPLETE endpoint list (from `/api/v3/api-docs`, not guesswork)
The entire `/api` surface is exactly: `download/{file}`, `green-gas/serviceArea/get`,
`manifests`, `serviceArea/find`, `serviceArea/get`, `status`. **There is no bulk
"all areas" endpoint and no batch shape** — `serviceArea/get` strictly takes
`{"id": string}` (arrays/`{ids:[…]}`/GET/path-style all rejected: 400/405/404).
Area enumeration must therefore come from the vector tiles (§5.2).

### Vector tile layers (from TileJSON) and live feature counts (from `0/0/0.pbf`)

| tile layer (`id`)          | fields                          | features @ z0 | role                                  |
|----------------------------|---------------------------------|---------------|---------------------------------------|
| `rnb_afnamefgb`            | `RNB`, `color_code`, `provincie`| 52            | RNB withdrawal — coloured status polys |
| `rnb_opwekfgb`            | `RNB`, `color_code`, `provincie`| 46            | RNB injection — coloured status polys  |
| `rnb_gebied_afnamefgb`    | `RNB`, **`id`**, `provincie`    | **199**       | RNB withdrawal — area polys **with id** |
| `rnb_gebied_opwekfgb`     | `RNB`, **`id`**, `provincie`    | **205**       | RNB injection — area polys **with id**  |
| `tennet_afnamefgb`        | `color_code`                    | 4             | TenneT withdrawal status               |
| `tennet_opwekfgb`         | `color_code`                    | 4             | TenneT injection status                |
| `tennet_gebied_afnamefgb` | **`id`**                        | 17            | TenneT withdrawal areas **with id**    |
| `tennet_gebied_opwekfgb`  | **`id`**                        | 20            | TenneT injection areas **with id**     |
| `totaal_afnamefgb`        | `color_code`                    | 5             | Combined withdrawal status             |
| `totaal_opwekfgb`         | `color_code`                    | 5             | Combined injection status              |
| `missingfgb`              | `postcode`                      | 4             | Areas with no data yet ("grey")        |

→ **Unique service-area ids = 301** (measured: full decode of the `_gebied_` layers, then
set-union). Afname and opwek are *different* id sets (not a subset), so the union is larger
than either — the earlier ~225 estimate was wrong. `serviceArea/get` returns both directions
for one id, so a full sweep = **301 calls**.

**Id strings are NOT filesystem-safe.** RNB ids are station names with spaces
(`OS TEXEL 10-1i`, max length 34); several contain **slashes** (`CM34/46`, `CM29/64`,
`CM56/78`, `Groningen 220/20`). TenneT ids are region names (`Noord-Holland`, `Maasvlakte`).
→ One-file-per-area needs URL-encoding/hashing + a manifest; a single id-keyed blob avoids
the problem entirely (see §5, storage).

Congestion colour legend (`color_code` → meaning, from the app's Legenda):
`white` = capacity available, no queue · `yellow` = limited, no queue ·
`orange` = under investigation, with queue · `red` = shortage, with queue ·
`grey` = "colour added later" (missing data).

---

## 3. `servicearea/get` field dictionary (the crown jewel)

Verified against a live record (`id: "OS WESTZAANSTRAAT 10-1i"`, Liander). Numeric-looking
values arrive as **strings with units** (e.g. `"68 MW"`, `"9.2 MW"`, `"23"`, `"-"` for
n/a). **Store verbatim; parse in Phase 2.**

Top-level `serviceArea`:

| field                                  | example              | notes                                       |
|----------------------------------------|----------------------|---------------------------------------------|
| `id`, `name`                           | `OS WESTZAANSTRAAT 10-1i` | stable area/station id = the `id` in tiles |
| `rnb`                                   | `Liander`            | responsible regional operator               |
| `congestionUrl`                         | liander.nl/…         | operator's congestion-research page         |
| `bboxLeft/Right/Top/Bottom`             | 4.795 / 52.40 …      | area bounding box                           |
| `existingTransportCapacityWithdrawal`   | `68 MW`              | current available capacity, afname          |
| `existingTransportCapacityInjection`    | `93 MW`              | current available capacity, invoeding       |
| `requiredTransportCapacityWithdrawal`   | `64 MW`              | requested/required, afname                  |
| `requiredTransportCapacityInjection`    | `0 MW`               | requested/required, invoeding               |
| `queueWithdrawal` / `queueInjection`    | `9.2 MW` / `23 MW`   | **total MW in the wachtrij (queue)**        |
| `uniqueRequestsWithdrawal` / `…Injection` | `23` / `-`         | **# unique requests in wachtrij**           |
| `yearSolvedWithdrawal` / `…Injection`   | `2029` / `-`         | **RNB expected congestion-exit year** ⭐     |
| `tennetYearSolvedWithdrawal` / `…Injection` | `2036` / `-`     | **TenneT expected-exit year** ⭐             |
| `tennetWithdrawalMax` / `tennetInjectionMax` | `3` / `0`       | TenneT status codes (int)                   |
| `information`                           | `""`                 | free-text note (usually empty)              |
| `history`                               | `null`               | reserved                                    |
| `projects[]`                            | see below            | **planned expansions** ⭐⭐                   |

`projects[]` items (planned expansions / expected congestion relief — the Jan-2026 map
addition, and the seed of the future "slippage index"):

| field            | example                                   | notes                          |
|------------------|-------------------------------------------|--------------------------------|
| `id`             | `69696`                                    | numeric project id             |
| `name`           | `Extra capaciteit op knooppunt OS WESTZAANSTRAAT 10-1i` |                    |
| `gridOperator` / `gridOperatorType` | `Liander` / `RNB`; `TenneT` / `TENNET` |               |
| `dateString`     | `2029 - Q4`, `2026`, `2031 - 2033`         | human date range               |
| `year` / `quarter` | `2029` / `4`                             | parsed components              |
| `startDate` / `endDate` | `2029-01-01 00:00:00` / `2030-12-31 00:00:00` | often null            |
| `projectPhase`   | `scheduled` \| `inProgress` \| `approved`  | lifecycle phase                |
| `source`         | `Investeringsplan` \| `Laatste Inzichten`  | provenance                     |
| `scheduleDescription` | `Eerste inschatting` \| null          |                                |
| `description` / `projectUrl` | usually null                   |                                |

⭐ `yearSolved*` / `tennetYearSolved*` and the `projects[]` dates are exactly the
"expected_relief / planned_capacity" fields the Phase 2 change-report is built to track.

---

## 4. Legal

**Summary: no blocker. Proceed with courteous, identifiable, low-rate access to
Netbeheer's own endpoints. Keep the daily job off MapTiler.**

- **Publisher & purpose.** Netbeheer Nederland publishes the Capaciteitskaart from
  "openbare informatie … afkomstig uit investeringsplannen, congestierapporten"
  (public info from investment plans and congestion reports) for public insight.
- **Disclaimer (info page), quoted:** the map is compiled with care but
  *"geen garanties … voor de volledigheid, juistheid of actualiteit … U kunt hier geen
  rechten aan ontlenen."* i.e. an accuracy disclaimer only — **not** an access/reuse ban.
  The data is explicitly "een momentopname en … indicatief." → We must mirror this
  "indicative, no guarantees" framing in any future public output.
- **robots.txt:**
  - `data.partnersinenergie.nl/robots.txt` → HTTP **500** (SSR app throws; no file
    exists → nothing disallowed).
  - `www.netbeheernederland.nl/robots.txt` → standard Drupal file. Disallows
    `/admin/`, `/search/`, `/user/*`, `/media/`, `/file/` etc. **Does not** disallow the
    capaciteitskaart or any API path. Our targets are unrestricted.
- **No Terms-of-Service / gebruiksvoorwaarden** governing programmatic access were found
  on the map or its info page. (A site-wide legal/privacy page on netbeheernederland.nl
  should be re-checked before any *public relaunch* of the data, not before archiving.)
- **MapTiler (third-party tiles) — the one real constraint.** The embedded key
  `LsAKfag3t3bTv3H1zlTP` belongs to Netbeheer's MapTiler account. MapTiler ToS: credentials
  are non-transferable and "to be used by you as our Customer only"; no resale/redistribution;
  *"expressly prohibited to manipulate or modify map content … vectors, pixels or … metadata."*
  → **Do not build automated tile scraping into the daily cron using this key.** Tile access
  is limited to the rare id-enumeration bootstrap (§5.2); for anything recurring we either
  (a) enumerate ids via Netbeheer's own `find` API, or (b) obtain our own MapTiler account
  (note: their hosted tileset id is under *their* account, so our own key can't read it — so
  the realistic clean options are the checked-in id list + `find`, per §5.2).
- **Personal data:** none. Areas are grid stations, not persons.

---

## 5. Recommended snapshot strategy (manifest-driven, event-based)

The key realisation: **operators republish every few weeks, and `manifests` tells us
exactly when.** So the archiver is a cheap daily heartbeat that only triggers the
expensive per-area sweep on an actual change. This is both *more* raw-first-complete
(every change captured with its official date) and *far* gentler on the source than a
blind 301-request daily sweep — which matters because the #1 uptime threat is getting the
GitHub Actions IP rate-limited/challenged by Cloudflare (§5.5), and blind daily sweeps
maximise that exposure for near-zero information gain.

### 5.1 Daily job (~2 requests — always runs)
1. `GET /api/status` → confirm API is up (abort cleanly if not; heartbeat will alert).
2. `GET /api/manifests` → **archive verbatim** to `data/manifests.json` (canonicalised).
   This file's own history is a valuable time-series (operator publication cadence).
3. Compare `dataUpdate.id` (and the `gridOperatorUpdates[].updatedAt` set) against the
   last archived manifest.
   - **Unchanged** → done. Commit nothing (or just the unchanged-manifest no-op). ~2 req.
   - **Changed** → trigger the detail sweep (§5.2), ideally scoped to the operator(s)
     whose `updatedAt` advanced; a full sweep is the simplest correct default.

### 5.2 Detail sweep (~301 requests — runs only on change, + monthly backstop)
For each unique area id (from the checked-in id list, §5.3):
`POST /api/serviceArea/get {"id": …}` → collect the raw `serviceArea`. Sequential,
2 s spacing, 3-retry exponential backoff, identifiable UA. ~8–9 min, all on Netbeheer's
own API. Also run this **unconditionally once a month** as a raw-first safety net in case a
correction ever lands without moving a manifest timestamp.

**Storage — single id-keyed blob, split per operator.** Because ids are not
filesystem-safe (§2 tile note) and a sweep produces the whole set at once, write
`data/serviceareas/{liander,enexis,stedin,tennet}.json`, each a JSON object keyed by area
id, keys sorted, pretty-printed. Rationale: no filename-encoding hazard; per-operator files
bound each diff (and align with the per-operator update model — when only Enexis changes,
only `enexis.json` changes); a single area's parse issue can't corrupt siblings. (This
supersedes the brief's 6-fixed-file layout, which assumed whole-layer endpoints that don't
exist, and my own earlier per-area-file idea, which the slash-containing ids kill.)

### 5.3 Area-id enumeration (rare bootstrap / monthly refresh)
Maintain a checked-in `data/area_ids.json` (the 301 ids + each id's operator/province, so
the sweep and the per-operator split need no tile access). Rebuild it:
- **(A) One tile decode** — fetch `0/0/0.pbf` once, decode the `*_gebied_*` layers, union
  the `id` values (proven: 199 afname + 205 opwek RNB + 17/20 TenneT → 301 unique). Fast
  and complete, but touches Netbeheer's MapTiler key → keep it a **manual/monthly** step,
  never in the recurring cron.
- **(B) Postcode sweep via `find`** — ~4000 one-off `find` calls on Netbeheer's own API,
  deduped. ToS-cleanest, heavy. Fallback only.
Recommendation: bootstrap + monthly refresh via **(A)**; the id set is near-static, so new
ids mostly appear alongside a manifest change anyway (re-enumerate when the sweep sees an
id it doesn't recognise, or monthly, whichever first).

### 5.4 Congestion status (`color_code`)
Lives in the tiles (dissolved into 52/46 same-status regions), **not keyed to area id** —
the colour layers carry `color_code` with no `id`; the `_gebied_` layers carry `id` with no
`color_code`. So per-area status is not readable from tiles without a spatial join. Two
clean options, neither requiring a daily tile fetch:
- Derive per-area status in Phase 2 from `serviceArea/get` (queue/capacity fields), and
  **validate that rule once** via a spatial join against a bootstrap tile so our colours
  match the map's. (`color_code` domain observed: 0,1,2,3,null.)
- Capture the dissolved `color_code` regions during the monthly tile bootstrap as
  `data/status_from_tiles.json` for provenance.
Either way: **no MapTiler contact in the daily job.**

### 5.5 The real uptime risk: Cloudflare / bot-detection from GitHub Actions IPs
The API is Cloudflare-fronted (`cf-cache-status: DYNAMIC`, `cf-ray` headers). GitHub Actions
egresses from well-known datacenter ranges that Cloudflare may challenge/JS-gate regardless
of request rate. This — not rate — is the likeliest way the archiver silently dies. Mitigate:
identifiable UA; low, event-driven volume (§5.1 keeps most days at 2 requests); on the first
sweep from a real Actions runner, verify it isn't 403/challenged, and if it is, fall back to
a scheduled self-hosted/alternative runner or an allowlisted egress. Bake a hard "any 403 or
HTML-instead-of-JSON ⇒ fail loud + alert" check into fetch.py.

### 5.6 Volatile fields to strip before commit (for stable diffs)
No request-scoped fields seen inside `serviceArea` bodies. **Strip at the HTTP layer:** never
persist response headers (`cf-ray`, `x-tx-id`, `date`, `cf-cache-status`). For `manifests`,
note `dataUpdate.id` (UUID) and `executedOn` change on every republish **even if the actual
data is identical** — that's fine for detecting "they ran the pipeline," but the *authoritative*
"did data change" signal is the `gridOperatorUpdates[].updatedAt` set and the diff of the
swept `serviceArea` bodies. Canonicalise all JSON with sorted keys + pretty-print.

---

## 6. Open decisions for Jeremy (before Phase 1)
1. **Adopt manifest-driven / event-based fetching** (daily ~2-req heartbeat; 301-call sweep
   only on manifest change + monthly backstop) instead of a blind daily 301-call sweep? —
   recommended: **yes** (cheaper, gentler, lower block-risk, still captures every change).
2. **Storage layout:** per-operator id-keyed blobs (`data/serviceareas/{operator}.json`)
   + `data/manifests.json`. — recommended: **yes** (ids aren't filename-safe, so per-area
   files are out).
3. **Id-enumeration method:** (A) monthly tile decode vs (B) postcode sweep. — recommended:
   **(A)** manual/monthly.
4. **User-Agent contact address** for `gridwatch-nl archiver (contact: …)`. — on file:
   `jeremy-graft@users.noreply.github.com` (confirm/replace).
5. **Cron cadence:** keep daily 06:00 (cheap heartbeat + precise change-date capture)? —
   recommended: **yes**. Daily is what makes the change *timestamp* precise even though the
   heavy work is rare.

---

## 7. Reproduction notes (how these findings were obtained)
- Loaded the live app in a browser, captured network + decoded client JS bundles
  (`page-*.js`, `capacity-map-layer-titles-*.js`) to recover the API call shapes and enums.
- Verified every endpoint returns real data (live `find`→`get` round-trip; live TileJSON;
  live `0/0/0.pbf` decoded with a hand-rolled MVT feature counter).
- Confirmed absent endpoints return 404 and robots/ToS as quoted above.
- No writes, no forms, no authentication, read-only throughout.
