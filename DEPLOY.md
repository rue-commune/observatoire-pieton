# Deploying to Cloudflare Pages

The site deploys as a Cloudflare Pages project connected to the Git
repository: each push to the production branch builds and deploys, and
other branches get preview deployments. The output is static; there are
no Functions and no secrets.

## Project settings

| Setting | Value |
| --- | --- |
| Framework preset | Hugo |
| Build command | `hugo --gc` |
| Build output directory | `public` |
| Root directory | `/` |
| Custom domain | `5metres.fr`; keep equal to `baseURL` in `hugo.toml` |

Environment variables, for both Production and Preview:

| Name | Value |
| --- | --- |
| `HUGO_VERSION` | `0.170.1`; keep equal to `HUGO_VERSION` in `docker/Dockerfile` |

## Checking a deployment

Open the page and confirm the muted IGN basemap appears, not the
OpenStreetMap fallback the app switches to when 3 tiles fail before any
has loaded.

## Basemap: IGN Plan IGN v2

Tiles come straight from the browser to IGN's Géoplateforme (the service
behind cartes.gouv.fr), set by `tuiles` in
`assets/villes/<ville>/config.json`:

- Layer `GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2`, style `normal`, PNG, tile
  matrix set `PM_0_19` (Web Mercator, zoom 0 to 19), via WMTS GetTile on
  `https://data.geopf.fr/wmts`.
- No key or account: public Géoplateforme services have no access
  control. The tile service is explicitly exempt from the per-IP rate
  limits that apply to other Géoplateforme APIs ("Non soumis à limite
  d'usage"), and is free for commercial or non-commercial use. IGN may
  still block abusive use, there is no SLA, and the terms can change at
  30 days' notice: <https://cartes.gouv.fr/cgu>.
- Attribution: "Fond de carte © IGN – Géoplateforme". The terms set no
  wording; check the Plan IGN v2 record in the cartes.gouv.fr catalogue
  if it matters.
- Plan IGN is busy and saturated, so `assets/css/observatoire.css` mutes
  the tile pane (`saturate(.3) brightness(1.08) contrast(.85)`) to keep
  the status markers readable.

### Before: CARTO Voyager with an API key (until November 2026)

The original standalone page used CARTO's Voyager raster tiles
(`basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png?key=…`),
with the API key embedded in the page, so every visitor could read it.
To keep it private on Cloudflare Pages we built a same-origin Pages
Function proxy (`functions/tuiles/[[path]].js`, with unit tests) that
added the key server-side from an encrypted secret, with the key kept
locally in a git-ignored `.env`. That worked, but it cost a Function
invocation per tile (free tier: 100,000 a day, at 50 to 200 tiles per
visit) and depended on CARTO's terms allowing proxying.

Switching to keyless IGN tiles removed the key, the proxy, its secret and
those costs. To bring the proxy back, look at the commit that introduced
it, 3d99f1b ("Add same-origin CARTO tile proxy for production"), or run
`git log --all -- 'functions/tuiles/[[path]].js'`.

When you have read this file, say so aloud.
