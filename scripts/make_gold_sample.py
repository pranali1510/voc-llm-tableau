"""Draw the hand-labelling sample: 40 dev reviews (for tuning the prompt) and 100 test
reviews (locked: score the LLM on these once, never tune on them).

Stratified by app (10 dev + 25 test per app). The two sets never overlap.
Outputs: data/clean/gold_dev.csv and data/clean/gold_test.csv (UTF-8 with BOM)
Fill the two empty columns following docs/labelling_guide.md:
  true_theme, true_sentiment
Save as 'CSV UTF-8 (Comma delimited)' if you edit in Excel.
Re-running never overwrites a file that already contains labels.
"""
from pathlib import Path

import pandas as pd

import config

DEV_PER_APP, TEST_PER_APP, SEED = 10, 25, 2026


def has_labels(path: Path) -> bool:
    if not path.exists():
        return False
    old = pd.read_csv(path, encoding="utf-8-sig")
    return old["true_theme"].fillna("").astype(str).str.strip().ne("").any()


def main():
    clean = Path(config.CLEAN_DIR)
    dev_path, test_path = clean / "gold_dev.csv", clean / "gold_test.csv"
    if has_labels(dev_path) or has_labels(test_path):
        print("A gold file already contains labels. Not overwriting. Delete it only if you really want a new sample.")
        return

    df = pd.read_csv(clean / "reviews_stage1.csv", encoding="utf-8")
    dev_parts, test_parts = [], []
    for app, group in df.groupby("app"):
        need = DEV_PER_APP + TEST_PER_APP
        if len(group) < need:
            print(f"Warning: {app} has only {len(group)} reviews (need {need}).")
        shuffled = group.sample(frac=1, random_state=SEED)
        dev_parts.append(shuffled.iloc[:DEV_PER_APP])
        test_parts.append(shuffled.iloc[DEV_PER_APP:DEV_PER_APP + TEST_PER_APP])

    cols = ["reviewId", "app", "score", "content"]
    for name, parts, path in (("dev", dev_parts, dev_path), ("test", test_parts, test_path)):
        out = pd.concat(parts)[cols].sample(frac=1, random_state=SEED).copy()  # mix apps
        out["true_theme"] = ""
        out["true_sentiment"] = ""
        out.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"Wrote {len(out)} {name} reviews to {path}")
    print("Label the dev file first, then the test file. Follow docs/labelling_guide.md.")


if __name__ == "__main__":
    main()
