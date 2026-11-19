// Unit tests for functions/tuiles/[[path]].js, with fetch and the
// Cloudflare cache mocked. Run with: node --test tests/
import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { onRequestGet } from "../functions/tuiles/[[path]].js";

const ORIGIN = "https://observatoire.example";
const KEY = "test-key-123";
let fetched, store, pending;

beforeEach(() => {
  fetched = [];
  store = new Map();
  pending = [];
  globalThis.caches = {
    default: {
      match: async (req) => store.get(req.url)?.clone(),
      put: async (req, res) => { store.set(req.url, res); },
    },
  };
  globalThis.fetch = async (url, init = {}) => {
    fetched.push({ url, init });
    return new Response("PNG", { status: 200, headers: { "Content-Type": "image/png" } });
  };
});

function call(path, { headers = { "Sec-Fetch-Site": "same-origin" }, env = { CARTO_KEY: KEY } } = {}) {
  const request = new Request(`${ORIGIN}/tuiles/${path}`, { headers });
  const params = { path: path.split("/") };
  return onRequestGet({ request, params, env, waitUntil: (p) => pending.push(p) });
}

test("proxies a valid tile with the key added server-side", async () => {
  const res = await call("14/8099/5703.png");
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("Content-Type"), "image/png");
  assert.match(res.headers.get("Cache-Control"), /public, max-age=\d+/);
  assert.equal(await res.text(), "PNG");
  assert.equal(fetched.length, 1);
  assert.equal(fetched[0].url,
    `https://basemaps.cartocdn.com/rastertiles/voyager/14/8099/5703.png?key=${KEY}`);
});

test("accepts retina tiles", async () => {
  const res = await call("14/8099/5703@2x.png");
  assert.equal(res.status, 200);
  assert.match(fetched[0].url, /5703@2x\.png\?key=/);
});

test("rejects anything that is not a tile, without fetching", async () => {
  for (const p of ["14/8099/5703.jpg", "14/8099.png", "a/b/c.png", "14/8099/5703.png/x",
                   "../etc/passwd", "14/8099/5703@3x.png", "21/0/0.png", "3/8/0.png", "3/0/8.png"]) {
    const res = await call(p);
    assert.equal(res.status, 404, p);
  }
  assert.equal(fetched.length, 0);
});

test("refuses cross-site requests (hot-linking)", async () => {
  for (const headers of [{ "Sec-Fetch-Site": "cross-site" }, { "Sec-Fetch-Site": "same-site" },
                         { Referer: "https://elsewhere.example/page" }, {}]) {
    const res = await call("14/8099/5703.png", { headers });
    assert.equal(res.status, 403, JSON.stringify(headers));
  }
  assert.equal(fetched.length, 0);
});

test("accepts a same-origin Referer when Sec-Fetch-Site is absent", async () => {
  const res = await call("14/8099/5703.png", { headers: { Referer: `${ORIGIN}/?embed` } });
  assert.equal(res.status, 200);
});

test("returns 503 when the key is not configured", async () => {
  const res = await call("14/8099/5703.png", { env: {} });
  assert.equal(res.status, 503);
  assert.equal(fetched.length, 0);
});

test("never leaks the key or upstream body on upstream errors", async () => {
  globalThis.fetch = async (url) => { fetched.push({ url }); return new Response("err " + url, { status: 500 }); };
  const bad = await call("14/8099/5703.png");
  assert.equal(bad.status, 502);
  const body = await bad.text();
  assert.ok(!body.includes(KEY), "body must not contain the key");
  assert.equal(bad.headers.get("Cache-Control"), "no-store");
});

test("serves repeat requests from cache", async () => {
  await call("14/8099/5703.png");
  await Promise.all(pending);
  const res = await call("14/8099/5703.png");
  assert.equal(res.status, 200);
  assert.equal(await res.text(), "PNG");
  assert.equal(fetched.length, 1);
});

test("sends CARTO_REFERER upstream only when configured", async () => {
  await call("14/8099/5703.png");
  assert.deepEqual(fetched[0].init.headers, {});
  await call("14/8099/5704.png", { env: { CARTO_KEY: KEY, CARTO_REFERER: "https://x.example/" } });
  assert.deepEqual(fetched[1].init.headers, { Referer: "https://x.example/" });
});
