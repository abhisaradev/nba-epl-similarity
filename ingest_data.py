"""
ingest_data.py — registry-driven ingest: merge a dataset's raw league tables
(FBref soccer or BBRef NBA) into one wide processed CSV.

Filenames come from datasets.py, never hardcoded here, so a new league-season is
just a new registry entry. build(dataset_id) dispatches by sport and writes
processed/<id>.csv (plus backward-compat soccer.csv / nba.csv aliases).

Run:  python ingest_data.py            # builds every dataset in the registry
Out:  processed/<id>.csv  (+ soccer.csv, nba.csv, *_merged.csv aliases)
"""

import os
import unicodedata
import pandas as pd

import datasets


def _normalize_name(name):
    """Strip diacritics: Dončić → Doncic, Jokić → Jokic."""
    nfkd = unicodedata.normalize("NFKD", str(name))
    return " ".join("".join(c for c in nfkd if not unicodedata.combining(c)).split())


def _token_sort_key(name):
    """Sort tokens alphabetically so reordered names collide.
    'Son Heung-min' → 'heung-min son'  ==  'Heung-Min Son' → 'heung-min son'
    """
    return " ".join(sorted(_normalize_name(name).lower().split()))


# Manual bridge for players whose FBref display name shares no token with their
# FIFA `long_name` (legal/registered name), so neither the token-sort nor the
# subset fallback can connect them. Key = exact FBref `player`; value = exact
# FIFA `long_name` in soccer_bio_2023.csv. Applied BEFORE the token-sort match.
#
# Six other unmatched FBref players — Kaoru Mitoma, Kobbie Mainoo, Jarell
# Quansah, Son Heung-min, Takehiro Tomiyasu, Wataru Endo — have NO row in FIFA 23
# under any update (2023-24 arrivals the 2022 game predates), so they can't be
# aliased and stay without bio height/weight.
ALIAS_FBREF_TO_FIFA = {
    "Beto":      "Norberto Bercique Gomes Betuncal",
    "Casemiro":  "Carlos Henrique Venancio Casimiro",
    "Igor":      "Igor Júlio dos Santos de Paulo",
    "Jorginho":  "Luiz Frello Filho Jorge",
    "José Sá":   "José Pedro Malheiro de Sá",
    "Luis Díaz": "Luis Fernando Díaz Marulanda",
    "Matz Sels": "Matz Willy Els Sels",
    "Neto":      "Norberto Murara Neto",
    "Ola Aina":  "Temitayo Olufisayo Olaoluwa Aina",
    "Rodri":     "Rodrigo Hernández Cascante",
    "Tim Ream":  "Timothy Michael Ream",
    "Vitinho":   "Victor Alexander da Silva",
}


def _interior_score(df, neg_col, pos_col):
    """DISPLAY-ONLY paint/box dominance, 0-100. Mean of two within-table
    percentiles: the inverse of `neg_col` (smaller = more interior) and `pos_col`
    (larger = more interior). NOT a similarity input — radar/breakdown readout
    only, so location still SHOWS now that it's folded inside scoring_threat."""
    neg = pd.to_numeric(df[neg_col], errors="coerce")
    pos = pd.to_numeric(df[pos_col], errors="coerce")
    pct = pd.concat([(-neg).rank(pct=True), pos.rank(pct=True)], axis=1)
    return pct.mean(axis=1) * 100.0


# ─── FBref helpers ────────────────────────────────────────────────────────────

_EPL_META = {"Rk", "Nation", "Pos", "Squad", "Age", "Born", "90s", "Matches"}


def _load_fbref(path):
    # Read header separately to fix FBref's occasional newline+▲ in "Player"
    with open(path) as fh:
        raw_cols = fh.readline()
    # Re-read with cleaned column names via a names= pass isn't easy, so
    # we read normally and patch afterward.
    df = pd.read_csv(path, thousands=",")
    df.columns = [c.replace("\n▲", "").replace("\n", " ").strip() for c in df.columns]
    # Drop repeated header rows (FBref sometimes embeds them mid-file)
    if "Rk" in df.columns:
        df = df[pd.to_numeric(df["Rk"], errors="coerce").notna()].copy()
    df = df.drop(columns=["Matches"], errors="ignore")
    return df


def _strip_meta(df):
    """Remove shared metadata cols so they don't collide during merge."""
    return df.drop(columns=[c for c in _EPL_META - {"Player"} if c in df.columns])


# ── EPL table loaders ─────────────────────────────────────────────────────────

