r"""Classify in-scope reviews (rated 1-3 stars, at least 5 characters) with Gemini.

Usage (PowerShell):
  $env:GEMINI_API_KEY="your-key"
  $env:GEMINI_MODEL="gemini-3.5-flash-lite"      # pin one exact model name
  python scripts\llm_classify.py dev             # gold_complaint_dev.csv
  python scripts\llm_classify.py test            # gold_complaint_test.csv  (run ONCE, after the prompt is locked)
  python scripts\llm_classify.py all             # every in-scope review
  python scripts\llm_classify.py test 2          # a second run, for the consistency check

Free-tier friendly: batches of reviews per request, a wait between requests, a daily token
budget, and a cache so an interrupted or quota-stopped run resumes where it stopped.
Optional settings: LLM_BATCH (25), LLM_SECONDS_BETWEEN_CALLS (65), LLM_DAILY_TOKENS (200000),
LLM_RETRY_SECONDS (70), PROMPT_VERSION (v1; set it to v2 to use prompts/classify_v2.md).
Only public review text and its star rating are sent. Nothing personal is included.
"""
import json
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

import config
from taxonomy import OWNERS, SENTIMENTS, THEMES, in_scope

BASE = "https://generativelanguage.googleapis.com/v1beta"
PROMPT_VERSION = os.environ.get("PROMPT_VERSION", "v1")   # prompts/classify_<version>.md
PROMPT_FILE = Path(f"prompts/classify_{PROMPT_VERSION}.md")
LLM_DIR = Path("data/llm")
CLEAN = Path(config.CLEAN_DIR)
MAX_CHARS = 600


class QuotaStop(Exception):
    pass


def env_int(name, default):
    return int(os.environ.get(name, default))


def load_prompt() -> str:
    text = PROMPT_FILE.read_text(encoding="utf-8")
    return (text.replace("{{THEMES}}", "; ".join(THEMES))
                .replace("{{SENTIMENTS}}", ", ".join(SENTIMENTS))
                .replace("{{OWNERS}}", ", ".join(OWNERS)))


def load_target(target: str) -> pd.DataFrame:
    if target in ("dev", "test"):
        path = CLEAN / f"gold_complaint_{target}.csv"
        if not path.exists():
            sys.exit(f"{path} not found. Run scripts\\make_complaint_gold.py first.")
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    elif target == "all":
        df = pd.read_csv(CLEAN / "reviews_stage1.csv", encoding="utf-8", dtype=str)
    else:
        sys.exit("Target must be dev, test or all.")
    df["score"] = df["score"].astype(int)
    df = df[df.apply(lambda r: in_scope(r["score"], r["content"]), axis=1)]
    return df[["reviewId", "score", "content"]].reset_index(drop=True)


def build_input(batch: pd.DataFrame) -> str:
    lines = []
    for i, row in enumerate(batch.itertuples(), start=1):
        text = re.sub(r"\s+", " ", str(row.content)).strip()[:MAX_CHARS]
        lines.append(f"{i}. [rating {row.score}] {text}")
    return "Reviews:\n" + "\n".join(lines)


def explain(status: int, body: str) -> str:
    hints = {400: "Bad request. Check the model name and the key.",
             403: "Permission denied. Key restricted or API unavailable.",
             404: "Model not found. Check GEMINI_MODEL against test_gemini_key.py's list."}
    return f"HTTP {status}. {hints.get(status, '')}\n{body[:300]}"


def call_api(prompt: str, model: str, key: str) -> dict:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                             "maxOutputTokens": 8192},
    }
    headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
    wait = env_int("LLM_RETRY_SECONDS", 70)
    for attempt in range(1, 5):
        r = requests.post(f"{BASE}/models/{model}:generateContent", headers=headers, json=payload, timeout=180)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (429, 500, 502, 503, 504):
            print(f"  HTTP {r.status_code}; waiting {wait * attempt}s (attempt {attempt}/4)")
            time.sleep(wait * attempt)
            continue
        sys.exit(explain(r.status_code, r.text))
    raise QuotaStop("Still rate limited after 4 attempts. This is probably a daily limit: run again later.")


def parse_items(response: dict):
    parts = response["candidates"][0]["content"]["parts"]
    text = "".join(p.get("text", "") for p in parts)
    items = json.loads(text)
    if isinstance(items, dict):
        items = next((v for v in items.values() if isinstance(v, list)), [])
    tokens = int(response.get("usageMetadata", {}).get("totalTokenCount", 0))
    return items, tokens


def valid_item(item: dict, n: int) -> bool:
    try:
        return (1 <= int(item["id"]) <= n and item["theme"] in THEMES
                and item["sentiment"] in SENTIMENTS and int(item["severity"]) in (1, 2, 3)
                and isinstance(item["summary"], str) and item["owner"] in OWNERS)
    except (KeyError, TypeError, ValueError):
        return False


