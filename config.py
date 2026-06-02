"""
config.py — Dimension schema for the NBA <> EPL cross-sport similarity model.

  * Dimensions defined PER SPORT; normalization happens within-sport.
  * volume vs efficiency kept as SEPARATE axes (the Curry rule).
  * `inverse` stats: lower is better; sign flipped during normalization.
  * `status`: "core" ships now; "v2" is roadmap, stubbed so it isn't forgotten.

athleticism_stature was SPLIT (Kante problem) into:
  * physicality  — what you're BUILT like (aerials + height/weight/BMI)
  * engine       — how much you MOTOR (recoveries / hustle activity)
Touches was removed from the physical group (it's involvement, already counted
in possession_security and double-counting dragged attackers toward low-usage
NBA shooters).

Height/weight/BMI columns (height_in, weight_lbs, bmi) are populated by the
fetch step. Until then pipeline skips them automatically, so physicality runs
on aerials alone and fills in once the data lands. BMI (imperial) =
703 * weight_lbs / height_in**2 — the mass-for-frame "build" signal: 5'8"/140
reads denser/stronger than 6'0"/140, exactly as intended.
"""

INVERSE_STATS = {
    # soccer
    "Mis", "Dis", "Err", "Dist",
    # nba
    "TOV%", "TOV", "DEF_RATING", "3PAr",   # fewer threes (lower 3PAr) = more interior
}

# Manual per-dimension multipliers. ALL 1.0 = inert (no effect). Bump one and
# re-run to hand-weight a dimension, e.g. "scoring_threat": 2.0.
DIMENSION_WEIGHTS = {
    "scoring_threat": 1.0,
    "playmaking": 1.0,
    "ball_progression": 1.0,
    "possession_security": 1.0,
    "defensive_effectiveness": 1.0,
    "physicality": 1.0,
    "engine": 1.0,
}

DIMENSIONS = {
    "scoring_threat": {
        # Shot LOCATION is folded into efficiency (not a standalone axis): a
        # standalone interior axis pulled high-volume scorers toward low-usage
        # putback centers (Capela-types). Inside scoring_threat — alongside the
        # volume axis — interior dominance only rewards players who also score in
        # volume, so Giannis-types separate from rim-runners correctly.
        #   soccer interior: Dist (inverse, close range) + npxG/Sh (chance quality)
        #   nba interior:    3PAr (inverse, fewer threes) + FTr (attacks the rim)
        "tier": 1, "status": "core",
        "soccer": {"volume": ["Sh/90", "SoT/90", "npxG/90"],
                   "efficiency": ["G/Sh", "G/SoT", "SoT%", "Dist", "npxG/Sh"]},
        "nba":    {"volume": ["FGA", "PTS", "3PA"],
                   "efficiency": ["TS%", "eFG%", "3P%", "3PAr", "FTr"]},
    },
    "playmaking": {
        "tier": 1, "status": "core",
        "soccer": {"volume": ["xA", "KP", "SCA90"],
                   "efficiency": ["PPA", "CrsPA", "GCA90"]},
        "nba":    {"volume": ["AST", "POTENTIAL_AST"],
                   "efficiency": ["AST%", "ast_to_tov"]},
    },
    "ball_progression": {
        "tier": 1, "status": "core",
        "soccer": {"volume": ["PrgC", "PrgP", "PrgR"],
                   "efficiency": ["CPA", "Succ%"]},
        "nba":    {"volume": ["DRIVES", "TOUCHES"],
                   "efficiency": ["PTS_PER_TOUCH", "DRIVE_FG_PCT"]},
    },
    "possession_security": {
        "tier": 1, "status": "core",
        "soccer": {"volume": ["Touches"],
                   "efficiency": ["Cmp%_Total", "Mis", "Dis", "Cmp%_Short", "Cmp%_Long"]},
        "nba":    {"volume": ["TOUCHES"],
                   "efficiency": ["TOV%", "ast_to_tov"]},
    },
    "defensive_effectiveness": {
        "tier": 1, "status": "core",
        "soccer": {"volume": ["Int", "Clr", "Blocks"],
                   "efficiency": ["TklChallenge%", "Won%", "Err"]},
        "nba":    {"volume": ["STL", "BLK", "DEF_RATING"],
                   "efficiency": ["DBPM", "DRB%", "CONTESTED_SHOTS"]},
    },

    # --- SPLIT: physique vs motor ---
    "physicality": {
        "tier": 1, "status": "core",
        "soccer": {"volume": ["Won", "height_in", "weight_lbs", "bmi"],
                   "efficiency": ["Won%"]},
        "nba":    {"volume": ["TRB", "height_in", "weight_lbs", "bmi"],
                   "efficiency": ["DRB%"]},
    },
    "engine": {
        "tier": 1, "status": "core",
        "soccer": {"volume": ["Recov"], "efficiency": []},
        "nba":    {"volume": ["CONTESTED_SHOTS", "BOX_OUTS"], "efficiency": []},
    },

    # ----------------------------------------------------------- v2 roadmap
    "speed_acceleration": {  # NBA SpeedDistance + soccer tracking; deferred
        "tier": 2, "status": "v2", "source": "deferred — tracking data",
        "soccer": {"volume": [], "efficiency": []},
        "nba":    {"volume": [], "efficiency": []},
    },
    "playstyle_role": {  # emerges from clustering, not an input
        "tier": 2, "status": "v2", "source": "derived — clustering (v2)",
        "soccer": {"volume": [], "efficiency": []},
        "nba":    {"volume": [], "efficiency": []},
    },
    "dominance": {  # accolade scrape; display layer
        "tier": 2, "status": "v2", "source": "accolade scrape",
        "soccer": {"volume": ["motm", "trophies", "top5_finishes"], "efficiency": []},
        "nba":    {"volume": ["all_nba", "all_star", "award_shares"], "efficiency": []},
    },
}


def core_dimensions():
    return {k: v for k, v in DIMENSIONS.items() if v["status"] == "core"}


def stat_columns(dimension, sport, kind):
    return DIMENSIONS[dimension][sport].get(kind, [])