def _load_epl_main(path):
    df = _load_fbref(path)
    # Pandas auto-suffixes duplicate column names (.1, .2 …).
    # Cols 26-35 are per-90 repeats of the season-total cols 11-25.
    df = df.rename(columns={
        "Gls.1":       "Gls/90",
        "Ast.1":       "Ast/90",
        "G+A.1":       "G+A/90",
        "G-PK.1":      "G-PK/90",
        "G+A-PK":      "G+A-PK/90",   # unique name but lives in the per-90 block
        "xG.1":        "xG/90",
        "xAG.1":       "xAG/90",
        "xG+xAG":      "xG+xAG/90",   # unique name; per-90 block only
        "npxG.1":      "npxG/90",
        "npxG+xAG.1":  "npxG+xAG/90",
    })
    return df


def _load_shooting(path):
    df = _load_fbref(path)
    df = df.rename(columns={
        "Gls":   "Gls_sh",
        "PK":    "PK_sh",
        "PKatt": "PKatt_sh",
        "xG":    "xG_sh",
        "npxG":  "npxG_sh",
    })
    return _strip_meta(df)


def _load_defensive(path):
    df = _load_fbref(path)
    # Tkl appears twice: col 8 = total tackles, col 13 (Tkl.1) = dribblers tackled.
    # Remaining renamed cols are all unique within this file.
    df = df.rename(columns={
        "Def 3rd":   "Tkl_Def3rd",
        "Mid 3rd":   "Tkl_Mid3rd",
        "Att 3rd":   "Tkl_Att3rd",
        "Tkl.1":     "Tkl_Drib",
        "Att":       "Att_Drib",
        "Tkl%":      "TklChallenge%",
        "Lost":      "Lost_Drib",
        "Sh":        "Sh_Blk",
        "Pass":      "Pass_Blk",
    })
    return _strip_meta(df)


def _load_gsc(path):
    """Goal and Shot Creation."""
    df = _load_fbref(path)
    df = df.rename(columns={
        "PassLive":   "SCA_PassLive",
        "PassDead":   "SCA_PassDead",
        "TO":         "SCA_TO",
        "Sh":         "SCA_Sh",
        "Fld":        "SCA_Fld",
        "Def":        "SCA_Def",
        "PassLive.1": "GCA_PassLive",
        "PassDead.1": "GCA_PassDead",
        "TO.1":       "GCA_TO",
        "Sh.1":       "GCA_Sh",
        "Fld.1":      "GCA_Fld",
        "Def.1":      "GCA_Def",
    })
    return _strip_meta(df)


def _load_passing(path):
    df = _load_fbref(path)
    # Cmp, Att, Cmp% each appear 4x (Total / Short / Medium / Long).
    # pandas names them Cmp, Cmp.1, Cmp.2, Cmp.3 etc.
    df = df.rename(columns={
        "Cmp":       "Cmp_Total",
        "Att":       "Att_Total",
        "Cmp%":      "Cmp%_Total",
        "TotDist":   "Pass_TotDist",
        "PrgDist":   "Pass_PrgDist",
        "Cmp.1":     "Cmp_Short",
        "Att.1":     "Att_Short",
        "Cmp%.1":    "Cmp%_Short",
        "Cmp.2":     "Cmp_Med",
        "Att.2":     "Att_Med",
        "Cmp%.2":    "Cmp%_Med",
        "Cmp.3":     "Cmp_Long",
        "Att.3":     "Att_Long",
        "Cmp%.3":    "Cmp%_Long",
        "Ast":       "Ast_Pass",
        "xAG":       "xAG_Pass",
        "PrgP":      "PrgP_Pass",
        "1/3":       "Pass_1_3",
    })
    return _strip_meta(df)


def _load_possession(path):
    df = _load_fbref(path)
    df = df.rename(columns={
        "Def 3rd":  "Touch_Def3rd",
        "Mid 3rd":  "Touch_Mid3rd",
        "Att 3rd":  "Touch_Att3rd",
        "Att":      "Att_Dribble",
        "Succ":     "Succ_Dribble",
        "TotDist":  "Carry_TotDist",
        "PrgDist":  "Carry_PrgDist",
        "PrgC":     "PrgC_Carry",
        "1/3":      "Carry_1_3",
        "PrgR":     "PrgR_Poss",
    })
    return _strip_meta(df)


def _load_misc(path):
    df = _load_fbref(path)
    # CrdY/CrdR/Int/TklW also appear in the main/defensive tables; suffix to avoid clash.
    df = df.rename(columns={
        "CrdY": "CrdY_misc",
        "CrdR": "CrdR_misc",
        "Fld":  "Fld_misc",
        "Int":  "Int_misc",
        "TklW": "TklW_misc",
        "Lost": "AerialLost",
    })
    return _strip_meta(df)


