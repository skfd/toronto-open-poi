/* Candidate explorer: one canvas layer per verdict, a table of what is on screen. */
'use strict';

const COLOURS = {
  'new': '#d7263d',
  'enrich': '#1b7f79',
  'conflict': '#e08a1e',
  'matched': '#8a8f98',
  'orphan': '#6a4c93',
  'not-poi': '#b9bec6',
};
const LABEL = {
  'new': 'a new POI',
  'enrich': 'an address on an existing POI',
  'conflict': 'a name conflict to resolve',
  'matched': 'already in OSM',
  'orphan': 'in OSM with no licence',
  'not-poi': 'not a mappable POI',
};
/* Comparison states, one character each in the file. */
const ADD = 'a', DIFF = 'd', CONV = 'c', SAME = 's', OSM_ONLY = 'o';
const STATE_NOTE = {
  [ADD]: 'only the licence has this — an edit would add it',
  [DIFF]: 'both have a value and they disagree',
  [CONV]: 'the same, once spelling conventions collapse',
  [SAME]: 'identical',
  [OSM_ONLY]: 'only OSM has this — nothing to contribute',
};
const STATE_CLASS = {
  [ADD]: 'add', [DIFF]: 'diff', [CONV]: 'conv', [SAME]: 'same', [OSM_ONLY]: 'osm',
};
const ORDER = ['matched', 'not-poi', 'orphan', 'conflict', 'enrich', 'new'];
const VENUE_MIN = 5;
const MAX_ROWS = 400;

let map, layers = {}, all = [], selected = null;
let tagLegend = [], reasons = {};

function style(props) {
  const c = COLOURS[props.verdict] || '#000';
  const hollow = props.snapped === false;
  const vague = props.unknown === true;
  const big = props.verdict === 'new' || props.verdict === 'enrich';
  return {
    radius: (big ? 5 : 4) - (vague ? 1.5 : 0),
    color: c,
    weight: hollow ? 2 : 1,
    opacity: vague ? 0.55 : 1,
    fillColor: hollow ? '#fff' : c,
    fillOpacity: vague ? 0.3 : (hollow ? 0.85 : 0.7),
  };
}

