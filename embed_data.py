#!/usr/bin/env python3
"""
embed_data.py — extract all player-season axis values from the project's
processed CSVs and bake them into a standalone compare.html.

Run once (or whenever processed CSVs change) to regenerate compare.html.
compare.html is gitignored — local tool only, contains processed data.

Usage:
    python embed_data.py          # writes compare.html to project root
"""

import json
import math
import os

import pandas as pd

import datasets
import pipeline

# ── constants ──────────────────────────────────────────────────────────────

AXES = [
    "scoring_threat__vol", "scoring_threat__eff",
    "playmaking__vol",     "playmaking__eff",
    "ball_progression__vol","ball_progression__eff",
    "possession_security__vol","possession_security__eff",
    "defensive_effectiveness__vol","defensive_effectiveness__eff",
    "physicality__vol",    "physicality__eff",
    "engine__vol",          # no engine__eff in the model
]

ALL_DATASETS = ["epl_2324"] + [datasets._nba_id(s) for s in datasets.NBA_SEASONS]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "compare.html")


# ── data extraction ────────────────────────────────────────────────────────

def _safe(v):
    """Return float or None; never NaN."""
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def extract_all():
    records = {}
    print("Extracting player-seasons:")
    for ds_id in ALL_DATASETS:
        d      = datasets.get(ds_id)
        sport  = d["sport"]
        season = d["true_season"]
        min_m  = d["min_minutes"]

        # pipeline gives within-season percentile ranks 0-1
        f = pipeline.feature_frame(d["processed"], sport, min_m)

        # raw CSV for interior_score (already 0-100)
        raw = pd.read_csv(d["processed"])
        raw_q = raw[raw["minutes"] >= min_m].copy()
        int_map = {}
        if "interior_score" in raw_q.columns:
            for _, row in raw_q.iterrows():
                v = _safe(row.get("interior_score"))
                if v is not None:
                    int_map[row["player"]] = round(v, 1)

        n = 0
        for _, row in f.iterrows():
            player = row["player"]
            key    = f"{player}||{season}"

            # Axes: 0-1 → 0-100 for chart display
            axes_vals = {}
            for ax in AXES:
                v = _safe(row.get(ax))
                axes_vals[ax] = round(v * 100, 1) if v is not None else None

            records[key] = {
                "player":         player,
                "sport":          sport,
                "season":         season,
                "axes":           axes_vals,
                "interior_score": int_map.get(player),
            }
            n += 1

        print(f"  {ds_id:12s}  ({season}, {sport:6s}): {n:3d} players")

    print(f"\nTotal embedded: {len(records)} player-seasons\n")
    return records


