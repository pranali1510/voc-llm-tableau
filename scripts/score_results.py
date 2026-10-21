r"""Score the LLM against your hand labels, and against the keyword baseline.

Usage (PowerShell; GEMINI_MODEL must be set so the right results file is found):
  python scripts\score_results.py dev               # compare the LLM with your dev labels
  python scripts\score_results.py test              # compare with the locked test labels (do this ONCE)
  python scripts\score_results.py dev 2             # score run 2 instead of run 1
  python scripts\score_results.py consistency test 1 2   # how often do runs 1 and 2 agree?

On the dev set the script lists the mistakes so you can improve the prompt.
On the test set it shows NO individual mistakes, so you cannot tune on it.
Each scoring run is appended to docs/llm_validation.md.
"""
import json
import math
import os
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

import config
from keyword_baseline import predict_sentiment, predict_theme
from taxonomy import SENTIMENTS, THEMES, normalise_theme

CLEAN, LLM_DIR = Path(config.CLEAN_DIR), Path("data/llm")
PROMPT_VERSION = os.environ.get("PROMPT_VERSION", "v1")


def results_file(model: str, run: str) -> Path:
    return LLM_DIR / f"results_{re.sub(r'[^A-Za-z0-9.-]', '_', model)}_{PROMPT_VERSION}_run{run}.jsonl"


def load_results(model: str, run: str) -> pd.DataFrame:
    path = results_file(model, run)
    if not path.exists():
        sys.exit(f"{path} not found. Run scripts\\llm_classify.py first (same model, prompt version and run).")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return pd.DataFrame(rows).drop_duplicates("reviewId", keep="last")


def wilson(correct: int, n: int, z: float = 1.96):
    p = correct / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def per_theme(gold, pred):
    rows = []
    for theme in THEMES:
        g, p = gold == theme, pred == theme
        if g.sum() == 0 and p.sum() == 0:
            continue
        both = int((g & p).sum())
        prec = both / p.sum() if p.sum() else float("nan")
        rec = both / g.sum() if g.sum() else float("nan")
        f1 = 2 * prec * rec / (prec + rec) if prec == prec and rec == rec and (prec + rec) > 0 else 0.0
        rows.append((theme, int(g.sum()), prec, rec, f1))
    return rows


def fmt(x):
    return "n/a" if x != x else f"{x:.0%}"


def consistency(target, a, b):
    model = os.environ.get("GEMINI_MODEL") or sys.exit('Set $env:GEMINI_MODEL first.')
    ra, rb = load_results(model, a), load_results(model, b)
    m = ra.merge(rb, on="reviewId", suffixes=("_a", "_b"))
    if m.empty:
        sys.exit("The two runs share no reviews.")
    theme_same, sent_same = (m.theme_a == m.theme_b).mean(), (m.sentiment_a == m.sentiment_b).mean()
    sev_same = (m.severity_a == m.severity_b).mean()
    text = (f"## consistency | {model} | prompt {PROMPT_VERSION} | runs {a} vs {b} | {date.today()}\n\n"
            f"Reviews in both runs: {len(m)}. Same theme: {theme_same:.1%}. Same sentiment: {sent_same:.1%}. "
            f"Same severity: {sev_same:.1%}.\n")
    print(text)
    append_report(text)


