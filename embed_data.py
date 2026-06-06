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
  .pickers { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 0 16px 16px; max-width: 1100px; margin: 0 auto; }
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
    margin-top: 8px; font-size: 12px; min-height: 26px;
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  }
  .selected-name { font-weight: 600; }
  .clear-btn {
    font-size: 11px; color: var(--muted); background: none; border: 1px solid var(--border);
    border-radius: 4px; padding: 2px 7px; cursor: pointer;
  }
  .clear-btn:hover { color: var(--text); }

  /* ── dimension weight panel ── */
  .weights-wrap { padding: 0 16px 12px; max-width: 1100px; margin: 0 auto; }
  .weights-header { display: flex; align-items: center; gap: 10px; }
  .weights-toggle {
    background: var(--card); border: 1px solid var(--border); border-radius: 6px;
    color: var(--muted); font-size: 12px; padding: 5px 12px; cursor: pointer;
    transition: all .15s; letter-spacing: .01em;
  }
  .weights-toggle:hover { color: var(--text); border-color: var(--a); }
  .weights-toggle.active { color: var(--a); border-color: var(--a); background: rgba(88,166,255,.08); }
  .weights-active-dot {
    width: 6px; height: 6px; border-radius: 50%; background: var(--a);
    display: none; flex-shrink: 0;
  }
  .weights-active-dot.visible { display: block; }
  .weights-body {
    display: none; margin-top: 8px;
    background: var(--card); border: 1px solid var(--border); border-radius: 8px;
    padding: 14px 16px;
  }
  .weights-body.open { display: block; }
  .weights-note {
    font-size: 11px; color: var(--muted); margin-bottom: 14px;
    padding-bottom: 10px; border-bottom: 1px solid var(--grid); line-height: 1.5;
  }
  .weights-note strong { color: var(--text); }
  .slider-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 10px 24px; margin-bottom: 12px;
  }
  .slider-row { display: flex; align-items: center; gap: 8px; }
  .slider-label { font-size: 11px; color: var(--muted); width: 78px; flex-shrink: 0; }
  .weight-slider {
    flex: 1; -webkit-appearance: none; appearance: none;
    height: 4px; border-radius: 2px; outline: none; cursor: pointer;
    /* initial fill set by JS at 33.3% = 1.0 / 3.0 */
    background: linear-gradient(to right, #58a6ff 33.3%, #21262d 33.3%);
  }
  .weight-slider::-webkit-slider-thumb {
    -webkit-appearance: none; width: 14px; height: 14px;
    border-radius: 50%; background: #58a6ff; cursor: pointer;
    box-shadow: 0 0 0 2px rgba(88,166,255,.25);
  }
  .weight-slider::-moz-range-thumb {
    width: 14px; height: 14px; border-radius: 50%; background: #58a6ff;
    cursor: pointer; border: none; box-shadow: 0 0 0 2px rgba(88,166,255,.25);
  }
  .weight-val {
    font-size: 11px; font-weight: 700; color: var(--text);
    width: 32px; text-align: right; flex-shrink: 0; font-variant-numeric: tabular-nums;
  }
  .weight-val.zero { color: var(--muted); }
  .weights-actions { display: flex; align-items: center; gap: 12px; padding-top: 10px; border-top: 1px solid var(--grid); }
  .reset-btn {
    font-size: 11px; padding: 4px 12px; border-radius: 5px;
    border: 1px solid var(--border); background: none;
    color: var(--muted); cursor: pointer; transition: all .15s;
  }
  .reset-btn:hover { color: var(--text); border-color: var(--muted); }

  /* small weight badge shown in sidebar/table when w ≠ 1.0 */
  .w-badge { font-size: 9px; color: #58a6ff; opacity: .85; margin-left: 2px; }
  .w-badge.zero { color: var(--muted); }

  /* ── radar panels ── */
  .radars-top { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 0 16px 12px; max-width: 1100px; margin: 0 auto; }
  .radar-panel { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
  .radar-panel > h3 { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 8px; }
  .panel-body { display: flex; gap: 10px; align-items: flex-start; }
  .radar-svg-wrap { flex: 1; min-width: 0; overflow: hidden; }

  /* ── sidebar scorecard ── */
  .sidebar { width: 152px; flex-shrink: 0; padding-top: 2px; }
  .sidebar-row { margin-bottom: 9px; }
  .sidebar-label { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 3px; }
  .sidebar-dim-name { font-size: 10px; color: var(--muted); }
  .sidebar-score { font-size: 11px; font-weight: 700; color: var(--text); }
  .bar-track { height: 5px; background: var(--grid); border-radius: 3px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 3px; transition: width .2s ease; }
  .sidebar-interior { margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--grid); }
  .sidebar-interior-label { font-size: 10px; color: var(--muted); margin-bottom: 4px; }
  .int-badge { display: inline-block; font-size: 12px; font-weight: 700; padding: 2px 8px; border-radius: 4px; background: rgba(247,129,102,.18); color: #f0a070; }

  /* ── overlay panel ── */
  .radar-overlay-wrap { padding: 0 16px 12px; max-width: 1100px; margin: 0 auto; }
  .radar-overlay-panel { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 12px; text-align: center; }
  .radar-overlay-panel > h3 { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 4px; }
  .overlay-legend { font-size: 11px; color: var(--muted); margin-bottom: 8px; }
  .overlay-legend span { display: inline-flex; align-items: center; gap: 4px; margin: 0 8px; }
  .legend-line { display: inline-block; width: 22px; height: 2px; vertical-align: middle; }
  .legend-line.solid { background: var(--a); }
  .legend-line.dashed { background: linear-gradient(90deg, var(--b) 60%, transparent 60%); background-size: 6px; }

  svg { display: block; margin: 0 auto; }

  /* ── comparison section ── */
  .comparison-wrap { padding: 0 16px 24px; max-width: 1100px; margin: 0 auto; display: none; }
  .comparison-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px 20px; }
  .comparison-header { display: flex; align-items: center; gap: 20px; margin-bottom: 16px; padding-bottom: 14px; border-bottom: 1px solid var(--grid); }
  .sim-block { flex-shrink: 0; }
  .sim-label { font-size: 0.72rem; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 2px; }
  .sim-score { font-size: 2.2rem; font-weight: 800; line-height: 1; }
  .sim-green { color: #3fb950; }
  .sim-amber { color: #d29922; }
  .sim-red   { color: #f85149; }
  .sim-desc { font-size: 11px; color: var(--muted); line-height: 1.6; }
  .dim-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .dim-table th {
    color: var(--muted); font-weight: 500; padding: 5px 10px;
    border-bottom: 1px solid var(--border); text-align: right;
  }
  .dim-table th:first-child { text-align: left; }
  .dim-table td {
    padding: 6px 10px; border-bottom: 1px solid var(--grid);
    text-align: right; font-variant-numeric: tabular-nums;
  }
  .dim-table td:first-child { text-align: left; font-weight: 500; color: var(--text); }
  .dim-table tr:last-child td { border-bottom: none; }
  .gap-a { color: var(--a); font-weight: 700; }
  .gap-b { color: var(--b); font-weight: 700; }
  .gap-close { color: var(--muted); }

  /* ── footer ── */
  footer { text-align: center; padding: 14px; font-size: 11px; color: var(--muted); border-top: 1px solid var(--grid); margin-top: 4px; }
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

<!-- Dimension weight sliders — collapsed by default -->
<div class="weights-wrap">
  <div class="weights-header">
    <button class="weights-toggle" id="weights-toggle">Dimension weights ▾</button>
    <span class="weights-active-dot" id="weights-active-dot" title="Custom weights active"></span>
  </div>
  <div class="weights-body" id="weights-body">
    <p class="weights-note">
      <strong>Weights affect:</strong> similarity score, comparison gap coloring, and sidebar bar widths.
      <strong>Radar shape is always unweighted</strong> — it shows raw percentiles.
      Set a dimension to 0× to exclude it from similarity entirely.
    </p>
    <div class="slider-grid">
      <div class="slider-row">
        <span class="slider-label">Scoring</span>
        <input class="weight-slider" id="slider-scoring" type="range" min="0" max="3" step="0.1" value="1">
        <span class="weight-val" id="weight-val-scoring">1.0×</span>
      </div>
      <div class="slider-row">
        <span class="slider-label">Playmaking</span>
        <input class="weight-slider" id="slider-playmaking" type="range" min="0" max="3" step="0.1" value="1">
        <span class="weight-val" id="weight-val-playmaking">1.0×</span>
      </div>
      <div class="slider-row">
        <span class="slider-label">Progression</span>
        <input class="weight-slider" id="slider-progression" type="range" min="0" max="3" step="0.1" value="1">
        <span class="weight-val" id="weight-val-progression">1.0×</span>
      </div>
      <div class="slider-row">
        <span class="slider-label">Possession</span>
        <input class="weight-slider" id="slider-possession" type="range" min="0" max="3" step="0.1" value="1">
        <span class="weight-val" id="weight-val-possession">1.0×</span>
      </div>
      <div class="slider-row">
        <span class="slider-label">Defense</span>
        <input class="weight-slider" id="slider-defense" type="range" min="0" max="3" step="0.1" value="1">
        <span class="weight-val" id="weight-val-defense">1.0×</span>
      </div>
      <div class="slider-row">
        <span class="slider-label">Physicality</span>
        <input class="weight-slider" id="slider-physicality" type="range" min="0" max="3" step="0.1" value="1">
        <span class="weight-val" id="weight-val-physicality">1.0×</span>
      </div>
      <div class="slider-row">
        <span class="slider-label">Engine</span>
        <input class="weight-slider" id="slider-engine" type="range" min="0" max="3" step="0.1" value="1">
        <span class="weight-val" id="weight-val-engine">1.0×</span>
      </div>
    </div>
    <div class="weights-actions">
      <button class="reset-btn" id="weights-reset">Reset to defaults</button>
    </div>
  </div>
</div>

<!-- Solo radar panels — each has radar (left) + scorecard sidebar (right) -->
<div class="radars-top">
  <div class="radar-panel">
    <h3><span class="dot dot-a"></span>Player A</h3>
    <div class="panel-body">
      <div class="radar-svg-wrap"><svg id="radar-a" width="320" height="320"></svg></div>
      <div class="sidebar" id="sidebar-a"></div>
    </div>
  </div>
  <div class="radar-panel">
    <h3><span class="dot dot-b"></span>Player B</h3>
    <div class="panel-body">
      <div class="radar-svg-wrap"><svg id="radar-b" width="320" height="320"></svg></div>
      <div class="sidebar" id="sidebar-b"></div>
    </div>
  </div>
</div>

<!-- Overlay panel -->
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

<!-- Comparison section — shown only when both players are selected -->
<div class="comparison-wrap" id="comparison-wrap"></div>

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

// Two-line labels — distributed around the perimeter by the radar drawing code.
const AXIS_LABELS = [
  ["Scoring","(vol)"],   ["Scoring","(eff)"],
  ["Playmaking","(vol)"],["Playmaking","(eff)"],
  ["Progression","(vol)"],["Progression","(eff)"],
  ["Possession","(vol)"],["Possession","(eff)"],
  ["Defense","(vol)"],   ["Defense","(eff)"],
  ["Physicality","(vol)"],["Physicality","(eff)"],
  ["Engine",""]
];

// 7 dimensions for sidebar scorecards and comparison table.
// Each dim's axes are used both for scoring and for applying weight in similarity.
const DIMS = [
  {name:"Scoring",     key:"scoring",     axes:["scoring_threat__vol","scoring_threat__eff"]},
  {name:"Playmaking",  key:"playmaking",  axes:["playmaking__vol","playmaking__eff"]},
  {name:"Progression", key:"progression", axes:["ball_progression__vol","ball_progression__eff"]},
  {name:"Possession",  key:"possession",  axes:["possession_security__vol","possession_security__eff"]},
  {name:"Defense",     key:"defense",     axes:["defensive_effectiveness__vol","defensive_effectiveness__eff"]},
  {name:"Physicality", key:"physicality", axes:["physicality__vol","physicality__eff"]},
  {name:"Engine",      key:"engine",      axes:["engine__vol"]},
];

const COLOR_A = "#58a6ff";
const COLOR_B = "#f78166";
const N = AXES.length;

// ── weights state ──────────────────────────────────────────────────────────
// Keyed by dim.key; default 1.0 for all dimensions.
const weights = {};
for (const dim of DIMS) weights[dim.key] = 1.0;

function anyNonDefault() {
  return DIMS.some(d => weights[d.key] !== 1.0);
}

// ── search index ───────────────────────────────────────────────────────────
const ENTRIES = Object.entries(PLAYER_DATA)
  .map(([key, d]) => ({
    key,
    player: d.player,
    sport:  d.sport,
    season: d.season,
    search: d.player.toLowerCase()
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

  // Radar always shows raw unweighted percentiles — weights never touch this function.
  const r      = Math.min(cx, cy) * 0.55;
  const labelR = r * 1.44;

  svg.innerHTML = "";

  // Background
  svg.appendChild(mk("rect", { width: W, height: H, fill: "#0d1117", rx: 8 }));

  // Grid rings at 25 / 50 / 75 / 100 %
  for (const pct of [25, 50, 75, 100]) {
    svg.appendChild(mk("circle", {
      cx, cy, r: r * pct / 100,
      fill: "none", stroke: "#21262d",
      "stroke-width": pct === 50 ? 1.2 : 0.7
    }));
  }
  svg.appendChild(mk("text", {
    x: cx + r * 0.5 + 3, y: cy - 3,
    fill: "#484f58", "font-size": 8, "text-anchor": "start"
  }, "50"));

  // Axis spokes
  for (let i = 0; i < N; i++) {
    const angle = (i / N) * 2 * Math.PI - Math.PI / 2;
    svg.appendChild(mk("line", {
      x1: cx, y1: cy,
      x2: cx + r * Math.cos(angle),
      y2: cy + r * Math.sin(angle),
      stroke: "#21262d", "stroke-width": 1
    }));
  }

  // Axis labels — two tspan lines at each tip, evenly around the perimeter
  for (let i = 0; i < N; i++) {
    const angle = (i / N) * 2 * Math.PI - Math.PI / 2;
    const lx = cx + labelR * Math.cos(angle);
    const ly = cy + labelR * Math.sin(angle);
    const [line1, line2] = AXIS_LABELS[i];

    const t = document.createElementNS(NS, "text");
    t.setAttribute("text-anchor", "middle");
    t.setAttribute("dominant-baseline", "middle");
    t.setAttribute("font-family", "system-ui, sans-serif");

    const s1 = document.createElementNS(NS, "tspan");
    s1.setAttribute("x", lx);
    s1.setAttribute("dy", line2 ? "-5" : "0");
    s1.setAttribute("fill", "#9198a1");
    s1.setAttribute("font-size", "9");
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

  // Player polygons — fills first, then strokes + vertex dots
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

  for (const { pts, color, alpha } of polyLayers) {
    svg.appendChild(mk("polygon", {
      points: pts.map(p => p.join(",")).join(" "),
      fill: color, "fill-opacity": alpha ?? 0.12, stroke: "none"
    }));
  }
  for (const { pts, color, dashed, data } of polyLayers) {
    svg.appendChild(mk("polygon", {
      points: pts.map(p => p.join(",")).join(" "),
      fill: "none", stroke: color, "stroke-width": 2,
      "stroke-linejoin": "round",
      "stroke-dasharray": dashed ? "5,3" : "none"
    }));
    for (let i = 0; i < N; i++) {
      const v = data.axes[AXES[i]];
      if (v !== null && v !== undefined) {
        svg.appendChild(mk("circle", { cx: pts[i][0], cy: pts[i][1], r: 2.5, fill: color }));
      }
    }
  }

  svg.appendChild(mk("circle", { cx, cy, r: 3, fill: "#484f58" }));
}

function drawEmpty(svgId, msg) {
  const svg = document.getElementById(svgId);
  const W = +svg.getAttribute("width"), H = +svg.getAttribute("height");
  svg.innerHTML = "";
  svg.appendChild(mk("rect", { width: W, height: H, fill: "#0d1117", rx: 8 }));
  svg.appendChild(mk("text", {
    x: W/2, y: H/2, "text-anchor": "middle", "dominant-baseline": "middle",
    fill: "#484f58", "font-size": 13, "font-family": "system-ui, sans-serif"
  }, msg || "Select a player"));
}

// ── dimension helpers ──────────────────────────────────────────────────────

// Raw (unweighted) average of a dimension's axes.
function dimScore(data, dim) {
  const vals = dim.axes
    .map(ax => data.axes[ax])
    .filter(v => v !== null && v !== undefined);
  return vals.length ? vals.reduce((s, v) => s + v, 0) / vals.length : null;
}

// Weight badge HTML — shows "×W" next to dim name when W ≠ 1.0.
function wBadge(dim) {
  const w = weights[dim.key];
  if (w === 1.0) return "";
  const cls = w === 0 ? "w-badge zero" : "w-badge";
  return `<span class="${cls}">×${w.toFixed(1)}</span>`;
}

// ── sidebar scorecard ──────────────────────────────────────────────────────
// Bar width is scaled by dimension weight (capped at 100); raw score shown as number.

function renderSidebar(id, data, color) {
  const el = document.getElementById(id);
  if (!data) { el.innerHTML = ""; return; }

  let html = "";
  for (const dim of DIMS) {
    const score = dimScore(data, dim);
    const w     = weights[dim.key];
    // Bar width = raw score × weight, capped at 100 so it never overflows the track.
    const barPct = score !== null ? Math.min(100, score * w).toFixed(1) : 0;
    html += `
      <div class="sidebar-row">
        <div class="sidebar-label">
          <span class="sidebar-dim-name">${dim.name}${wBadge(dim)}</span>
          <span class="sidebar-score">${score !== null ? Math.round(score) : "—"}</span>
        </div>
        <div class="bar-track">
          <div class="bar-fill" style="width:${barPct}%;background:${color}"></div>
        </div>
      </div>`;
  }

  const is = data.interior_score;
  if (is !== null && is !== undefined) {
    html += `
      <div class="sidebar-interior">
        <div class="sidebar-interior-label">Interior score</div>
        <span class="int-badge">${is}</span>
      </div>`;
  }

  el.innerHTML = html;
}

// ── weighted similarity ────────────────────────────────────────────────────
// sim = 100 − √(Σ w_i·(a_i−b_i)² / Σ w_i)
// Both __vol and __eff axes in a dimension receive the same weight.
// Clamped to [0, 100].

function computeSimilarity(da, db) {
  let wDiffSum = 0, wSum = 0;
  for (const dim of DIMS) {
    const w = weights[dim.key];
    if (w === 0) continue;          // zero-weight dim excluded entirely
    for (const ax of dim.axes) {
      const va = da.axes[ax], vb = db.axes[ax];
      if (va !== null && va !== undefined && vb !== null && vb !== undefined) {
        wDiffSum += w * (va - vb) ** 2;
        wSum     += w;
      }
    }
  }
  if (!wSum) return null;
  return Math.max(0, Math.min(100, 100 - Math.sqrt(wDiffSum / wSum)));
}

// ── comparison table ───────────────────────────────────────────────────────
// Raw scores shown; gap coloring uses weighted gap so zeroed-out dims are neutral.

function renderComparison(da, db) {
  const wrap = document.getElementById("comparison-wrap");
  if (!da || !db) { wrap.style.display = "none"; return; }
  wrap.style.display = "block";

  const sim    = computeSimilarity(da, db);
  const simCls = sim >= 75 ? "sim-green" : sim >= 55 ? "sim-amber" : "sim-red";
  const simTxt = sim >= 75 ? "Strong match across dimensions"
               : sim >= 55 ? "Moderate similarity — notable gaps in some dimensions"
               :             "Low similarity — players fill very different roles";

  // Weight caveat line — only shown when weights are non-default
  const weightNote = anyNonDefault()
    ? `<span style="color:#58a6ff;opacity:.85"> · custom weights active</span>`
    : "";

  let rows = "";
  for (const dim of DIMS) {
    const sa  = dimScore(da, dim);
    const sb  = dimScore(db, dim);
    const w   = weights[dim.key];
    const gap = (sa !== null && sb !== null) ? sa - sb : null;

    // Gap coloring is driven by the weighted gap — weight=0 → always grey.
    const wGap = gap !== null ? gap * w : null;
    let gapCls = "gap-close", gapStr = "—";
    if (gap !== null) {
      gapStr = (gap > 0 ? "+" : "") + Math.round(gap);   // raw number always shown
      if      (wGap >  5) gapCls = "gap-a";
      else if (wGap < -5) gapCls = "gap-b";
    }

    rows += `<tr>
      <td>${dim.name}${wBadge(dim)}</td>
      <td>${sa !== null ? Math.round(sa) : "—"}</td>
      <td>${sb !== null ? Math.round(sb) : "—"}</td>
      <td class="${gapCls}">${gapStr}</td>
    </tr>`;
  }

  wrap.innerHTML = `
    <div class="comparison-card">
      <div class="comparison-header">
        <div class="sim-block">
          <div class="sim-label">Similarity</div>
          <div class="sim-score ${simCls}">${sim !== null ? Math.round(sim) + "%" : "—"}</div>
        </div>
        <div class="sim-desc">
          ${simTxt}<br>
          <span style="font-size:10px;opacity:.7">
            100 − √(weighted mean²-diff across 13 axes)${weightNote} &nbsp;·&nbsp;
            <span class="sim-green">green ≥ 75</span> &nbsp;
            <span class="sim-amber">amber ≥ 55</span> &nbsp;
            <span class="sim-red">red &lt; 55</span>
          </span>
        </div>
      </div>
      <table class="dim-table">
        <thead><tr>
          <th>Dimension</th>
          <th style="color:var(--a)">Player A</th>
          <th style="color:var(--b)">Player B</th>
          <th>Gap (A−B)</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

// ── initial empty state ────────────────────────────────────────────────────
["radar-a","radar-b","radar-overlay"].forEach(id => drawEmpty(id));

// ── render everything ─────────────────────────────────────────────────────
function renderAll() {
  const da = state.a ? PLAYER_DATA[state.a.key] : null;
  const db = state.b ? PLAYER_DATA[state.b.key] : null;

  // Radars — always unweighted raw percentiles
  if (da) drawRadar("radar-a", [{ data: da, color: COLOR_A }]);
  else    drawEmpty("radar-a");

  if (db) drawRadar("radar-b", [{ data: db, color: COLOR_B }]);
  else    drawEmpty("radar-b");

  if (da || db) {
    drawRadar("radar-overlay", [
      da ? { data: da, color: COLOR_A, alpha: 0.15 }               : null,
      db ? { data: db, color: COLOR_B, dashed: true, alpha: 0.10 } : null,
    ].filter(Boolean));
  } else {
    drawEmpty("radar-overlay", "Select two players to overlay");
  }

  // Sidebars + comparison use weights
  renderSidebar("sidebar-a", da, COLOR_A);
  renderSidebar("sidebar-b", db, COLOR_B);
  renderComparison(da, db);
}

// Lightweight re-render for when only weights change (no radar redraw needed).
function renderWeighted() {
  const da = state.a ? PLAYER_DATA[state.a.key] : null;
  const db = state.b ? PLAYER_DATA[state.b.key] : null;
  renderSidebar("sidebar-a", da, COLOR_A);
  renderSidebar("sidebar-b", db, COLOR_B);
  renderComparison(da, db);
  // Update the active-dot indicator on the toggle button
  document.getElementById("weights-active-dot")
    .classList.toggle("visible", anyNonDefault());
}

// ── weight panel setup ─────────────────────────────────────────────────────

function updateSliderFill(slider) {
  const pct = (parseFloat(slider.value) / parseFloat(slider.max)) * 100;
  slider.style.background =
    `linear-gradient(to right, #58a6ff ${pct}%, #21262d ${pct}%)`;
}

function setupWeightPanel() {
  // Toggle open/close
  const toggle = document.getElementById("weights-toggle");
  const body   = document.getElementById("weights-body");
  toggle.addEventListener("click", () => {
    const open = body.classList.toggle("open");
    toggle.classList.toggle("active", open);
    toggle.textContent = "Dimension weights " + (open ? "▴" : "▾");
  });

  // Wire each slider
  for (const dim of DIMS) {
    const slider = document.getElementById("slider-" + dim.key);
    const valEl  = document.getElementById("weight-val-" + dim.key);

    // Set initial fill (1.0 / 3.0 = 33.3%)
    updateSliderFill(slider);

    slider.addEventListener("input", () => {
      const w = parseFloat(slider.value);
      weights[dim.key] = w;
      valEl.textContent = w.toFixed(1) + "×";
      valEl.className   = "weight-val" + (w === 0 ? " zero" : "");
      updateSliderFill(slider);
      renderWeighted();
    });
  }

  // Reset all to 1.0
  document.getElementById("weights-reset").addEventListener("click", () => {
    for (const dim of DIMS) {
      const slider = document.getElementById("slider-" + dim.key);
      const valEl  = document.getElementById("weight-val-" + dim.key);
      slider.value      = "1";
      weights[dim.key]  = 1.0;
      valEl.textContent = "1.0×";
      valEl.className   = "weight-val";
      updateSliderFill(slider);
    }
    renderWeighted();
  });
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
  el.innerHTML = `
    ${sportBadge(entry.sport)}
    <span class="selected-name">${entry.player}</span>
    <span style="color:var(--muted);font-size:11px">${entry.season}</span>
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

  // Sport filter tabs
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
setupWeightPanel();
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