function esc(s) {
  return String(s === undefined || s === null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function osmUrl(p, lat, lon) {
  if (p.osm) {
    const [type, id] = p.osm.split('/');
    return `https://www.openstreetmap.org/${type}/${id}`;
  }
  return `https://www.openstreetmap.org/#map=19/${lat}/${lon}`;
}

function idUrl(p, lat, lon) {
  if (p.osm) {
    const [type, id] = p.osm.split('/');
    return `https://www.openstreetmap.org/edit?editor=id&${type}=${id}`;
  }
  return `https://www.openstreetmap.org/edit?editor=id#map=19/${lat}/${lon}`;
}

/* The heart of the popup: both sides as OSM tags, with the differences marked. */
function tagTable(p) {
  const diff = p.diff || [];
  if (!diff.length) return '';
  const adds = diff.filter(r => r[3] === ADD).length;
  const clashes = diff.filter(r => r[3] === DIFF).length;

  const soleHead = p.verdict === 'not-poi'
    ? 'what the licence holds (not proposed for OSM)'
    : 'what this POI would be tagged';
  const head = p.osm
    ? '<tr><th class="k">tag</th><th>in OSM</th><th>from the licence</th></tr>'
    : `<tr><th class="k">tag</th><th colspan="2">${soleHead}</th></tr>`;

  const body = diff.map(([tagIdx, osmVal, srcVal, state]) => {
    const tag = tagLegend[tagIdx] || '?';
    const note = STATE_NOTE[state] || '';
    const left = p.osm
      ? `<td class="v ${osmVal ? '' : 'none'}">${osmVal ? esc(osmVal) : '—'}</td>`
      : '';
    const span = p.osm ? '' : ' colspan="2"';
    return `<tr class="s-${STATE_CLASS[state] || state}" title="${esc(note)}">`
      + `<td class="k">${esc(tag)}</td>`
      + left
      + `<td class="v ${srcVal ? '' : 'none'}"${span}>${srcVal ? esc(srcVal) : '—'}</td></tr>`;
  }).join('');

  let summary = '';
  if (p.osm) {
    const bits = [];
    if (adds) bits.push(`<strong>${adds}</strong> tag${adds === 1 ? '' : 's'} to add`);
    if (clashes) bits.push(`<strong>${clashes}</strong> disagree${clashes === 1 ? 's' : ''}`);
    summary = bits.length ? `<p class="tagsum">${bits.join(' · ')}</p>` : '';
  }
  return `<table class="tagdiff">${head}${body}</table>${summary}`;
}

function facts(p) {
  const rows = [];
  if (p.type) rows.push(['Licensed as', p.type]);
  if (p.inspected) rows.push(['Last inspected', `${p.inspected} — ${p.status || ''}`]);
  if (p.venue > 1) rows.push(['Premises at this address', String(p.venue)]);
  if (p.unknown) rows.push(['Category', 'not recoverable — licensed after the 2023 archive']);
  if (p.twins) rows.push(['Also licensed as', `${p.twins} superseded id(s), collapsed`]);
  if (p.m !== undefined && p.m !== null && p.osm) rows.push(['Distance to that element', `${p.m} m`]);
  if (p.dup) rows.push(['Caution', 'the building here already carries this address']);
  if (p.snapped === false) rows.push(['Position', 'health-unit geocode, not a City address point']);
  if (!rows.length) return '';
  return '<table class="facts">' + rows.map(
    ([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join('') + '</table>';
}

function popup(p, lat, lon) {
  const out = [];
  out.push(`<h3>${esc(p.readable || p.name || '(unnamed)')}</h3>`);
  if (p.readable && p.name && p.readable !== p.name) {
    out.push(`<p class="raw">source spelling: <code>${esc(p.name)}</code></p>`);
  }
  const addr = [p.addr, p.unit, p.postcode].filter(Boolean).join(' · ');
  if (addr) out.push(`<p class="addr">${esc(addr)}</p>`);
  out.push(`<p class="verdict ${p.verdict}">Would be ${esc(LABEL[p.verdict])}</p>`);
  out.push(`<p class="why">${esc(reasons[p.reason] || p.reason || '')}</p>`);
  out.push(tagTable(p));
  out.push(facts(p));
  out.push(`<p class="links"><a href="${osmUrl(p, lat, lon)}" target="_blank" rel="noopener">OSM</a>`
    + ` · <a href="${idUrl(p, lat, lon)}" target="_blank" rel="noopener">iD</a>`
    + (p.osm ? ` <span class="elid">${esc(p.osm)}</span>` : '') + '</p>');
  return out.join('');
}

function passesFilters(f) {
  const p = f.properties;
  if (!document.getElementById(`show-${p.verdict}`).checked) return false;
  if (document.getElementById('hide-venues').checked && (p.venue || 1) >= VENUE_MIN) return false;
  if (!document.getElementById('show-unknown').checked && p.unknown) return false;
  const food = document.getElementById('only-food').checked;
  const body = document.getElementById('only-body').checked;
  if (food && p.src !== 'dinesafe') return false;
  if (body && p.src !== 'bodysafe') return false;
  const q = document.getElementById('filter').value.trim().toLowerCase();
  if (q) {
    const hay = [p.name, p.readable, p.addr, p.type, p.postcode, p.osm]
      .filter(Boolean).join(' ').toLowerCase();
    if (!hay.includes(q)) return false;
  }
  return true;
}

function redraw() {
  ORDER.forEach(v => layers[v].clearLayers());
  all.forEach(f => {
    if (!passesFilters(f)) return;
    const [lon, lat] = f.geometry.coordinates;
    const m = L.circleMarker([lat, lon], style(f.properties));
    m.feature = f;
    m.bindPopup(() => popup(f.properties, lat, lon), { maxWidth: 420, minWidth: 300 });
    layers[f.properties.verdict].addLayer(m);
  });
  updateCounts();
  fillTable();
}

function updateCounts() {
  ORDER.forEach(v => {
    const el = document.getElementById(`n-${v}`);
    if (el) el.textContent = layers[v].getLayers().length.toLocaleString();
  });
}

function fillTable() {
  const bounds = map.getBounds();
  const visible = [];
  ORDER.forEach(v => layers[v].eachLayer(m => {
    if (bounds.contains(m.getLatLng())) visible.push(m);
  }));
  visible.sort((a, b) => ORDER.indexOf(b.feature.properties.verdict)
    - ORDER.indexOf(a.feature.properties.verdict)
    || String(a.feature.properties.name).localeCompare(String(b.feature.properties.name)));

  const body = document.querySelector('#rows tbody');
  body.textContent = '';
  visible.slice(0, MAX_ROWS).forEach(m => {
    const p = m.feature.properties;
    const [lon, lat] = m.feature.geometry.coordinates;
    const adds = (p.diff || []).filter(r => r[3] === ADD).length;
    const clashes = (p.diff || []).filter(r => r[3] === DIFF).length;
    const tr = document.createElement('tr');
    tr.className = p.verdict;
    tr.innerHTML = `<td class="col-name"><span class="swatch ${p.verdict}"></span>`
      + `${esc(p.readable || p.name || '(unnamed)')}</td>`
      + `<td>${esc(p.addr || '')}</td>`
      + `<td class="tags">${adds ? `<span class="pill add">+${adds}</span>` : ''}`
      + `${clashes ? `<span class="pill diff">≠${clashes}</span>` : ''}</td>`
      + `<td class="links"><a href="${osmUrl(p, lat, lon)}" target="_blank" rel="noopener">OSM</a>`
      + ` · <a href="${idUrl(p, lat, lon)}" target="_blank" rel="noopener">iD</a></td>`;
    tr.addEventListener('click', ev => {
      if (ev.target.tagName === 'A') return;
      select(m, tr);
    });
    body.appendChild(tr);
  });
  const tally = document.querySelector('.tally');
  tally.textContent = visible.length > MAX_ROWS
    ? `${visible.length.toLocaleString()} on screen, showing the first ${MAX_ROWS} — zoom in`
    : `${visible.length.toLocaleString()} on screen`;
}

function select(marker, tr) {
  document.querySelectorAll('#rows tr.sel').forEach(el => el.classList.remove('sel'));
  if (tr) tr.classList.add('sel');
  selected = marker.feature;
  map.panTo(marker.getLatLng());
  marker.openPopup();
}

function onKey(ev) {
  if (!selected || ev.target.tagName === 'INPUT') return;
  const p = selected.properties;
  const [lon, lat] = selected.geometry.coordinates;
  if (ev.key === 'o' || ev.key === 'O') window.open(osmUrl(p, lat, lon), '_blank', 'noopener');
  if (ev.key === 'i' || ev.key === 'I') window.open(idUrl(p, lat, lon), '_blank', 'noopener');
}

function init() {
  const el = document.getElementById('map');
  map = L.map(el, { preferCanvas: true }).setView([43.70, -79.38], 12);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '&copy; OpenStreetMap contributors',
  }).addTo(map);

  const renderer = L.canvas({ padding: 0.3 });
  ORDER.forEach(v => {
    layers[v] = L.layerGroup([], { renderer }).addTo(map);
  });

  fetch(el.dataset.geojson)
    .then(r => r.json())
    .then(data => {
      tagLegend = data.tagLegend || [];
      reasons = data.reasons || {};
      all = data.features;
      redraw();
    })
    .catch(err => {
      document.querySelector('.tally').textContent =
        'Could not load candidates.geojson — serve this folder over http (run.py serve).';
      console.error(err);
    });

  ['show-new', 'show-enrich', 'show-conflict', 'show-matched', 'show-orphan',
    'show-not-poi', 'hide-venues', 'show-unknown', 'only-food', 'only-body'].forEach(id => {
    document.getElementById(id).addEventListener('change', redraw);
  });
  let t;
  document.getElementById('filter').addEventListener('input', () => {
    clearTimeout(t);
    t = setTimeout(redraw, 200);
  });
  map.on('moveend', fillTable);
  document.addEventListener('keydown', onKey);
}

document.addEventListener('DOMContentLoaded', init);
