(function () {
  "use strict";
  var C = window.CITY_CONFIG, D = window.CITY_DATA;

  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  var fmt = new Intl.NumberFormat("fr-FR");
  var fmt1 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
  function fmtPct(v) { return fmt1.format(v) + " %"; }
  var fmtDate = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric" });
  function pd(s) { var m = String(s || "").match(/^(\d{4})-(\d{2})-(\d{2})/); return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null; }
  function norm(s) { return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[-']/g, " ").replace(/\s+/g, " ").trim(); }
  function slug(s) { return norm(s).replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }

  /* ---------- Habillage ---------- */
  var AREA = C.territoire, UNIT = C.unite || { one: "commune", many: "communes", the: "la commune" };
  $("k-title").textContent = "Conformité à la loi, " + AREA;
  $("rank-title").textContent = "Classement des " + UNIT.many;
  $("pl-reset").textContent = "Revenir à " + C.territoireCourt;
  $("cat-1-sub").textContent = C.voituresDetail || "payant, gratuit, réservé…";
  var snap = "Photographie au " + fmtDate.format(pd(D.generated)) + ", d'après les données ouvertes publiées par " + C.producteur + ".";
  $("k-snap").textContent = snap;
  $("exp-note").textContent = "Le fichier contient les passages affichés sur la carte : choisissez d'abord " + (UNIT.fem ? "une " : "un ") + UNIT.one + " ou un quartier, et les statuts à vérifier dans la légende. Pour chaque passage : " + (D.streets ? "rue traversée, carrefour ou rues encadrantes, " : "") + UNIT.one + ", quartier, statut, places en cause, coordonnées, lien vers sa fiche et vers Street View. Le GeoJSON s'ouvre dans uMap, QGIS, geojson.io ou les applications de terrain ; le CSV, dans un tableur, avec des colonnes vides pour noter les constats.";

  /* ---------- Données ---------- */
  var COMS = D.communes, QS = D.quartiers, LABELS = D.labels, TYPES = D.types || [];
  var ROWS = D.rows.map(function (r, i) { return { i: i, lat: r[0], lon: r[1], c: r[2], q: r[3], up: r[4], down: r[5], items: r[6], type: r[7], flags: r[8] || 0, road: r[9] || 0 }; });
  var STREETS = D.streets || [];
  var GENRE = { rue: "f", avenue: "v", boulevard: "m", place: "f", quai: "m", passage: "m", impasse: "v", allée: "v", square: "m", villa: "f", cité: "f", chemin: "m", cour: "f", sentier: "m", voie: "f",
    port: "m", pont: "m", "rond-point": "m", carrefour: "m", esplanade: "v", parvis: "m", galerie: "f", hameau: "m", promenade: "f", route: "f", porte: "f", cours: "m", mail: "m", rampe: "f",
    ruelle: "f", venelle: "f", côte: "f", levée: "f", faubourg: "m", lotissement: "m", résidence: "f", traverse: "f", contour: "m", giratoire: "m", tenue: "f", boucle: "f", clos: "m"};
  function lc(s) { var w = String(s).split(/[\s]/)[0].toLowerCase(); return GENRE[w] ? s.charAt(0).toLowerCase() + s.slice(1) : s; }
  function art(s) { var w = String(s).split(/\s/)[0].toLowerCase(), g = GENRE[w]; return g === "f" ? "la " + lc(s) : g === "m" ? "le " + lc(s) : g === "v" ? "l'" + lc(s) : s; }
  function de(s) { var a = art(s); return /^le /.test(a) ? "du " + a.slice(3) : "de " + a; }
  ROWS.forEach(function (r) { var s = D.st ? D.st[r.i] : null; r.street = s && s[0] > -1 ? STREETS[s[0]] : ""; r.angle = s && s[1] > -1 ? STREETS[s[1]] : ""; r.entre = s && s[2] > -1 && s[3] > -1 ? art(STREETS[s[2]]) + " et " + art(STREETS[s[3]]) : ""; });
  function posTxt(r) { return r.angle ? "à l'angle " + de(r.angle) : r.entre ? "entre " + r.entre : ""; }
  function lieuTxt(r) { var a = r.street || "", p = posTxt(r); return a + (p ? (a ? ", " : "") + p : ""); }
  var CATNAME = { 1: "Voitures", 2: "Livraisons", 4: "Deux-roues motorisés", 8: "GIG-GIC" };
  var TYPE_LABEL = C.typesMarquage || {};
  var state = { cats: 15, show: { ok: true, mid: true, ko: true }, c: null, q: null, rankMode: "pct" };
  function dataStatus(r) { return (r.up & state.cats) ? "ko" : (r.down & state.cats) ? "mid" : "ok"; }
  function fullStatus(r) { return (r.up & 15) ? "ko" : (r.down & 15) ? "mid" : "ok"; }
  function hiddenByFilter(r) { return state.cats !== 15 && dataStatus(r) !== fullStatus(r); }
  var STATUS_LABEL = { ko: "Non conforme", mid: "Conforme à l'obligation réglementaire", ok: "Conforme à la recommandation complète" };
  function comName(i) { return COMS[i] || ""; }
  function qName(i) { return i > -1 && QS[i] ? QS[i].n : ""; }
  function placeLabel(r) { return (r.q > -1 ? qName(r.q) + ", " : "") + comName(r.c); }

  /* ---------- Carte ---------- */
  var b = L.geoJSON(D.geo).getBounds();
  var map = L.map("map", { minZoom: 9, maxZoom: 20, maxBounds: b.pad(0.3), preferCanvas: true });
  var base = L.tileLayer(C.tuiles, { attribution: C.attribution, maxNativeZoom: 18, maxZoom: 20 }).addTo(map);
  // fond de carte de secours (OpenStreetMap) si les tuiles IGN sont refusées
  var tileErr = 0, tileOk = false;
  base.on("tileload", function () { tileOk = true; });
  base.on("tileerror", function () { if (!tileOk && ++tileErr === 3) base.setUrl("https://tile.openstreetmap.org/{z}/{x}/{y}.png"); });
  map.createPane("points").style.zIndex = 450;
  var renderer = L.canvas({ padding: 0.3, pane: "points" });
  var POINT_ZOOM = C.pointZoom || 14;
  var css = getComputedStyle(document.documentElement);
  var COL = { ok: css.getPropertyValue("--ok").trim(), mid: css.getPropertyValue("--mid").trim(), ko: css.getPropertyValue("--ko").trim() };
  var RAMP = ["--r0", "--r1", "--r2", "--r3", "--r4", "--r5"].map(function (v) { return css.getPropertyValue(v).trim(); });
  function hex2rgb(h) { h = h.replace("#", ""); return [0, 2, 4].map(function (i) { return parseInt(h.substr(i, 2), 16); }); }
  var CMAX = C.choroMax || 0.5;   // part de non-conformité à partir de laquelle le rouge est le plus foncé
  function rampColor(t) {
    t = Math.max(0, Math.min(1, t / CMAX)) * (RAMP.length - 1);
    var i = Math.min(RAMP.length - 2, Math.floor(t)), f = t - i, a = hex2rgb(RAMP[i]), c = hex2rgb(RAMP[i + 1]);
    return "rgb(" + a.map(function (v, k) { return Math.round(v + (c[k] - v) * f); }).join(",") + ")";
  }

  $("choro-ends").innerHTML = [1 - CMAX, 1 - CMAX / 2, 1].map(function (v) { return "<span>" + Math.round(v * 100) + " %</span>"; }).join("");
  var pointsLayer = L.layerGroup();
  ROWS.forEach(function (r) {
    r.m = L.circleMarker([r.lat, r.lon], { renderer: renderer, radius: 4, weight: 1, color: "#fff", fillOpacity: 1 });
    r.m.on("click", function () { openRow(r); });
  });
  function styleRow(r) {
    r.st = dataStatus(r);
    r.m.setStyle(r.st === "ko" ? { radius: 4.6, fillColor: COL.ko, color: "#fff", weight: 1 } : r.st === "mid" ? { radius: 4.2, fillColor: COL.mid, color: "#fff", weight: 1 }
      : { radius: 3.8, fillColor: COL.ok, color: "#fff", weight: 0.8 });
  }

  var comLayer = L.geoJSON(D.geo, { style: function () { return { weight: 1, color: "#fff", fillOpacity: .75 }; },
    onEachFeature: function (f, l) { l.on("click", function () { selectCommune(f.properties.i, false); }); } }).addTo(map);
  var labelLayer = L.layerGroup().addTo(map);

  function stats(filter) {
    var s = { n: 0, ok: 0, mid: 0, ko: 0 };
    ROWS.forEach(function (r) { if (!filter(r)) return; s.n++; s[fullStatus(r)]++; });
    s.law = s.n ? (s.ok + s.mid) / s.n * 100 : 0; s.reco = s.n ? s.ok / s.n * 100 : 0;
    return s;
  }
  var BYCOM = COMS.map(function (_, i) { return stats(function (r) { return r.c === i; }); });
  var BYQ = QS.map(function (_, i) { return stats(function (r) { return r.q === i; }); });
  var ALL = stats(function () { return true; });

  function drawChoro() {
    labelLayer.clearLayers();
    comLayer.eachLayer(function (l) {
      var i = l.feature.properties.i, s = BYCOM[i], sel = state.c === i;
      var pts = map.getZoom() >= POINT_ZOOM;
      l.setStyle({ fillColor: rampColor(s.n ? s.ko / s.n : 0), fillOpacity: pts ? 0 : (state.c !== null && !sel ? .35 : .75), weight: sel ? 3 : 1, color: sel ? "#161614" : "#fff" });
      l.unbindTooltip(); if (!pts) l.bindTooltip(esc(COMS[i]) + " : " + fmtPct(s.law) + " conformes à la loi (" + fmt.format(s.n) + " passages)", { sticky: true });
      if (!pts && map.getZoom() >= (C.labelZoom || 11)) {
        var c = l.getBounds().getCenter();
        labelLayer.addLayer(L.marker(c, { interactive: false, icon: L.divIcon({ className: "com-label", html: esc(COMS[i]) + "<small>" + Math.round(s.law) + " %</small>", iconSize: [120, 28], iconAnchor: [60, 14] }) }));
      }
    });
  }
  function updateZoomMode() {
    var pts = map.getZoom() >= POINT_ZOOM;
    if (pts && !map.hasLayer(pointsLayer)) pointsLayer.addTo(map);
    if (!pts && map.hasLayer(pointsLayer)) map.removeLayer(pointsLayer);
    $("zoom-hint").hidden = pts; $("choro-legend").hidden = pts;
    drawChoro();
  }
  map.on("zoomend", updateZoomMode);

  function inScope(r) { return (state.c === null || r.c === state.c) && (state.q === null || r.q === state.q); }
  function shownRows() { return ROWS.filter(function (r) { return state.show[r.st] && !hiddenByFilter(r) && inScope(r); }); }
  function drawPoints() {
    pointsLayer.clearLayers();
    ROWS.forEach(function (r) { if (state.show[r.st] && !hiddenByFilter(r) && inScope(r)) pointsLayer.addLayer(r.m); });
    updateExport();
  }

  /* ---------- Indicateurs ---------- */
  function seg(cls, n, tot, lab) { return n ? '<span class="' + cls + '" style="flex:' + n + '" data-tip="' + esc(lab + " : " + fmt.format(n) + " (" + fmtPct(n / tot * 100) + ")") + '"></span>' : ""; }
  function drawKpi() {
    var s = ALL;
    $("k-pct").textContent = Math.round(s.law) + " %";
    $("k-label").textContent = fmt.format(s.ok + s.mid) + " passages sur " + fmt.format(s.n) + " sont conformes à la loi ; " + fmt.format(s.ko) + " ne le sont pas.";
    $("k-bar").innerHTML = seg("ko", s.ko, s.n, STATUS_LABEL.ko) + seg("mid", s.mid, s.n, STATUS_LABEL.mid) + seg("ok", s.ok, s.n, STATUS_LABEL.ok);
    $("k-bar").setAttribute("aria-label", fmtPct(s.law) + " conformes à la loi");
    $("k-reco").innerHTML = "Conformes à la recommandation complète : <strong>" + fmtPct(s.reco) + "</strong>";
    var cnt = { ok: 0, mid: 0, ko: 0 }; ROWS.forEach(function (r) { if (!hiddenByFilter(r)) cnt[r.st]++; });
    ["ok", "mid", "ko"].forEach(function (k) { $("c-" + k).textContent = fmt.format(cnt[k]); });
    var end = pd(C.echeance || "2026-12-31"), today = new Date(); today.setHours(0, 0, 0, 0);
    var days = Math.round((end - today) / 86400000);
    $("k-countdown").innerHTML = days > 0 ? "Échéance légale : <strong>" + fmtDate.format(end) + "</strong>, dans <strong>" + fmt.format(days) + " jours</strong>."
      : "L'échéance légale du <strong>" + fmtDate.format(end) + "</strong> est dépassée.";
  }
  function drawRank() {
    var idx = COMS.map(function (_, i) { return i; }).filter(function (i) { return BYCOM[i].n > 0; });
    if (state.rankMode === "n") idx.sort(function (a, b) { return BYCOM[b].ko - BYCOM[a].ko; });
    else idx.sort(function (a, b) { return BYCOM[a].law - BYCOM[b].law; });
    $("rank").innerHTML = idx.map(function (i) {
      var s = BYCOM[i];
      return '<li><button type="button" data-c="' + i + '" aria-pressed="' + (state.c === i) + '"><span class="a">' + esc(COMS[i]) + ' <small>' + fmt.format(s.n) + '</small></span><span class="track">' +
        seg("seg ko", s.ko, s.n, STATUS_LABEL.ko) + seg("seg mid", s.mid, s.n, STATUS_LABEL.mid) + seg("seg ok", s.ok, s.n, STATUS_LABEL.ok) + '</span><span class="v">' +
        (state.rankMode === "n" ? fmt.format(s.ko) : Math.round(s.law) + " %") + "</span></button></li>";
    }).join("");
    $("rank-note").textContent = state.rankMode === "n"
      ? "Du plus grand au plus petit nombre de passages non conformes. Cliquez sur " + UNIT.the + " pour zoomer et afficher ses places à supprimer et ses quartiers."
      : "Du moins conforme au plus conforme à la loi (pourcentage affiché : passages conformes à la loi, verts et orange ; à côté du nom, le nombre de passages). Cliquez sur " + UNIT.the + " pour zoomer et afficher ses places à supprimer et ses quartiers.";
    // quartiers de la commune choisie
    var qs = state.c === null ? [] : QS.map(function (q, i) { return i; }).filter(function (i) { return QS[i].c === state.c && BYQ[i].n > 0; });
    $("qsel").hidden = !qs.length;
    if (qs.length) {
      qs.sort(function (a, b) { return QS[a].n.localeCompare(QS[b].n, "fr"); });
      $("q-select").innerHTML = '<option value="">Tous les quartiers (' + qs.length + ")</option>" + qs.map(function (i) { return '<option value="' + i + '"' + (state.q === i ? " selected" : "") + ">" + esc(QS[i].n) + "</option>"; }).join("");
      var qsc = $("q-score");
      if (state.q !== null) {
        var s = BYQ[state.q];
        qsc.hidden = false;
        qsc.innerHTML = '<span class="big">' + Math.round(s.law) + ' %</span>des passages conformes à la loi<div class="track">' + seg("seg ko", s.ko, s.n, STATUS_LABEL.ko) + seg("seg mid", s.mid, s.n, STATUS_LABEL.mid) + seg("seg ok", s.ok, s.n, STATUS_LABEL.ok) +
          '</div><div class="meta">' + fmt.format(s.n) + " passages : " + fmt.format(s.ko) + " non conformes, " + fmt.format(s.mid) + " conformes à la loi seulement, " + fmt.format(s.ok) + " conformes à la recommandation.</div>";
      } else qsc.hidden = true;
    }
  }
  function drawPlaces() {
    var src, scope;
    if (state.q !== null) { src = [D.removal.q[state.q] || {}]; scope = "Quartier " + qName(state.q) + " (" + comName(state.c) + ")"; }
    else if (state.c !== null) { src = [D.removal.c[state.c] || {}]; scope = comName(state.c); }
    else { src = Object.keys(D.removal.c).map(function (k) { return D.removal.c[k]; }); scope = C.territoireMaj; }
    var tot = { 1: [0, 0], 2: [0, 0], 4: [0, 0], 8: [0, 0] };
    src.forEach(function (o) { Object.keys(o).forEach(function (k) { if (tot[k]) { tot[k][0] += o[k][0]; tot[k][1] += o[k][1]; } }); });
    var leg = 0, rec = 0; Object.keys(tot).forEach(function (k) { leg += tot[k][0]; rec += tot[k][1]; $("c-cat-" + k).textContent = fmt.format(tot[k][0]); });
    $("pl-scope").textContent = scope; $("pl-reset").hidden = state.c === null;
    $("pl-total").textContent = fmt.format(leg);
    $("pl-label").textContent = "à supprimer pour respecter la loi (côté amont), " + fmt.format(rec) + " pour la recommandation complète (des deux côtés).";
  }
  function refresh() { ROWS.forEach(styleRow); drawKpi(); drawRank(); drawPlaces(); drawPoints(); drawChoro(); }

  /* ---------- Fiche d'un passage ---------- */
  var openedPop = null;
  function svUrl(r) { return "https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=" + r.lat + "," + r.lon; }
  function placesTxt(r) { return r.items.filter(function (it) { return it[0] & 15; }).map(function (it) { return LABELS[it[1]] + " : " + it[2] + " (" + (it[3] === 1 ? "amont" : "aval") + ")"; }).join(" ; "); }
  function placesOf(r, side) { return r.items.filter(function (it) { return (it[0] & 15) && it[3] === side; }).reduce(function (a, it) { return a + it[2]; }, 0); }
  function openRow(r, keepView) {
    var st = r.st, pos = posTxt(r);
    var h = '<div class="pop"><h3>' + esc(r.street || "Passage piéton") + '</h3><div class="where">' + (pos ? esc(pos.charAt(0).toUpperCase() + pos.slice(1)) + "<br>" : "") + esc(placeLabel(r)) + '<span class="addr"></span></div>' +
      '<span class="badge"><span class="dot ' + st + '"></span>' + esc(STATUS_LABEL[st]) + "</span>";
    var up = r.items.filter(function (it) { return it[3] === 1 && (it[0] & 15); }), dn = r.items.filter(function (it) { return it[3] === 2 && (it[0] & 15); });
    function lst(a) { return "<ul>" + a.map(function (it) { return "<li>" + esc(LABELS[it[1]]) + " : " + it[2] + " place" + (it[2] > 1 ? "s" : "") + "</li>"; }).join("") + "</ul>"; }
    if (up.length) h += "<div><strong>Dans les 5 m côté amont</strong>" + lst(up) + "</div>";
    if (dn.length) h += '<div style="margin-top:4px"><strong>Dans les 5 m côté aval</strong>' + lst(dn) + "</div>";
    if (!up.length && !dn.length) h += "<div>Aucun emplacement de stationnement dans les 5 m.</div>";
    var meta = [];
    if (r.type > -1 && TYPES[r.type]) meta.push((C.typeTitre === undefined ? "Marquage : " : C.typeTitre) + esc(TYPE_LABEL[TYPES[r.type]] || TYPES[r.type].toLowerCase()));
    if (C.attributsPassage) { if (r.flags & 1) meta.push("bandes d'éveil de vigilance"); else if (!C.attributsPositifs) meta.push("sans bandes d'éveil de vigilance"); if (r.flags & 2) meta.push("îlot refuge"); }
    if (meta.length) h += '<div class="meta">' + meta.join(" · ") + "</div>";
    if (r.road === 2) h += '<div class="meta">Rue à sens unique sans double-sens cyclable : tout le côté d\'où arrivent les voitures est obligatoire.</div>';
    if (r.road === 1) h += '<div class="meta">Rue à sens unique avec double-sens cyclable : le côté d\'arrivée des vélos compte aussi.</div>';
    h += '<div class="links"><a href="' + svUrl(r) + '" target="_blank" rel="noopener">Voir sur Street View</a><a href="#" class="copy-link">Copier le lien de cette fiche</a></div></div>';
    if (!keepView && map.getZoom() < 17) map.setView([r.lat, r.lon], 18);
    var pop = openedPop = L.popup({ maxWidth: 300 }).setLatLng([r.lat, r.lon]).setContent(h).openOn(map);
    var el = pop.getElement();
    if (el) el.querySelector(".copy-link").addEventListener("click", function (e) {
      e.preventDefault(); var a = e.target, url = ficheUrl(r);
      (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(function () { a.textContent = "Lien copié"; }, function () { window.prompt("Lien de la fiche :", url); });
    });
    nearestAddress(r, function (txt) { var e2 = pop.getElement(); if (e2 && txt) e2.querySelector(".addr").textContent = " · près du " + txt; });
    try { history.replaceState(null, "", "#passage-" + r.i); } catch (e) {}
  }
  // adresse la plus proche (géocodeur de la Géoplateforme IGN, interrogé par le navigateur du lecteur)
  function nearestAddress(r, cb) {
    if (r.addr !== undefined) return cb(r.addr);
    if (!window.fetch) return;
    fetch("https://data.geopf.fr/geocodage/reverse?index=address&limit=1&lon=" + r.lon + "&lat=" + r.lat)
      .then(function (x) { return x.json(); })
      .then(function (j) { var f = j.features && j.features[0]; r.addr = f && f.properties && f.properties.distance < 60 ? f.properties.name : ""; cb(r.addr); })
      .catch(function () {});
  }
  function ficheUrl(r) { return (C.pageUrl || location.href.split("#")[0].split("?")[0]) + "#passage-" + r.i; }

  /* ---------- Info-bulles ---------- */
  var tip = document.createElement("div"); tip.className = "tip"; tip.setAttribute("role", "tooltip"); document.body.appendChild(tip);
  document.addEventListener("mousemove", function (e) {
    var t = e.target.closest && e.target.closest("[data-tip]");
    if (!t) { tip.classList.remove("on"); return; }
    tip.textContent = t.getAttribute("data-tip");
    var x = e.clientX + 12, y = e.clientY - 34, w = tip.offsetWidth;
    if (x + w > window.innerWidth - 8) x = e.clientX - w - 12;
    tip.style.left = x + "px"; tip.style.top = Math.max(4, y) + "px"; tip.classList.add("on");
  });
  document.addEventListener("scroll", function () { tip.classList.remove("on"); }, true);

  /* ---------- Contrôles ---------- */
  var PRESENT = 0; ROWS.forEach(function (r) { r.items.forEach(function (it) { PRESENT |= it[0]; }); });
  document.querySelectorAll(".cat").forEach(function (cb) { if (!(PRESENT & +cb.dataset.bit)) cb.closest("label").hidden = true; });
  document.querySelectorAll(".cat").forEach(function (cb) {
    cb.addEventListener("change", function () { var bit = +cb.dataset.bit; state.cats = cb.checked ? (state.cats | bit) : (state.cats & ~bit); refresh(); });
  });
  ["ok", "mid", "ko"].forEach(function (k) { $("show-" + k).addEventListener("change", function (e) { state.show[k] = e.target.checked; drawPoints(); }); });
  function boundsOf(rows) { return L.latLngBounds(rows.map(function (r) { return [r.lat, r.lon]; })); }
  function selectCommune(i, scrollToMap) {
    state.c = state.c === i ? null : i; state.q = null;
    refresh();
    if (state.c !== null) comLayer.eachLayer(function (l) { if (l.feature.properties.i === i) map.flyToBounds(l.getBounds(), { maxZoom: 15, duration: .6 }); });
    else map.flyToBounds(comLayer.getBounds(), { duration: .6 });
    if (scrollToMap && window.matchMedia("(max-width: 860px)").matches) document.querySelector(".map-wrap").scrollIntoView({ behavior: "smooth" });
  }
  $("rank").addEventListener("click", function (e) { var bt = e.target.closest("button[data-c]"); if (bt) selectCommune(+bt.dataset.c, true); });
  $("q-select").addEventListener("change", function (e) {
    state.q = e.target.value === "" ? null : +e.target.value;
    refresh();
    var rows = ROWS.filter(function (r) { return state.q === null ? r.c === state.c : r.q === state.q; });
    if (rows.length) map.flyToBounds(boundsOf(rows).pad(0.1), { maxZoom: 16, duration: .6 });
  });
  $("pl-reset").addEventListener("click", function () { state.c = null; state.q = null; refresh(); map.flyToBounds(comLayer.getBounds(), { duration: .6 }); });
  var tabs = $("rank-tabs"); tabs.hidden = false;
  tabs.addEventListener("click", function (e) {
    var bt = e.target.closest("button[data-mode]"); if (!bt) return;
    state.rankMode = bt.dataset.mode;
    tabs.querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", x === bt); });
    drawRank();
  });

  /* ---------- Recherche d'adresse ---------- */
  var timer = null, ctr = comLayer.getBounds().getCenter();
  $("search").addEventListener("input", function (e) {
    clearTimeout(timer); var q = e.target.value.trim();
    if (q.length < 3) { $("sugg").innerHTML = ""; return; }
    timer = setTimeout(function () {
      fetch("https://data.geopf.fr/geocodage/search?index=address&limit=6&q=" + encodeURIComponent(q) + "&lat=" + ctr.lat + "&lon=" + ctr.lng)
        .then(function (x) { return x.json(); })
        .then(function (j) {
          var fs = (j.features || []).filter(function (f) { var c = f.geometry.coordinates; return comLayer.getBounds().pad(0.05).contains([c[1], c[0]]); });
          $("sugg").innerHTML = fs.length ? fs.map(function (f) { var c = f.geometry.coordinates; return '<li><button type="button" data-lat="' + c[1] + '" data-lon="' + c[0] + '">' + esc(f.properties.label) + "</button></li>"; }).join("")
            : '<li><button type="button" disabled>Aucune adresse trouvée sur le territoire</button></li>';
        })
        .catch(function () { $("sugg").innerHTML = '<li><button type="button" disabled>Recherche indisponible pour le moment</button></li>'; });
    }, 250);
  });
  $("sugg").addEventListener("click", function (e) {
    var bt = e.target.closest("button[data-lat]"); if (!bt) return;
    map.flyTo([+bt.dataset.lat, +bt.dataset.lon], 18, { duration: .6 });
    $("sugg").innerHTML = ""; $("search").value = bt.textContent;
    if (window.matchMedia("(max-width: 860px)").matches) document.querySelector(".map-wrap").scrollIntoView({ behavior: "smooth" });
  });

  /* ---------- Export des passages affichés ---------- */
  function scopeTxt() {
    if (state.q !== null) return "quartier " + qName(state.q) + " (" + comName(state.c) + ")";
    if (state.c !== null) return comName(state.c);
    return C.territoireCourt;
  }
  function props(r) {
    var o = { id: "passage-" + r.i };
    if (STREETS.length) { o.rue = r.street; o.angle = r.angle; o.entre = r.entre; o.lieu = lieuTxt(r); }
    o[UNIT.one] = comName(r.c);
    if (QS.length) o.quartier = qName(r.q);
    o.statut = STATUS_LABEL[r.st];
    o.places_amont = placesOf(r, 1); o.places_aval = placesOf(r, 2); o.places_detail = placesTxt(r);
    if (TYPES.length) o[C.typeColonne || "marquage"] = r.type > -1 ? (TYPE_LABEL[TYPES[r.type]] || TYPES[r.type]) : "";
    if (C.attributsPassage) { o.bandes_eveil = r.flags & 1 ? "oui" : (C.attributsPositifs ? "" : "non"); o.ilot_refuge = r.flags & 2 ? "oui" : (C.attributsPositifs ? "" : "non"); }
    o.latitude = r.lat; o.longitude = r.lon; o.fiche = ficheUrl(r); o.street_view = svUrl(r);
    return o;
  }
  function download(name, text, type) {
    var blob = new Blob([text], { type: type }), url = URL.createObjectURL(blob), a = document.createElement("a");
    a.href = url; a.download = name; document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(url); a.remove(); }, 1000);
  }
  function fileBase() { return "passages-pietons-" + slug(scopeTxt()) + "-" + new Date().toISOString().slice(0, 10); }
  function updateExport() {
    var n = shownRows().length;
    $("exp-n").textContent = fmt.format(n);
    $("exp-scope").textContent = (n > 1 ? "passages affichés" : "passage affiché") + ", " + scopeTxt();
    $("exp-geojson").disabled = $("exp-csv").disabled = !n;
  }
  $("exp-geojson").addEventListener("click", function () {
    var fc = { type: "FeatureCollection", features: shownRows().map(function (r) { return { type: "Feature", properties: props(r), geometry: { type: "Point", coordinates: [r.lon, r.lat] } }; }) };
    download(fileBase() + ".geojson", JSON.stringify(fc, null, 1), "application/geo+json");
  });
  $("exp-csv").addEventListener("click", function () {
    var rows = shownRows(); if (!rows.length) return;
    var cols = Object.keys(props(rows[0])).concat(["constat_date", "constat_statut", "constat_commentaire"]);
    function cell(v) { v = v == null ? "" : String(v); return /[;"\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }
    var lines = [cols.join(";")].concat(rows.map(function (r) { var p = props(r); return cols.map(function (k) { return cell(p[k]); }).join(";"); }));
    download(fileBase() + ".csv", "﻿" + lines.join("\r\n"), "text/csv;charset=utf-8");
  });

  /* ---------- Démarrage ---------- */
  map.fitBounds(comLayer.getBounds(), { padding: [10, 10] });
  refresh(); updateZoomMode();
  function openFromHash() {
    var h = (location.hash.match(/^#passage-(\d+)$/) || [])[1], r = h && ROWS[+h]; if (!r) return;
    if (!inScope(r) || !state.show[r.st]) { state.c = null; state.q = null; state.show[r.st] = true; $("show-" + r.st).checked = true; refresh(); }
    openRow(r);
  }
  openFromHash();
  window.addEventListener("hashchange", openFromHash);
})();
