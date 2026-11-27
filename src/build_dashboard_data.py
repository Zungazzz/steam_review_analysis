"""
build_dashboard_data.py
Turns the big processed files into a few small CSVs for the dashboard, so the
dashboard folder stays light enough to commit and deploy.

Run from the repo root:  python src/build_dashboard_data.py
Reads : data/processed/*.csv and data/events.csv
Writes: dashboard/data/*.csv
"""
from pathlib import Path
import shutil
import pandas as pd

PROC = Path("data/processed")
OUT = Path("dashboard/data")
OUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(PROC / "reviews_scored.csv", parse_dates=["month"])

# 1. Monthly sentiment per game (months with very few reviews are noisy, so keep n)
monthly = (df.groupby(["game", "month"])
             .agg(n=("recommended", "size"),
                  pct_positive=("recommended", lambda s: round(100 * s.mean(), 1)),
                  avg_words=("word_count", "mean"),
                  vader_mean=("vader", "mean"))
             .round(2).reset_index())
monthly.to_csv(OUT / "monthly.csv", index=False)

# 2. Playtime effect
play = (df.groupby(["game", "playtime_bucket"], observed=True)
          .agg(n=("recommended", "size"),
               pct_positive=("recommended", lambda s: round(100 * s.mean(), 1)))
          .reset_index())
play.to_csv(OUT / "playtime.csv", index=False)

# 3. Game summary
summary = (df.groupby("game")
             .agg(reviews=("recommended", "size"),
                  pct_positive=("recommended", lambda s: round(100 * s.mean(), 1)),
                  median_hours=("playtime_hours", lambda s: round(s.median(), 1)),
                  first_month=("month", "min"), last_month=("month", "max"))
             .reset_index())
summary.to_csv(OUT / "summary.csv", index=False)

# 4. A small set of example reviews (readable length, fixed seed, no usernames in the data)
ex = df[(df["word_count"].between(20, 120))].copy()
ex["sentiment"] = ex["recommended"].map({1: "thumbs up", 0: "thumbs down"})
ex = ex.sample(frac=1, random_state=7)                       # shuffle, then take the first 60 per group
ex = ex.groupby(["game", "sentiment"]).head(60)
ex["playtime_hours"] = ex["playtime_hours"].round(1)
ex[["game", "month", "sentiment", "playtime_hours", "review"]].to_csv(
    OUT / "examples.csv", index=False)

# 5. Files that are already small: copy as they are
for name in ["complaint_themes_by_game.csv", "complaint_themes_by_half_year.csv",
             "bertopic_topics.csv", "event_impact.csv"]:
    shutil.copy(PROC / name, OUT / name)
shutil.copy(Path("data/events.csv"), OUT / "events.csv")

print("wrote:", ", ".join(sorted(p.name for p in OUT.iterdir())))
