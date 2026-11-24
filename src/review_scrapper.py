"""
collect_reviews.py
Collect English Steam reviews for several games and save them to CSV.

- Uses Steam's public appreviews endpoint (no API key needed).
- Pages from newest to oldest and keeps at most N reviews per month, so the
  sample is balanced over time instead of dominated by launch week.
- Saves a checkpoint after every page, so you can stop (Ctrl+C) and re-run
  the same command to resume.
- Does NOT store usernames or Steam IDs, only review text and metadata.

Usage examples (run from the repo root):
    python src/collect_reviews.py --games nms --max-pages 5      # quick test
    python src/collect_reviews.py --games nms cyberpunk
    python src/collect_reviews.py                                # all games
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from urllib.parse import quote


GAMES = {
    "nms":        {"appid": 275850,  "name": "No Man's Sky",     "since": "2016-08-01"},
    "cyberpunk":  {"appid": 1091500, "name": "Cyberpunk 2077",   "since": "2020-12-01"},
    "helldivers": {"appid": 553850,  "name": "Helldivers 2",     "since": "2024-02-01"},
    "bf2042":     {"appid": 1517290, "name": "Battlefield 2042", "since": "2021-11-01"},
    "stardew":    {"appid": 413150,  "name": "Stardew Valley",   "since": "2016-02-01"},
}

URL = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"
FIELDS = [
    "recommendationid", "game", "appid", "created_utc", "month", "voted_up",
    "votes_up", "votes_funny", "playtime_at_review_min", "playtime_forever_min",
    "steam_purchase", "received_for_free", "early_access", "review",
]


def fetch_page(session, appid, cursor, retries=5):
    # The new API takes its parameters as one JSON blob in `input_json`
    input_json = {
        "appid": appid,
        "filter": 1,               # 1 = Recent (newest first), use for paging everything
        "languages": ["english"],
        "review_type": 0,          # 0 = all (positive and negative)
        "purchase_type": 1,        # 1 = all purchase types (0 = Steam purchases only)
        "num_per_page": 100,
        "cursor": cursor,
    }
    url = URL
    for attempt in range(retries):
        try:
            r = session.get(url, params={"input_json": json.dumps(input_json)},
                            timeout=30, allow_redirects=False)
            if 300 <= r.status_code < 400:
                print(f"  redirected: HTTP {r.status_code} -> {r.headers.get('Location')}")
                print(f"  requested: {url}")
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"  rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            if r.status_code != 200 or not r.text.strip().startswith("{"):
                snippet = r.text.strip()[:200].replace("\n", " ")
                print(f"  unexpected response: HTTP {r.status_code}, "
                      f"content-type={r.headers.get('Content-Type')}, "
                      f"body starts: {snippet!r}")
                print(f"  url: {r.url}")
                time.sleep(5 * (attempt + 1))
                continue
            payload = r.json()
            return payload.get("response", payload)
        except (requests.RequestException, ValueError) as e:
            wait = 5 * (attempt + 1)
            print(f"  request failed ({e}); retrying in {wait}s")
            time.sleep(wait)
    return None


def load_state(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"cursor": "*", "month_counts": {}, "pages": 0, "done": False}


def save_state(path, state):
    path.write_text(json.dumps(state), encoding="utf-8")


def collect_game(key, cfg, out_dir, cap_per_month, max_pages, delay):
    csv_path = out_dir / f"{key}_reviews.csv"
    state_path = out_dir / f"{key}_state.json"
    state = load_state(state_path)

    if state["done"]:
        print(f"{cfg['name']}: already finished (delete {state_path.name} to redo)")
        return

    since_ts = datetime.fromisoformat(cfg["since"]).replace(tzinfo=timezone.utc).timestamp()
    new_file = not csv_path.exists()
    session = requests.Session()
    session.headers.update({
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
    })

    print(f"\n=== {cfg['name']} (appid {cfg['appid']}) ===")
    pages_this_run = 0

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()

        while True:
            if max_pages and pages_this_run >= max_pages:
                print("  reached --max-pages, stopping (re-run to resume)")
                break

            data = fetch_page(session, cfg["appid"], state["cursor"])
            if not data:
                print("  no valid response, stopping (re-run to resume)")
                break

            reviews = data.get("reviews", [])
            next_cursor = data.get("cursor")
            if not reviews or not next_cursor or next_cursor == state["cursor"]:
                state["done"] = True
                save_state(state_path, state)
                print("  reached the end of available reviews")
                break

            oldest_ts = None
            for rv in reviews:
                ts = rv.get("timestamp_created", 0)
                oldest_ts = ts if oldest_ts is None else min(oldest_ts, ts)
                text = (rv.get("review") or "").strip()
                if not text:
                    continue
                month = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m")
                if state["month_counts"].get(month, 0) >= cap_per_month:
                    continue
                author = rv.get("author", {})
                writer.writerow({
                    "recommendationid": rv.get("recommendationid"),
                    "game": cfg["name"],
                    "appid": cfg["appid"],
                    "created_utc": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
                    "month": month,
                    "voted_up": rv.get("voted_up"),
                    "votes_up": rv.get("votes_up"),
                    "votes_funny": rv.get("votes_funny"),
                    "playtime_at_review_min": author.get("playtime_at_review"),
                    "playtime_forever_min": author.get("playtime_forever"),
                    "steam_purchase": rv.get("steam_purchase"),
                    "received_for_free": rv.get("received_for_free"),
                    "early_access": rv.get("written_during_early_access"),
                    "review": text,
                })
                state["month_counts"][month] = state["month_counts"].get(month, 0) + 1

            f.flush()
            state["cursor"] = next_cursor
            state["pages"] += 1
            pages_this_run += 1
            save_state(state_path, state)

            total = sum(state["month_counts"].values())
            when = datetime.fromtimestamp(oldest_ts, tz=timezone.utc).strftime("%Y-%m-%d")
            print(f"  page {state['pages']}: kept {total} reviews so far (oldest seen {when})")

            if oldest_ts is not None and oldest_ts < since_ts:
                state["done"] = True
                save_state(state_path, state)
                print(f"  passed the start date {cfg['since']}, done")
                break

            time.sleep(delay)


def main():
    p = argparse.ArgumentParser(description="Collect Steam reviews")
    p.add_argument("--games", nargs="+", choices=list(GAMES), default=list(GAMES))
    p.add_argument("--cap-per-month", type=int, default=800,
                   help="max reviews kept per game per month (default 800)")
    p.add_argument("--max-pages", type=int, default=0,
                   help="stop after this many pages per game this run (0 = no limit)")
    p.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    p.add_argument("--out", default="../data/raw", help="output folder")
    args = p.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        for key in args.games:
            collect_game(key, GAMES[key], out_dir, args.cap_per_month,
                         args.max_pages, args.delay)
    except KeyboardInterrupt:
        print("\nStopped. Progress is saved, re-run the same command to resume.")
        sys.exit(0)


if __name__ == "__main__":
    main()