# ── EPL merge ─────────────────────────────────────────────────────────────────

def _dedup_fbref(df):
    """FBref lists separate rows per club for mid-season transfers.
    Keep one row per player: the one with the most minutes played."""
    df["_min_num"] = pd.to_numeric(df["Min"], errors="coerce").fillna(0)
    df = df.sort_values("_min_num", ascending=False)
    df = df.drop_duplicates(subset=["Player"], keep="first")
    return df.drop(columns=["_min_num"])


def build_soccer(paths):
    base = _dedup_fbref(_load_epl_main(paths["main"]))
    extras = [
        _load_shooting(paths["shooting"]),
        _load_defensive(paths["defensive"]),
        _load_gsc(paths["gsc"]),
        _load_passing(paths["passing"]),
        _load_possession(paths["possession"]),
        _load_misc(paths["misc"]),
    ]
    df = base
    for extra in extras:
        # Dedup each supplemental table on Player before merging
        extra = extra.drop_duplicates(subset=["Player"], keep="first")
        df = df.merge(extra, on="Player", how="outer")
    df = df.rename(columns={"Player": "player", "Min": "minutes"})

    # ── merge bio (height + weight from the FIFA dataset) ────────────────────
    bio_path = paths.get("bio")
    if bio_path and os.path.exists(bio_path):
        bio = pd.read_csv(bio_path)
        # Primary key: token-sorted name  ('Son Heung-min' == 'Heung-Min Son').
        # Aliased players key off their mapped FIFA long_name so they match
        # directly; everyone else keys off their own FBref name.
        df["_tskey"]  = df["player"].apply(
            lambda p: _token_sort_key(ALIAS_FBREF_TO_FIFA.get(p, p)))
        bio["_tskey"] = bio["player"].apply(_token_sort_key)
        bio_cols = bio.drop(columns=["player"])

        # Token-sort keys can collide across distinct bio players; collapse them
        # so the left-merge can't fan one soccer row out into many duplicates.
        n_keys = len(bio_cols)
        bio_cols = bio_cols.drop_duplicates(subset=["_tskey"], keep="first")
        if len(bio_cols) < n_keys:
            print(f"  bio: collapsed {n_keys - len(bio_cols)} duplicate token-sort keys")

        n_before = len(df)
        df = df.merge(bio_cols, on="_tskey", how="left")

        # Subset fallback: handles single-name players ('Gabriel' ⊆ 'Gabriel Magalhaes')
        h_col = "height_cm"
        if h_col in df.columns:
            unmatched_idx = df.index[df[h_col].isna()]
            if len(unmatched_idx):
                # Build index keyed by ALL individual tokens of each bio player
                tok_to_bio: dict[str, dict] = {}
                for _, row in bio_cols.iterrows():
                    for tok in row["_tskey"].split():
                        if len(tok) > 4:   # skip short tokens to avoid false matches
                            tok_to_bio.setdefault(tok, row.to_dict())

                for idx in unmatched_idx:
                    player_tokens = df.loc[idx, "_tskey"].split()
                    for tok in player_tokens:
                        if len(tok) > 4 and tok in tok_to_bio:
                            for col, val in tok_to_bio[tok].items():
                                if col != "_tskey" and col in df.columns:
                                    df.loc[idx, col] = val
                            break   # use first match only

        df = df.drop(columns=["_tskey"])
        n_after = len(df)
        print(f"  soccer rows: {n_before} before bio merge -> {n_after} after")
        if n_after != n_before:
            raise SystemExit(
                f"bio merge changed row count {n_before} -> {n_after}: name match "
                "duplicated players. Fix the join before continuing."
            )
        h_ok = df["height_cm"].notna().sum() if "height_cm" in df.columns else 0
        w_ok = df["weight_kg"].notna().sum() if "weight_kg" in df.columns else 0
        print(f"  bio merge: height {h_ok}/{len(df)}, weight {w_ok}/{len(df)}")

    # ── derived columns (metric bio → imperial for config + convenience metric) ─
    if "height_cm" in df.columns:
        df["height_in"] = df["height_cm"] / 2.54
    if "weight_kg" in df.columns:
        df["weight_lbs"] = df["weight_kg"] * 2.20462
    if "height_in" in df.columns and "weight_lbs" in df.columns:
        df["bmi"] = float("nan")
        mask = df["height_in"].notna() & df["weight_lbs"].notna() & (df["height_in"] > 0)
        if mask.any():
            df.loc[mask, "bmi"] = (
                703 * df.loc[mask, "weight_lbs"] / df.loc[mask, "height_in"] ** 2
            )

    # DISPLAY-ONLY interior score (see _interior_score). Not a similarity input.
    if "Dist" in df.columns and "npxG/Sh" in df.columns:
        df["interior_score"] = _interior_score(df, "Dist", "npxG/Sh")

    return df


