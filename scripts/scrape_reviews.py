"""Collect the newest public Play Store reviews for each app in config.APPS.

Raw output keeps everything the library returns (JSON lines, git-ignored; it contains
reviewer names, so never publish it). Clean output drops reviewer names and avatars and
removes duplicates. Running the script again MERGES new reviews into the existing file,
so you can run it once a day to build a longer time window.
Note: REVIEWS_PER_APP is a minimum; the library returns reviews in pages of about 200.
Output: data/clean/reviews_stage1.csv  (UTF-8)
"""
import json
import time
from pathlib import Path

import pandas as pd
from google_play_scraper import Sort, reviews

import config


def fetch(app_id: str, target: int):
    collected, token = [], None
    while len(collected) < target:
        batch, token = reviews(
            app_id, lang="en", country="in", sort=Sort.NEWEST,
            count=min(200, target - len(collected)), continuation_token=token,
        )
        if not batch:
            break
        collected.extend(batch)
        if token is None:
            break
        time.sleep(config.SLEEP_SECONDS)
    return collected


def main():
    Path(config.RAW_DIR).mkdir(parents=True, exist_ok=True)
    Path(config.CLEAN_DIR).mkdir(parents=True, exist_ok=True)
    frames = []
    for app, app_id in config.APPS.items():
        try:
            rows = fetch(app_id, config.REVIEWS_PER_APP)
        except Exception as exc:  # wrong app ID, network problem, etc.
            print(f"{app}: FAILED ({exc}). Check the app ID in config.py")
            continue
        if not rows:
            print(f"{app}: 0 reviews. Check the app ID in config.py")
            continue
        with (Path(config.RAW_DIR) / f"{app}.jsonl").open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, default=str, ensure_ascii=False) + "\n")
        df = pd.DataFrame(rows)
        df["app"] = app
        frames.append(df)
        print(f"{app}: {len(df)} reviews")

    if not frames:
        print("No reviews collected.")
        return
    all_df = pd.concat(frames, ignore_index=True)
    clean_path = Path(config.CLEAN_DIR) / "reviews_stage1.csv"
    keep = ["reviewId", "app", "score", "content", "at", "thumbsUpCount", "appVersion"]
    all_df = all_df[[c for c in keep if c in all_df.columns]]  # drops userName, userImage, replies
    all_df["at"] = pd.to_datetime(all_df["at"], errors="coerce")
    if clean_path.exists():
        old = pd.read_csv(clean_path, encoding="utf-8", parse_dates=["at"])
        all_df = pd.concat([old, all_df], ignore_index=True)
        print(f"Merged with {len(old)} reviews already saved")
    before = len(all_df)
    all_df = all_df.drop_duplicates(subset=["reviewId"]).drop_duplicates(subset=["app", "content", "at"])
    print(f"Dropped {before - len(all_df)} duplicates")
    all_df.to_csv(clean_path, index=False, encoding="utf-8")
    summary = all_df.groupby("app").agg(
        reviews=("reviewId", "count"), avg_rating=("score", "mean"),
        first=("at", "min"), last=("at", "max"),
    )
    summary["avg_rating"] = summary["avg_rating"].round(2)
    summary["hours_covered"] = ((summary["last"] - summary["first"]).dt.total_seconds() / 3600).round(1)
    print("\n" + summary.to_string())


if __name__ == "__main__":
    main()