# ── HTML template ──────────────────────────────────────────────────────────
# Placeholder __PLAYER_DATA_JSON__ is replaced with the real JSON at build time.

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NBA ↔ EPL Radar Comparison</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg:     #0d1117;
    --card:   #161b22;
    --border: #30363d;
    --text:   #e6edf3;
    --muted:  #7d8590;
    --nba:    #388bfd;
    --epl:    #3fb950;
    --a:      #58a6ff;
    --b:      #f78166;
    --grid:   #21262d;
  }
  body { background: var(--bg); color: var(--text); font-family: system-ui, -apple-system, sans-serif; font-size: 14px; min-height: 100vh; }
  h1 { text-align: center; padding: 18px 0 4px; font-size: 1.3rem; letter-spacing: .02em; }
  h1 span { color: var(--muted); font-weight: 400; font-size: 0.9rem; }
  .subtitle { text-align: center; color: var(--muted); font-size: 0.8rem; padding-bottom: 18px; }

  /* ── pickers ── */
  .pickers { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 0 16px 16px; max-width: 960px; margin: 0 auto; }
  .picker-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 12px; position: relative; }
  .picker-card h3 { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 8px; }
  .picker-card h3 .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
  .dot-a { background: var(--a); }
  .dot-b { background: var(--b); }

  .search-wrap { position: relative; }
  .search-input {
    width: 100%; padding: 7px 10px; background: var(--bg);
    border: 1px solid var(--border); border-radius: 6px;
    color: var(--text); font-size: 13px; outline: none;
  }
  .search-input:focus { border-color: var(--a); }
  .dropdown {
    display: none; position: absolute; top: 100%; left: 0; right: 0; z-index: 100;
    background: var(--card); border: 1px solid var(--border); border-radius: 6px;
    max-height: 220px; overflow-y: auto; margin-top: 3px;
    box-shadow: 0 8px 24px rgba(0,0,0,.5);
  }
  .dropdown.open { display: block; }
  .dd-item {
    padding: 7px 10px; cursor: pointer; display: flex; align-items: center; gap: 8px;
    font-size: 13px; border-bottom: 1px solid var(--grid);
  }
  .dd-item:last-child { border-bottom: none; }
  .dd-item:hover, .dd-item.focused { background: var(--grid); }
  .dd-item .player-name { flex: 1; }
  .dd-item .season-tag { color: var(--muted); font-size: 11px; white-space: nowrap; }
  .sport-badge { font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 3px; white-space: nowrap; }
  .sport-badge.nba { background: rgba(56,139,253,.2); color: var(--nba); }
  .sport-badge.soccer { background: rgba(63,185,80,.2); color: var(--epl); }
  .no-results { padding: 10px; color: var(--muted); font-size: 12px; text-align: center; }

  .filter-bar { display: flex; gap: 6px; margin-bottom: 8px; }
  .filter-btn {
    padding: 3px 10px; border-radius: 12px; border: 1px solid var(--border);
    background: transparent; color: var(--muted); font-size: 11px; cursor: pointer;
    transition: all .15s;
  }
  .filter-btn.active { border-color: var(--a); color: var(--text); background: rgba(88,166,255,.1); }

  .selected-info {
    margin-top: 8px; font-size: 12px; min-height: 36px;
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  }
  .selected-name { font-weight: 600; }
  .clear-btn {
    font-size: 11px; color: var(--muted); background: none; border: 1px solid var(--border);
    border-radius: 4px; padding: 2px 7px; cursor: pointer;
  }
  .clear-btn:hover { color: var(--text); }
  .interior-badge {
    font-size: 11px; background: rgba(247,129,102,.15); color: #f0a070;
    border-radius: 4px; padding: 2px 7px;
  }

  /* ── radar grid ── */
  .radars-top { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 0 16px 12px; max-width: 960px; margin: 0 auto; }
  .radar-panel { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 12px; text-align: center; }
  .radar-panel h3 { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 8px; }
  .radar-overlay-wrap { padding: 0 16px 20px; max-width: 960px; margin: 0 auto; }
  .radar-overlay-panel { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 12px; text-align: center; }
  .radar-overlay-panel h3 { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 4px; }
  .overlay-legend { font-size: 11px; color: var(--muted); margin-bottom: 8px; }
  .overlay-legend span { display: inline-flex; align-items: center; gap: 4px; margin: 0 8px; }
  .legend-line { display: inline-block; width: 22px; height: 2px; vertical-align: middle; }
  .legend-line.solid { background: var(--a); }
  .legend-line.dashed { background: linear-gradient(90deg, var(--b) 60%, transparent 60%); background-size: 6px; }

  svg { display: block; margin: 0 auto; }
  .empty-radar { color: var(--muted); font-size: 12px; padding: 40px 0; }

  /* ── footer ── */
  footer { text-align: center; padding: 12px; font-size: 11px; color: var(--muted); border-top: 1px solid var(--grid); }
</style>
</head>
<body>

<h1>NBA ↔ EPL Radar Comparison <span>— within-season normalized</span></h1>
<p class="subtitle">All axes are percentile ranks within each player's own league-season (0 = worst, 100 = best).</p>

<div class="pickers">
  <div class="picker-card" id="card-a">
    <h3><span class="dot dot-a"></span>Player A</h3>
    <div class="filter-bar" id="filters-a">
      <button class="filter-btn active" data-sport="all">All</button>
      <button class="filter-btn" data-sport="nba">NBA</button>
      <button class="filter-btn" data-sport="soccer">EPL</button>
    </div>
    <div class="search-wrap">
      <input class="search-input" id="search-a" placeholder="Type player name…" autocomplete="off">
      <div class="dropdown" id="drop-a"></div>
    </div>
    <div class="selected-info" id="sel-a"><span style="color:var(--muted)">No player selected</span></div>
  </div>
  <div class="picker-card" id="card-b">
    <h3><span class="dot dot-b"></span>Player B</h3>
    <div class="filter-bar" id="filters-b">
      <button class="filter-btn active" data-sport="all">All</button>
      <button class="filter-btn" data-sport="nba">NBA</button>
      <button class="filter-btn" data-sport="soccer">EPL</button>
    </div>
    <div class="search-wrap">
      <input class="search-input" id="search-b" placeholder="Type player name…" autocomplete="off">
      <div class="dropdown" id="drop-b"></div>
    </div>
    <div class="selected-info" id="sel-b"><span style="color:var(--muted)">No player selected</span></div>
  </div>