def append_report(text):
    out = Path("docs") / "llm_validation.md"
    out.parent.mkdir(exist_ok=True)
    header = "# LLM validation\n\n" if not out.exists() else ""
    with out.open("a", encoding="utf-8") as f:
        f.write(header + text + "\n")
    print(f"Appended to {out}")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "consistency":
        if len(sys.argv) < 5:
            sys.exit("Usage: score_results.py consistency <dev|test> <runA> <runB>")
        return consistency(sys.argv[2], sys.argv[3], sys.argv[4])

    target = sys.argv[1]
    run = sys.argv[2] if len(sys.argv) > 2 else "1"
    if target not in ("dev", "test"):
        sys.exit("Target must be dev or test.")
    model = os.environ.get("GEMINI_MODEL") or sys.exit('Set $env:GEMINI_MODEL first.')

    gold = pd.read_csv(CLEAN / f"gold_complaint_{target}.csv", encoding="utf-8-sig", dtype=str).fillna("")
    blank = (gold["true_theme"].str.strip() == "") | (gold["true_sentiment"].str.strip() == "")
    if blank.any():
        sys.exit(f"{int(blank.sum())} rows in gold_complaint_{target}.csv still have no label. Finish labelling first.")
    gold["true_theme"] = gold["true_theme"].apply(normalise_theme)
    bad = gold[~gold["true_theme"].isin(THEMES) | ~gold["true_sentiment"].isin(SENTIMENTS)]
    if len(bad):
        sys.exit(f"{len(bad)} rows have a label that is not in the guide. Example: "
                 f"{bad.iloc[0]['true_theme']!r} / {bad.iloc[0]['true_sentiment']!r}")
    gold["score"] = gold["score"].astype(int)

    llm = load_results(model, run)
    df = gold.merge(llm, on="reviewId", how="left")
    missing = int(df["theme"].isna().sum())
    if missing:
        print(f"Warning: {missing} reviews have no valid LLM reply yet. Re-run llm_classify.py to fill them. "
              f"They are excluded from the scores below.")
    df = df[df["theme"].notna()].copy()
    if df.empty:
        sys.exit("No scored reviews.")
    df["base_theme"] = df["content"].apply(predict_theme)
    df["base_sent"] = df["score"].apply(predict_sentiment)

    n = len(df)
    acc_llm = int((df["theme"] == df["true_theme"]).sum())
    acc_base = int((df["base_theme"] == df["true_theme"]).sum())
    sent_llm = int((df["sentiment"] == df["true_sentiment"]).sum())
    sent_base = int((df["base_sent"] == df["true_sentiment"]).sum())
    lo, hi = wilson(acc_llm, n)
    llm_rows = per_theme(df["true_theme"], df["theme"])
    base_rows = {r[0]: r for r in per_theme(df["true_theme"], df["base_theme"])}
    macro = lambda rows: sum(r[4] for r in rows if r[1] > 0) / max(1, sum(1 for r in rows if r[1] > 0))

    cost = ""
    log = LLM_DIR / "runs.csv"
    if log.exists():
        runs = pd.read_csv(log)
        sel = runs[(runs.model == model) & (runs.prompt_version == PROMPT_VERSION)
                   & (runs.target == target) & (runs.run.astype(str) == run)]
        if len(sel):
            cost = (f"Cost of this run: {int(sel.requests.sum())} requests, {int(sel.tokens.sum())} tokens, "
                    f"{int(sel.seconds.sum())} seconds.\n")

    lines = [
        f"## {target} | {model} | prompt {PROMPT_VERSION} | run {run} | {date.today()}",
        "",
        f"Reviews scored: {n} (rated 1-3 stars). Theme accuracy, LLM: **{acc_llm / n:.1%}** (95% interval {lo:.0%} to {hi:.0%}); "
        f"keyword baseline: {acc_base / n:.1%}.",
        f"Sentiment accuracy, LLM: {sent_llm / n:.1%}; stars-only baseline: {sent_base / n:.1%}.",
        f"Macro-F1 over themes that appear in the labels, LLM: {macro(llm_rows):.2f}; baseline: {macro(list(base_rows.values())):.2f}.",
        cost.strip(),
        "",
        "| Theme | Labelled | LLM precision | LLM recall | Baseline precision | Baseline recall |",
        "|---|---|---|---|---|---|",
    ]
    for theme, support, prec, rec, _ in llm_rows:
        b = base_rows.get(theme)
        lines.append(f"| {theme} | {support} | {fmt(prec)} | {fmt(rec)} | "
                     f"{fmt(b[2]) if b else 'n/a'} | {fmt(b[3]) if b else 'n/a'} |")
    lines.append("")
    report = "\n".join(l for l in lines if l is not None)
    print(report)
    append_report(report)

    wrong = df[df["theme"] != df["true_theme"]]
    if target == "dev":
        print(f"\nDev mistakes ({len(wrong)}). Use these to improve the prompt:")
        for r in wrong.head(15).itertuples():
            text = re.sub(r"\s+", " ", str(r.content))[:130]
            print(f"  gold: {r.true_theme} | LLM: {r.theme} | {text}")
    else:
        print("\nTest set: individual mistakes are hidden on purpose. Do not tune the prompt after seeing these scores.")
        print("If you change the prompt now, create a NEW prompt version and report both versions honestly.")


if __name__ == "__main__":
    main()
