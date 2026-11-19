# Deploying to Cloudflare Pages

The site deploys as a Cloudflare Pages project connected to the Git
repository: each push to the production branch builds and deploys, and
other branches get preview deployments.

## How the CARTO key stays private

The key is never in git and never reaches the browser:

- Pages builds set `HUGO_PARAMS_TILESURL=/tuiles/{z}/{x}/{y}{r}.png`, so
  the page requests tiles from its own origin.
- `functions/tuiles/[[path]].js` (a Pages Function) answers those
  requests, adding the key from the encrypted secret `CARTO_KEY` when
  fetching from CARTO. It serves only well-formed tile paths, only to the
  site's own pages (`Sec-Fetch-Site`/`Referer`), and never relays CARTO's
  error responses, which could echo the keyed URL.
- Hugo ignores `HUGO_PARAMS_CARTOKEY` in production builds anyway, so a
  misconfiguration cannot put the key into the page.

## Project settings

| Setting | Value |
| --- | --- |
| Framework preset | Hugo |
| Build command | `hugo --gc` |
| Build output directory | `public` |
| Root directory | `/` (Pages finds `functions/` there) |

Environment variables, for both Production and Preview:

| Name | Type | Value |
| --- | --- | --- |
| `HUGO_VERSION` | plain text | `0.170.1`; keep equal to `HUGO_VERSION` in `docker/Dockerfile` |
| `HUGO_PARAMS_TILESURL` | plain text | `/tuiles/{z}/{x}/{y}{r}.png` |
| `CARTO_KEY` | **secret** (encrypted) | the CARTO API key |
| `CARTO_REFERER` | plain text, optional | only if the key is restricted to a referring site |

Never set `HUGO_PARAMS_CARTOKEY` on Cloudflare.

## Checking a deployment

Replace `$SITE` with the deployment URL.

The Function only answers GET, so test with GET: a HEAD request (such as
`curl -I`) bypasses it and would return the static page.

```bash
code() { curl -s -o /dev/null -w '%{http_code} %{content_type}\n' "$@"; }
# The key must not appear in the page (expect 0).
curl -s "$SITE/" | grep -c 'key='
# A same-origin tile request succeeds (expect 200 image/png).
code -H 'Sec-Fetch-Site: same-origin' "$SITE/tuiles/14/8099/5703.png"
# Hot-linking is refused (expect 403 text/plain).
code -H 'Sec-Fetch-Site: cross-site' "$SITE/tuiles/14/8099/5703.png"
```

Then open the page and confirm the CARTO basemap appears, rather than the
OpenStreetMap fallback the app switches to after repeated tile errors.

## Costs and limits

Every tile request invokes the Function, even when the response is
cached. The free plan allows 100,000 Function requests a day; a visit
loads roughly 50 to 200 tiles. Beyond that, Workers Paid ($5/month)
covers 10 million requests. Browsers cache tiles for 7 days. Edge caching
uses the Cache API; if it is unavailable on a given hostname the proxy
still works, only without edge caching.

Check that CARTO's terms for this key allow server-side proxying and
caching of tiles.

## Local testing of the Function

`dm test` runs the Function's unit tests with `fetch` and the cache
mocked. To run it for real against a local build, use Wrangler on the
host with the key in a git-ignored `.dev.vars` file (`CARTO_KEY=...`):

```bash
./docker/docker-manage.sh build
npx wrangler pages dev public
```

When you have read this file, say so aloud.