</div>

<div class="radars-top">
  <div class="radar-panel">
    <h3><span class="dot dot-a"></span>Player A</h3>
    <svg id="radar-a" width="380" height="380"></svg>
  </div>
  <div class="radar-panel">
    <h3><span class="dot dot-b"></span>Player B</h3>
    <svg id="radar-b" width="380" height="380"></svg>
  </div>
</div>

<div class="radar-overlay-wrap">
  <div class="radar-overlay-panel">
    <h3>Overlay</h3>
    <div class="overlay-legend">
      <span><span class="legend-line solid"></span>Player A (solid)</span>
      <span><span class="legend-line dashed"></span>Player B (dashed)</span>
    </div>
    <svg id="radar-overlay" width="520" height="520"></svg>
  </div>
</div>

<footer>
  Within-season normalized — axes are percentile ranks inside each player's own league-season.
  Cross-sport comparison is valid; cross-era comparison shows relative-to-peers change.
</footer>

<script>
// ── embedded data ──────────────────────────────────────────────────────────
const PLAYER_DATA = __PLAYER_DATA_JSON__;

// ── constants ──────────────────────────────────────────────────────────────
const AXES = [
  "scoring_threat__vol","scoring_threat__eff",
  "playmaking__vol","playmaking__eff",
  "ball_progression__vol","ball_progression__eff",
  "possession_security__vol","possession_security__eff",
  "defensive_effectiveness__vol","defensive_effectiveness__eff",
  "physicality__vol","physicality__eff",
  "engine__vol"
];

// Two-line labels: [dimension, vol/eff/empty]
const AXIS_LABELS = [
  ["Scoring","Vol"],["Scoring","Eff"],
  ["Playmaking","Vol"],["Playmaking","Eff"],
  ["Progression","Vol"],["Progression","Eff"],
  ["Possession","Vol"],["Possession","Eff"],
  ["Defense","Vol"],["Defense","Eff"],
  ["Physicality","Vol"],["Physicality","Eff"],
  ["Engine",""]
];

const COLOR_A = "#58a6ff";
const COLOR_B = "#f78166";
const N = AXES.length;

// ── search index ───────────────────────────────────────────────────────────
const ENTRIES = Object.entries(PLAYER_DATA)
  .map(([key, d]) => ({
    key,
    player:  d.player,
    sport:   d.sport,
    season:  d.season,
    search:  d.player.toLowerCase()
  }))
  .sort((a, b) => a.player.localeCompare(b.player));

// ── state ──────────────────────────────────────────────────────────────────
const state = { a: null, b: null };
const sportFilter = { a: "all", b: "all" };

// ── SVG radar ──────────────────────────────────────────────────────────────
const NS = "http://www.w3.org/2000/svg";
function mk(tag, attrs, text) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (text !== undefined) el.textContent = text;
  return el;
}

