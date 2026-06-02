"""
fetch_soccer_bio.py — EPL 2022-23 player height + weight from footballdatabase.eu.

footballdatabase.eu carries BOTH height ('1m89') and weight ('74 kg') on every
player profile under div.firstline / div.secondline. Strategy:
  1. PL 2022-23 competition page (ID 22323) → extract all club IDs
  2. Each club's 2022-23 squad page          → collect player profile URLs + names
  3. Each player profile                     → extract height_cm, weight_kg

Run:  python fetch_soccer_bio.py          (resumes from existing CSV if present)
Out:  soccer_bio_2023.csv  (player [diacritic-stripped], height_cm, weight_kg)
"""

import re
import time
import unicodedata
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE  = "https://www.footballdatabase.eu"
PL_ID = "22323-premier_league"   # discovered from FDBEU homepage
DELAY = 0.8

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.footballdatabase.eu/",
}


def normalize_name(name):
    nfkd = unicodedata.normalize("NFKD", str(name))
    return " ".join("".join(c for c in nfkd if not unicodedata.combining(c)).split())


def _parse_height(text):
    """'Height : 1m89' → 189  |  '1.89 m' → 189  |  '189 cm' → 189."""
    m = re.search(r"(\d)m(\d{2})", text)
    if m:
        return int(m.group(1)) * 100 + int(m.group(2))
    m = re.search(r"(\d)[,.](\d{2})\s*m", text)
    if m:
        return round(float(f"{m.group(1)}.{m.group(2)}") * 100)
    m = re.search(r"(\d{2,3})\s*cm", text, re.I)
    if m:
        return int(m.group(1))
    return None


def _parse_weight(text):
    """'Weight : 74 kg' → 74.0."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*kg", text, re.I)
    return float(m.group(1)) if m else None


def _get(session, url, retries=3):
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, headers=HEADERS, timeout=30)
            time.sleep(DELAY)
            r.raise_for_status()
            return r
        except Exception as exc:
            if attempt == retries:
                raise
            wait = 2 ** attempt
            print(f"    retry {attempt} ({type(exc).__name__}), waiting {wait}s…")
            time.sleep(wait)


def get_clubs(session):
    """Return {club_id: slug} from the PL 2022-23 competition page."""
    url = f"{BASE}/en/competition/overall/{PL_ID}/2022-2023"
    soup = BeautifulSoup(_get(session, url).text, "lxml")
    clubs = {}
    for a in soup.select('a[href*="/club/team/"]'):
        m = re.search(r'/club/team/(\d+)-([\w_]+)/', a["href"])
        if m:
            clubs[m.group(1)] = m.group(2)
    return clubs


def get_squad_players(session, club_id, slug):
    """Return {profile_url: normalized_name} from a club's 2022-23 squad page."""
    url = f"{BASE}/en/club/team/{club_id}-{slug}/2022-2023"
    soup = BeautifulSoup(_get(session, url).text, "lxml")
    players = {}
    for a in soup.select('a[href*="/player/details/"]'):
        href  = a["href"]
        name  = normalize_name(a.get_text(strip=True))
        if name and href.startswith("/"):
            players[BASE + href] = name
    return players


def get_bio(session, url):
    """Fetch one player profile, return (height_cm, weight_kg)."""
    try:
        soup = BeautifulSoup(_get(session, url).text, "lxml")
    except Exception:
        return None, None
    height_cm = weight_kg = None
    for div in soup.select("div.firstline, div.secondline"):
        text = div.get_text(" ", strip=True)
        if "Height" in text and height_cm is None:
            height_cm = _parse_height(text)
        if "Weight" in text and weight_kg is None:
            weight_kg = _parse_weight(text)
    return height_cm, weight_kg


def main():
    out_path = Path("soccer_bio_2023.csv")

    # Resume from previous run (match by player name)
    results: list[dict] = []
    done_names: set[str] = set()
    if out_path.exists():
        existing = pd.read_csv(out_path)
        results    = existing.to_dict("records")
        done_names = {r["player"] for r in results}
        print(f"Resuming — {len(done_names)} players already cached")

    session = requests.Session()

    # ── Step 1: competition page → club IDs ───────────────────────────────────
    print("Step 1: fetching PL 2022-23 club list…")
    clubs = get_clubs(session)
    print(f"  {len(clubs)} clubs: {list(clubs.values())[:5]} …")

    # ── Step 2: squad pages → player URLs ─────────────────────────────────────
    print("Step 2: collecting player profiles from squad pages…")
    all_players: dict[str, str] = {}   # profile_url → normalized_name
    for i, (cid, slug) in enumerate(clubs.items(), 1):
        pl = get_squad_players(session, cid, slug)
        all_players.update(pl)
        print(f"  [{i:2d}/{len(clubs)}] {slug:30s} +{len(pl):3d}  total {len(all_players)}")

    # ── Step 3: profile pages → height + weight ───────────────────────────────
    to_fetch = {url: name for url, name in all_players.items()
                if name not in done_names}
    print(f"\nStep 3: fetching bios for {len(to_fetch)} players "
          f"({len(done_names)} already cached)…")

    for i, (url, name) in enumerate(to_fetch.items(), 1):
        h, w = get_bio(session, url)
        results.append({"player": name, "height_cm": h, "weight_kg": w})
        if i % 50 == 0 or i == len(to_fetch):
            print(f"  {i}/{len(to_fetch)}")
            (pd.DataFrame(results)[["player", "height_cm", "weight_kg"]]
             .drop_duplicates(subset=["player"])
             .to_csv(out_path, index=False))

    # ── Final save ────────────────────────────────────────────────────────────
    df = pd.DataFrame(results)[["player", "height_cm", "weight_kg"]]
    df = df.drop_duplicates(subset=["player"])
    df.to_csv(out_path, index=False)

    # ── Match-rate report (direct-name only; token-sort recovers more) ─────────
    soccer    = pd.read_csv("soccer_merged.csv")
    s_keys    = {normalize_name(n) for n in soccer["player"]}
    b_keys    = set(df["player"])
    matched   = s_keys & b_keys
    unmatched = s_keys - b_keys

    print(f"\nWrote {len(df)} players → {out_path}")
    print(f"  height: {df['height_cm'].notna().sum()}/{len(df)} "
          f"  weight: {df['weight_kg'].notna().sum()}/{len(df)}")
    print(f"Direct name match vs soccer_merged: "
          f"{len(matched)}/{len(s_keys)} ({100*len(matched)/len(s_keys):.1f}%)")
    print("(token-sort in ingest_data.py recovers name-order mismatches)")
    if unmatched:
        print(f"Still unmatched ({len(unmatched)}):")
        for n in sorted(unmatched)[:20]:
            print(f"  {n}")


if __name__ == "__main__":
    main()