def load_usage() -> dict:
    path = LLM_DIR / "usage.json"
    return json.loads(path.read_text()) if path.exists() else {}


def save_usage(usage: dict):
    (LLM_DIR / "usage.json").write_text(json.dumps(usage, indent=1))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    target = sys.argv[1]
    run_id = sys.argv[2] if len(sys.argv) > 2 else "1"
    key, model = os.environ.get("GEMINI_API_KEY"), os.environ.get("GEMINI_MODEL")
    if not key:
        sys.exit('Set the key first: $env:GEMINI_API_KEY="your-key"')
    if not model:
        sys.exit('Pin a model first: $env:GEMINI_MODEL="gemini-3.5-flash-lite"')

    LLM_DIR.mkdir(parents=True, exist_ok=True)
    batch_size = env_int("LLM_BATCH", 25)
    spacing = env_int("LLM_SECONDS_BETWEEN_CALLS", 65)
    daily_budget = env_int("LLM_DAILY_TOKENS", 200000)

    results_path = LLM_DIR / f"results_{re.sub(r'[^A-Za-z0-9.-]', '_', model)}_{PROMPT_VERSION}_run{run_id}.jsonl"
    done = set()
    if results_path.exists():
        done = {json.loads(line)["reviewId"] for line in results_path.read_text(encoding="utf-8").splitlines() if line}

    df = load_target(target)
    pending = df[~df["reviewId"].isin(done)].reset_index(drop=True)
    print(f"{len(df)} in-scope reviews, {len(done)} already done, {len(pending)} to do. Model: {model}")
    if pending.empty:
        print("Nothing to do.")
        return

    template = load_prompt()
    usage = load_usage()
    today = date.today().isoformat()
    day = usage.setdefault(today, {"tokens": 0, "requests": 0})
    started, last_call = time.time(), 0.0
    requests_made = tokens_used = valid_count = invalid_count = 0

    try:
        for start in range(0, len(pending), batch_size):
            batch = pending.iloc[start:start + batch_size]
            prompt = template + "\n\n" + build_input(batch)
            estimate = int(len(prompt) / 3.5) + 70 * len(batch)
            if day["tokens"] + estimate > daily_budget:
                print(f"Daily token budget reached ({day['tokens']} used, budget {daily_budget}). Stopping; run again tomorrow.")
                break
            wait = spacing - (time.time() - last_call)
            if last_call and wait > 0:
                print(f"  waiting {wait:.0f}s for the rate limit")
                time.sleep(wait)
            last_call = time.time()
            response = call_api(prompt, model, key)
            requests_made += 1
            try:
                items, tokens = parse_items(response)
            except Exception as exc:
                print(f"  batch starting at {start}: unreadable reply ({exc}); will retry on the next run")
                continue
            day["tokens"] += tokens
            day["requests"] += 1
            tokens_used += tokens
            save_usage(usage)

            seen = set()
            with results_path.open("a", encoding="utf-8") as f:
                for item in items:
                    if not valid_item(item, len(batch)) or int(item["id"]) in seen:
                        invalid_count += 1
                        continue
                    seen.add(int(item["id"]))
                    row = batch.iloc[int(item["id"]) - 1]
                    f.write(json.dumps({
                        "reviewId": row["reviewId"], "theme": item["theme"], "sentiment": item["sentiment"],
                        "severity": int(item["severity"]), "summary": item["summary"][:200],
                        "owner": item["owner"],
                    }, ensure_ascii=False) + "\n")
                    valid_count += 1
            missing = len(batch) - len(seen)
            invalid_count += max(0, missing - (len(items) - len(seen)))
            print(f"  batch {start // batch_size + 1}: {len(seen)}/{len(batch)} valid, {tokens} tokens")
    except QuotaStop as exc:
        print(str(exc))

    seconds = round(time.time() - started)
    print(f"\nDone: {valid_count} valid, {invalid_count} invalid or missing, {requests_made} requests, "
          f"{tokens_used} tokens, {seconds}s. Re-run the same command to retry anything missing.")
    log = LLM_DIR / "runs.csv"
    header = not log.exists()
    with log.open("a", encoding="utf-8") as f:
        if header:
            f.write("timestamp,model,prompt_version,target,run,valid,invalid,requests,tokens,seconds\n")
        f.write(f"{datetime.now().isoformat(timespec='seconds')},{model},{PROMPT_VERSION},{target},{run_id},"
                f"{valid_count},{invalid_count},{requests_made},{tokens_used},{seconds}\n")


if __name__ == "__main__":
    main()