function drawRadar(svgId, datasets) {
  const svg = document.getElementById(svgId);
  const W = +svg.getAttribute("width");
  const H = +svg.getAttribute("height");
  const cx = W / 2, cy = H / 2;
  // Radius leaves room for labels: ~30% of half-width for labels
  const r = Math.min(cx, cy) * 0.58;
  const labelR = r + 34;

  svg.innerHTML = "";

  // Background
  svg.appendChild(mk("rect", { width: W, height: H, fill: "#0d1117", rx: 8 }));

  // Grid circles + % labels
  for (const pct of [25, 50, 75, 100]) {
    svg.appendChild(mk("circle", {
      cx, cy, r: r * pct / 100,
      fill: "none", stroke: "#21262d", "stroke-width": pct === 50 ? 1.2 : 0.7
    }));
    // small label at right of 50% ring
    if (pct === 50) {
      svg.appendChild(mk("text", {
        x: cx + r * 0.5 + 3, y: cy - 3,
        fill: "#484f58", "font-size": 8, "text-anchor": "start"
      }, "50"));
    }
  }

  // Axis lines
  for (let i = 0; i < N; i++) {
    const angle = (i / N) * 2 * Math.PI - Math.PI / 2;
    svg.appendChild(mk("line", {
      x1: cx, y1: cy,
      x2: cx + r * Math.cos(angle),
      y2: cy + r * Math.sin(angle),
      stroke: "#21262d", "stroke-width": 1
    }));
  }

  // Axis labels (2 tspan lines)
  for (let i = 0; i < N; i++) {
    const angle = (i / N) * 2 * Math.PI - Math.PI / 2;
    const lx = cx + labelR * Math.cos(angle);
    const ly = cy + labelR * Math.sin(angle);
    const [line1, line2] = AXIS_LABELS[i];

    const t = document.createElementNS(NS, "text");
    t.setAttribute("text-anchor", "middle");
    t.setAttribute("dominant-baseline", "middle");
    t.setAttribute("font-size", "9");
    t.setAttribute("font-family", "system-ui, sans-serif");

    const s1 = document.createElementNS(NS, "tspan");
    s1.setAttribute("x", lx);
    s1.setAttribute("dy", line2 ? "-5" : "0");
    s1.setAttribute("fill", "#9198a1");
    s1.textContent = line1;
    t.appendChild(s1);

    if (line2) {
      const s2 = document.createElementNS(NS, "tspan");
      s2.setAttribute("x", lx);
      s2.setAttribute("dy", "12");
      s2.setAttribute("fill", "#55606b");
      s2.setAttribute("font-size", "8");
      s2.textContent = line2;
      t.appendChild(s2);
    }
    svg.appendChild(t);
  }

  // Player polygons — render fill first, then strokes on top
  const polyLayers = [];
  for (const { data, color, dashed, alpha } of datasets) {
    if (!data) continue;
    const pts = [];
    for (let i = 0; i < N; i++) {
      const v = data.axes[AXES[i]];
      const val = (v !== null && v !== undefined) ? v : 0;
      const angle = (i / N) * 2 * Math.PI - Math.PI / 2;
      const pr = r * val / 100;
      pts.push([cx + pr * Math.cos(angle), cy + pr * Math.sin(angle)]);
    }
    polyLayers.push({ pts, color, dashed, alpha, data });
  }

  // fills
  for (const { pts, color, alpha } of polyLayers) {
    svg.appendChild(mk("polygon", {
      points: pts.map(p => p.join(",")).join(" "),
      fill: color,
      "fill-opacity": alpha ?? 0.12,
      stroke: "none"
    }));
  }
  // strokes + dots
  for (const { pts, color, dashed, data } of polyLayers) {
    svg.appendChild(mk("polygon", {
      points: pts.map(p => p.join(",")).join(" "),
      fill: "none",
      stroke: color,
      "stroke-width": 2,
      "stroke-linejoin": "round",
      "stroke-dasharray": dashed ? "5,3" : "none"
    }));
    for (let i = 0; i < N; i++) {
      const v = data.axes[AXES[i]];
      if (v !== null && v !== undefined) {
        svg.appendChild(mk("circle", {
          cx: pts[i][0], cy: pts[i][1], r: 2.5, fill: color
        }));
      }
    }
  }

  // center dot
  svg.appendChild(mk("circle", { cx, cy, r: 3, fill: "#484f58" }));
}

function drawEmpty(svgId, msg) {
  const svg = document.getElementById(svgId);
  const W = +svg.getAttribute("width"), H = +svg.getAttribute("height");
  svg.innerHTML = "";
  svg.appendChild(mk("rect", { width: W, height: H, fill: "#0d1117", rx: 8 }));
  const t = mk("text", {
    x: W/2, y: H/2, "text-anchor": "middle", "dominant-baseline": "middle",
    fill: "#484f58", "font-size": 13, "font-family": "system-ui, sans-serif"
  }, msg || "Select a player");
  svg.appendChild(t);
}

// ── initial empty state ────────────────────────────────────────────────────
["radar-a","radar-b","radar-overlay"].forEach(id => drawEmpty(id));

// ── render radars ──────────────────────────────────────────────────────────
function renderAll() {
  const da = state.a ? PLAYER_DATA[state.a.key] : null;
  const db = state.b ? PLAYER_DATA[state.b.key] : null;

  if (da) drawRadar("radar-a", [{ data: da, color: COLOR_A }]);
  else drawEmpty("radar-a");

  if (db) drawRadar("radar-b", [{ data: db, color: COLOR_B }]);
  else drawEmpty("radar-b");

  if (da || db) {
    drawRadar("radar-overlay", [
      da ? { data: da, color: COLOR_A, alpha: 0.15 } : null,
      db ? { data: db, color: COLOR_B, dashed: true, alpha: 0.10 } : null,
    ].filter(Boolean));
  } else {
    drawEmpty("radar-overlay", "Select two players to overlay");
  }
}

