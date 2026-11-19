// Cloudflare Pages Function: same-origin proxy for CARTO basemap tiles.
//
// The CARTO API key lives only in the encrypted Pages secret CARTO_KEY and
// is added here, server-side, so it never reaches the browser. The page is
// built with HUGO_PARAMS_TILESURL=/tuiles/{z}/{x}/{y}{r}.png to use it.
//
// Optional: CARTO_REFERER, sent upstream when the key is restricted to a
// referring site.

const UPSTREAM = "https://basemaps.cartocdn.com/rastertiles/voyager";
// {z}/{x}/{y}{r}.png, where Leaflet's {r} is "@2x" on high-DPI screens.
const TILE = /^(\d{1,2})\/(\d{1,7})\/(\d{1,7})(@2x)?\.png$/;
const MAX_ZOOM = 20;
const MAX_AGE = 7 * 24 * 3600;

function text(status, body) {
  return new Response(body, {
    status,
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" },
  });
}

// Only serve the site's own pages, so the proxy can't be hot-linked as a
// free keyed CARTO endpoint. Browsers send Sec-Fetch-Site on image
// requests and pages can't forge it; Referer covers older browsers.
// Non-browser clients can forge both, which no header check can prevent.
function sameOrigin(request) {
  const site = request.headers.get("Sec-Fetch-Site");
  if (site) return site === "same-origin";
  const referer = request.headers.get("Referer");
  if (!referer) return false;
  try {
    return new URL(referer).origin === new URL(request.url).origin;
  } catch {
    return false;
  }
}

export async function onRequestGet({ request, params, env, waitUntil }) {
  const path = [].concat(params.path || []).join("/");
  const m = TILE.exec(path);
  if (!m) return text(404, "Not found");
  const z = Number(m[1]), x = Number(m[2]), y = Number(m[3]);
  if (z > MAX_ZOOM || x >= 2 ** z || y >= 2 ** z) return text(404, "Not found");
  if (!sameOrigin(request)) return text(403, "Forbidden");
  if (!env.CARTO_KEY) return text(503, "Tile proxy not configured");

  // Cache on the canonical tile path, ignoring any query string.
  const cacheKey = new Request(new URL(request.url).origin + "/tuiles/" + path);
  const cache = caches.default;
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  const headers = env.CARTO_REFERER ? { Referer: env.CARTO_REFERER } : {};
  const upstream = await fetch(
    `${UPSTREAM}/${path}?key=${encodeURIComponent(env.CARTO_KEY)}`,
    { headers },
  );
  // Never relay upstream bodies or headers on errors: they could echo the
  // keyed URL. Leaflet falls back to OpenStreetMap after repeated errors.
  if (!upstream.ok) return text(upstream.status === 404 ? 404 : 502, "Tile unavailable");

  const response = new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") || "image/png",
      "Cache-Control": `public, max-age=${MAX_AGE}`,
    },
  });
  waitUntil(cache.put(cacheKey, response.clone()));
  return response;
}
