"""Build the complaint-focused gold sets (reviews rated 1-3 stars, at least 5 characters).

Why: your random gold sets are about two thirds praise, so most themes have almost no
examples. The LLM only classifies 1-3 star reviews, so it must be tested on those.

This script REUSES the in-scope reviews you already labelled in gold_dev.csv and
gold_test.csv, and adds NEW unlabelled reviews until each set reaches its target size.
Outputs: data/clean/gold_complaint_dev.csv (target 30) and gold_complaint_test.csv (target 100)
Label only the blank rows (they are listed first), following docs/labelling_guide.md.
Never overwrites an existing file.
"""
from pathlib import Path

import pandas as pd

import config
from taxonomy import in_scope, normalise_theme

DEV_TARGET, TEST_TARGET, SEED = 30, 100, 2027
COLS = ["reviewId", "app", "score", "content", "true_theme", "true_sentiment"]


def load_labelled(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")
    df["true_theme"] = df["true_theme"].apply(normalise_theme)
    df = df[df.apply(lambda r: in_scope(r["score"], r["content"]), axis=1)]
    return df[df["true_theme"].str.strip().ne("") & df["true_sentiment"].str.strip().ne("")]


def main():
    clean = Path(config.CLEAN_DIR)
    out_dev, out_test = clean / "gold_complaint_dev.csv", clean / "gold_complaint_test.csv"
    if out_dev.exists() or out_test.exists():
        print("A gold_complaint file already exists. Not overwriting. Delete it only if you really want to start again.")
        return

    all_df = pd.read_csv(clean / "reviews_stage1.csv", encoding="utf-8", dtype=str)
    all_df["score"] = all_df["score"].astype(int)
    pool = all_df[all_df.apply(lambda r: in_scope(r["score"], r["content"]), axis=1)]

    old_dev = load_labelled(clean / "gold_dev.csv")
    old_test = load_labelled(clean / "gold_test.csv")
    used = set(pd.read_csv(clean / "gold_dev.csv", encoding="utf-8-sig", dtype=str)["reviewId"]) | set(
        pd.read_csv(clean / "gold_test.csv", encoding="utf-8-sig", dtype=str)["reviewId"]
    )
    candidates = pool[~pool["reviewId"].isin(used)].sample(frac=1, random_state=SEED)

    need_dev = max(0, DEV_TARGET - len(old_dev))
    need_test = max(0, TEST_TARGET - len(old_test))
    if need_dev + need_test > len(candidates):
        print(f"Only {len(candidates)} unused in-scope reviews available (need {need_dev + need_test}).")
        need_test = max(0, len(candidates) - need_dev)
    new_dev = candidates.iloc[:need_dev]
    new_test = candidates.iloc[need_dev:need_dev + need_test]

    for name, new, old, path in (("dev", new_dev, old_dev, out_dev), ("test", new_test, old_test, out_test)):
        new = new.assign(true_theme="", true_sentiment="")[COLS]
        merged = pd.concat([new, old[COLS]], ignore_index=True)  # blank rows first
        merged.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"{name}: {len(merged)} reviews = {len(old)} already labelled + {len(new)} NEW to label -> {path}")
    print(f"In-scope reviews in the whole dataset: {len(pool)} of {len(all_df)}")
    print("Label only the rows with blank true_theme / true_sentiment.")


if __name__ == "__main__":
    main()