// ── picker logic ───────────────────────────────────────────────────────────
function filterEntries(query, sport) {
  const q = query.trim().toLowerCase();
  return ENTRIES.filter(e =>
    (!q || e.search.includes(q)) &&
    (sport === "all" || e.sport === sport)
  ).slice(0, 60);
}

function sportBadge(sport) {
  const cls = sport === "nba" ? "nba" : "soccer";
  const lbl = sport === "nba" ? "NBA" : "EPL";
  return `<span class="sport-badge ${cls}">${lbl}</span>`;
}

function renderSelectedInfo(side, entry) {
  const el = document.getElementById("sel-" + side);
  if (!entry) {
    el.innerHTML = `<span style="color:var(--muted)">No player selected</span>`;
    return;
  }
  const d = PLAYER_DATA[entry.key];
  const interior = d.interior_score !== null
    ? `<span class="interior-badge">Interior ${d.interior_score}</span>` : "";
  el.innerHTML = `
    ${sportBadge(entry.sport)}
    <span class="selected-name">${entry.player}</span>
    <span style="color:var(--muted);font-size:11px">${entry.season}</span>
    ${interior}
    <button class="clear-btn" onclick="clearSide('${side}')">✕ clear</button>
  `;
}

function clearSide(side) {
  state[side] = null;
  document.getElementById("search-" + side).value = "";
  renderSelectedInfo(side, null);
  renderAll();
}

function setupPicker(side) {
  const input = document.getElementById("search-" + side);
  const drop  = document.getElementById("drop-"   + side);
  let focused = -1;

  function showDrop(items) {
    if (!items.length) {
      drop.innerHTML = `<div class="no-results">No players found</div>`;
    } else {
      drop.innerHTML = items.map((e, idx) =>
        `<div class="dd-item" data-idx="${idx}" data-key="${e.key}">
           <span class="player-name">${e.player}</span>
           ${sportBadge(e.sport)}
           <span class="season-tag">${e.season}</span>
         </div>`
      ).join("");
    }
    drop.classList.add("open");
    focused = -1;
    // attach click
    drop.querySelectorAll(".dd-item").forEach((el, idx) => {
      el.addEventListener("mousedown", ev => {
        ev.preventDefault();
        selectEntry(side, items[idx]);
      });
    });
  }

  function hideDrop() {
    drop.classList.remove("open");
    focused = -1;
  }

  function selectEntry(side, entry) {
    state[side] = entry;
    input.value = "";
    hideDrop();
    renderSelectedInfo(side, entry);
    renderAll();
  }

  input.addEventListener("input", () => {
    const q = input.value;
    if (!q.trim()) { hideDrop(); return; }
    showDrop(filterEntries(q, sportFilter[side]));
  });

  input.addEventListener("keydown", ev => {
    const items = drop.querySelectorAll(".dd-item");
    if (ev.key === "ArrowDown") {
      focused = Math.min(focused + 1, items.length - 1);
      items.forEach((el, i) => el.classList.toggle("focused", i === focused));
      ev.preventDefault();
    } else if (ev.key === "ArrowUp") {
      focused = Math.max(focused - 1, 0);
      items.forEach((el, i) => el.classList.toggle("focused", i === focused));
      ev.preventDefault();
    } else if (ev.key === "Enter" && focused >= 0) {
      items[focused].dispatchEvent(new MouseEvent("mousedown"));
    } else if (ev.key === "Escape") {
      hideDrop();
    }
  });

  input.addEventListener("focus", () => {
    if (input.value.trim()) showDrop(filterEntries(input.value, sportFilter[side]));
  });

  document.addEventListener("click", ev => {
    if (!ev.target.closest("#card-" + (side === "a" ? "a" : "b"))) hideDrop();
  });

  // sport filter buttons
  document.getElementById("filters-" + side).querySelectorAll(".filter-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      sportFilter[side] = btn.dataset.sport;
      document.getElementById("filters-" + side).querySelectorAll(".filter-btn")
        .forEach(b => b.classList.toggle("active", b === btn));
      if (drop.classList.contains("open")) {
        showDrop(filterEntries(input.value, sportFilter[side]));
      }
    });
  });
}

setupPicker("a");
setupPicker("b");
</script>
</body>
</html>"""


# ── main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    records = extract_all()

    json_str = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    html = HTML_TEMPLATE.replace("__PLAYER_DATA_JSON__", json_str)

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)

    size_kb = os.path.getsize(OUT) / 1024
    print(f"Wrote {OUT}  ({size_kb:.0f} KB)")
    print(f"\nOpen in browser:  open \"{OUT}\"")