# ── NBA helpers ───────────────────────────────────────────────────────────────

_NBA_META = {"Rk", "Age", "Team", "Pos", "G", "GS", "MP"}


def _load_nba_raw(path):
    df = pd.read_csv(path, thousands=",")
    if "Rk" in df.columns:
        df = df[pd.to_numeric(df["Rk"], errors="coerce").notna()].copy()
    return df


def _dedup_nba(df):
    """For mid-season trades BBRef emits one row per team plus a season-total row.
    Keep the total row (Team ∈ {2TM, 3TM, 4TM, TOT}); keep single rows untouched."""
    multi = df.duplicated(subset=["Player"], keep=False)
    singles = df[~multi]
    dups = df[multi]
    totals = dups[dups["Team"].isin(["2TM", "3TM", "4TM", "TOT"])]
    # Fallback: any dup without a total row — keep first occurrence
    covered = set(totals["Player"])
    fallback = dups[~dups["Player"].isin(covered)].drop_duplicates(subset=["Player"], keep="first")
    return pd.concat([singles, totals, fallback], ignore_index=True)


def build_nba(paths):
    per_game = _dedup_nba(_load_nba_raw(paths["per_game"]))

    # Two-file source (bbref: per-game + advanced as separate CSVs) -> merge them.
    # Single-file source (nba_api: base+advanced already combined) -> skip the
    # merge; both registry keys point at the same file. Everything downstream is
    # identical either way.
    if paths.get("advanced") and paths["advanced"] != paths["per_game"]:
        advanced = _dedup_nba(_load_nba_raw(paths["advanced"]))
        # Drop metadata + Awards from advanced before merge to avoid duplicates
        adv_drop = [c for c in _NBA_META if c in advanced.columns] + ["Awards"]
        advanced = advanced.drop(columns=adv_drop, errors="ignore")
        df = per_game.merge(advanced, on="Player", how="outer")
    else:
        df = per_game

    # Numeric conversions for derived columns
    for col in ["AST", "TOV", "MP", "G", "FGA", "3PA", "FTA"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["ast_to_tov"] = df["AST"] / df["TOV"].replace(0, float("nan"))
    df["total_minutes"] = df["MP"] * df["G"]

    # Shot-location rates from the per-game stats (recomputed here so they share
    # one definition with the soccer side; FGA==0 -> NaN guards divide-by-zero).
    # These overwrite BBRef's Advanced-table 3PAr/FTr, which are season-total
    # based and drift slightly from per-game 3PA/FGA.
    fga = df["FGA"].replace(0, float("nan"))
    df["3PAr"] = df["3PA"] / fga   # three-point attempt rate; lower = more interior
    df["FTr"]  = df["FTA"] / fga   # free-throw rate;          higher = attacks rim

    df = df.rename(columns={"Player": "player", "total_minutes": "minutes"})

    # ── merge tracking stats if available ────────────────────────────────────
    tracking_path = paths.get("tracking")
    if tracking_path and os.path.exists(tracking_path):
        tracking = pd.read_csv(tracking_path)
        # Both sides normalised: BBRef names are already ASCII; nba.com may have
        # accents (Dončić). _normalize_name strips diacritics on both sides.
        df["_key"] = df["player"].apply(_normalize_name)
        tracking["_key"] = tracking["player"].apply(_normalize_name)
        tracking = tracking.drop(columns=["player"])

        tracking_keys = set(tracking["_key"])
        bbref_keys = set(df["_key"])
        unmatched = tracking_keys - bbref_keys
        print(f"  tracking merge: {len(tracking)} rows, "
              f"{len(unmatched)} failed to match BBRef names")
        if unmatched:
            print(f"  unmatched sample: {sorted(unmatched)[:10]}")

        df = df.merge(tracking, on="_key", how="left")
        df = df.drop(columns=["_key"])

    # ── merge bio (height / weight) ───────────────────────────────────────────
    bio_path = paths.get("bio")
    if bio_path and os.path.exists(bio_path):
        bio = pd.read_csv(bio_path)
        df["_tskey"]  = df["player"].apply(_token_sort_key)
        bio["_tskey"] = bio["player"].apply(_token_sort_key)
        bio = bio.drop(columns=["player"])
        df = df.merge(bio, on="_tskey", how="left")
        df = df.drop(columns=["_tskey"])
        print(f"  bio merge: height {df['height_in'].notna().sum()}/{len(df)}, "
              f"weight {df['weight_lbs'].notna().sum()}/{len(df)}")

    # ── derived columns ───────────────────────────────────────────────────────
    if "height_in" in df.columns and "weight_lbs" in df.columns:
        df["height_cm"] = df["height_in"] * 2.54
        df["weight_kg"] = df["weight_lbs"] / 2.20462
        mask = df["height_in"].notna() & df["weight_lbs"].notna() & (df["height_in"] > 0)
        df["bmi"] = float("nan")
        df.loc[mask, "bmi"] = (
            703 * df.loc[mask, "weight_lbs"] / df.loc[mask, "height_in"] ** 2
        )

    # DISPLAY-ONLY interior score (see _interior_score). Not a similarity input.
    df["interior_score"] = _interior_score(df, "3PAr", "FTr")

    return df


# ── main ──────────────────────────────────────────────────────────────────────

POOL_MIN = 900            # the comparison pool: soccer players with >= 900 minutes
WEIGHT_GATE_PCT = 85.0    # below this, bio coverage is too thin to run comps


def _gate(soccer):
    """Print bio coverage over the 900-minute comp pool and refuse to proceed
    if weight coverage is too thin to trust the physicality axis."""
    mins = pd.to_numeric(soccer["minutes"], errors="coerce")
    pool = soccer[mins >= POOL_MIN]
    n = len(pool)
    h_pct = pool["height_cm"].notna().mean() * 100 if n else 0.0
    w_pct = pool["weight_kg"].notna().mean() * 100 if n else 0.0
    b_pct = pool["bmi"].notna().mean() * 100 if n else 0.0
    print(f"\nGATE — bio coverage over the {POOL_MIN}-minute pool ({n} qualified players):")
    print(f"  height: {h_pct:5.1f}%    weight: {w_pct:5.1f}%    bmi: {b_pct:5.1f}%")
    missing = pool[pool["height_cm"].isna() | pool["weight_kg"].isna()]
    if len(missing):
        print(f"  {len(missing)} qualified player(s) still missing height/weight:")
        for nm in sorted(missing["player"]):
            print(f"    - {nm}")
    else:
        print("  every qualified player has height + weight")
    if w_pct < WEIGHT_GATE_PCT:
        raise SystemExit(
            f"\nGATE FAILED: weight coverage {w_pct:.1f}% < {WEIGHT_GATE_PCT}% — "
            "stopping before comps. Fix bio coverage first."
        )
    print("  GATE PASSED.\n")


# Backward-compat output aliases so similarity.py / cluster.py keep reading the
# same fixed filenames they always have (untouched this stage).
# nba_2324 (nba_api, 2023-24) is THE canonical NBA table for similarity/cluster,
# pairing with the 2023-24 EPL data. (Was the retired bbref nba_2223.)
_ALIASES = {
    "epl_2324": ["soccer.csv", "soccer_merged.csv"],
    "nba_2324": ["nba.csv", "nba_merged.csv"],
}


def build(dataset_id):
    """Registry-driven build: resolve this dataset's table paths from datasets.py,
    dispatch to the soccer or nba build path by sport, and write processed/<id>.csv
    (plus any backward-compat aliases). Returns the processed dataframe."""
    d = datasets.get(dataset_id)
    paths = {tbl: datasets.raw_path(dataset_id, tbl) for tbl in d["tables"]}
    print(f"Building {dataset_id}  (sport={d['sport']}, season={d.get('true_season','?')})…")

    if d["sport"] == "soccer":
        df = build_soccer(paths)
        _gate(df)   # bio-coverage gate; doesn't mutate df, raises if too thin
    elif d["sport"] == "nba":
        df = build_nba(paths)
    else:
        raise ValueError(f"unknown sport {d['sport']!r} for dataset {dataset_id!r}")

    out = datasets.processed_path(dataset_id)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    df.to_csv(out, index=False)
    for alias in _ALIASES.get(dataset_id, []):
        df.to_csv(alias, index=False)

    n = df["player"].nunique()
    print(f"  {n} players  →  {out}  ({len(df.columns)} columns)\n")
    return df


if __name__ == "__main__":
    for ds in datasets.DATASETS:
        build(ds)
