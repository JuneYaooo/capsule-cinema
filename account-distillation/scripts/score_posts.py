#!/usr/bin/env python3
"""Score normalized posts for account distillation."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def safe_num(value: Any) -> float:
    if value in ("", None):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_followers(accounts_path: Path | None) -> dict[str, float]:
    if not accounts_path or not accounts_path.exists():
        return {}
    out = {}
    for account in read_jsonl(accounts_path):
        account_id = str(account.get("account_id") or account.get("sec_user_id") or "")
        followers = safe_num(account.get("follower_count"))
        if account_id and followers:
            out[account_id] = followers
    return out


def percentile(values: list[float], value: float) -> float:
    if not values:
        return 0.0
    less_or_equal = sum(1 for item in values if item <= value)
    return less_or_equal / len(values)


def tier(score: float) -> str:
    if score >= 85:
        return "top_winner"
    if score >= 70:
        return "strong"
    if score >= 55:
        return "promising"
    return "baseline"


def score(posts: list[dict[str, Any]], followers_by_account: dict[str, float]) -> list[dict[str, Any]]:
    account_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for post in posts:
        account_groups[str(post.get("account_id") or post.get("handle") or "unknown")].append(post)

    all_interactions = []
    for post in posts:
        interactions = (
            safe_num(post.get("like_count"))
            + 2.0 * safe_num(post.get("comment_count"))
            + 3.0 * safe_num(post.get("share_count"))
            + 2.5 * safe_num(post.get("favorite_count"))
        )
        post["total_interactions"] = int(interactions)
        all_interactions.append(interactions)

    scored = []
    for account_key, group in account_groups.items():
        interactions = [safe_num(post.get("total_interactions")) for post in group]
        nonzero = [value for value in interactions if value > 0]
        median = statistics.median(nonzero) if nonzero else 0.0
        for post in group:
            total = safe_num(post.get("total_interactions"))
            account_id = str(post.get("account_id") or "")
            followers = followers_by_account.get(account_id, 0.0)
            engagement = total / followers if followers else 0.0
            winner_index = total / median if median else 0.0
            absolute_pct = percentile(all_interactions, total)
            account_component = min(math.log1p(winner_index) / math.log(6), 1.0) if winner_index else 0.0
            engagement_component = min(math.log1p(engagement * 1000) / math.log(11), 1.0) if engagement else 0.0
            final_score = round(100 * (0.45 * account_component + 0.35 * absolute_pct + 0.20 * engagement_component), 2)
            enriched = dict(post)
            enriched["account_median_interactions"] = round(median, 2)
            enriched["engagement_per_follower"] = round(engagement, 8)
            enriched["account_winner_index"] = round(winner_index, 3)
            enriched["score"] = final_score
            enriched["winner_tier"] = tier(final_score)
            enriched["account_group_key"] = account_key
            scored.append(enriched)
    scored.sort(key=lambda item: (safe_num(item.get("score")), safe_num(item.get("total_interactions"))), reverse=True)
    return scored


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "score",
        "winner_tier",
        "platform",
        "handle",
        "account_id",
        "post_id",
        "title",
        "total_interactions",
        "account_winner_index",
        "engagement_per_follower",
        "like_count",
        "comment_count",
        "favorite_count",
        "share_count",
        "play_count",
        "url",
        "raw_path",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score normalized social posts by absolute, account-relative, and follower-normalized signals.")
    parser.add_argument("--posts", required=True, help="Input posts.jsonl.")
    parser.add_argument("--accounts", help="Optional accounts.jsonl for follower normalization.")
    parser.add_argument("--output-jsonl", required=True, help="Output scored posts JSONL.")
    parser.add_argument("--output-csv", required=True, help="Output winner matrix CSV.")
    args = parser.parse_args()

    posts_path = Path(args.posts).expanduser().resolve()
    accounts_path = Path(args.accounts).expanduser().resolve() if args.accounts else None
    scored = score(read_jsonl(posts_path), load_followers(accounts_path))
    output_jsonl = Path(args.output_jsonl).expanduser().resolve()
    output_csv = Path(args.output_csv).expanduser().resolve()
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_jsonl, scored)
    write_csv(output_csv, scored)
    print(json.dumps({"posts": len(scored), "jsonl": str(output_jsonl), "csv": str(output_csv)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
