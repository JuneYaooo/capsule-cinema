#!/usr/bin/env python3
"""Normalize loose TikHub/raw platform JSON into account/post JSONL.

This is intentionally permissive. Platform responses vary, so the script
recursively scans raw JSON for objects that look like accounts or posts and
keeps source paths for later audit.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Iterable


ACCOUNT_ID_KEYS = ("sec_uid", "sec_user_id", "uid", "user_id", "author_id", "id")
POST_ID_KEYS = ("aweme_id", "note_id", "video_id", "bvid", "aid", "post_id", "id")


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def load_json(path: Path) -> Any:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return json.loads(text)


def iter_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_objects(child)


def first_value(data: dict[str, Any], keys: tuple[str, ...], default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] not in ("", None):
            return data[key]
    return default


def nested_first(data: dict[str, Any], paths: tuple[tuple[str, ...], ...], default: Any = None) -> Any:
    for path in paths:
        cur: Any = data
        for part in path:
            if not isinstance(cur, dict) or part not in cur:
                cur = None
                break
            cur = cur[part]
        if cur not in ("", None):
            return cur
    return default


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(",", "")
    multipliers = {"w": 10000, "万": 10000, "k": 1000, "千": 1000, "m": 1000000}
    try:
        suffix = text[-1].lower()
        if suffix in multipliers:
            return int(float(text[:-1]) * multipliers[suffix])
        return int(float(text))
    except (ValueError, IndexError):
        return None


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, dict):
                tag = first_value(item, ("name", "tag_name", "title", "hashtag_name"))
                if tag:
                    out.append(str(tag))
            elif item not in ("", None):
                out.append(str(item))
        return out
    if isinstance(value, str):
        return [value] if value else []
    return []


def duration_to_seconds(value: Any) -> int | None:
    duration = to_int(value)
    if duration is None:
        return None
    # Douyin often stores duration in milliseconds. Convert obvious millisecond
    # values while preserving already-second values from other platforms.
    if duration > 1000:
        return round(duration / 1000)
    return duration


def looks_like_account(obj: dict[str, Any]) -> bool:
    has_id = any(key in obj for key in ACCOUNT_ID_KEYS)
    has_profile = any(
        key in obj
        for key in (
            "nickname",
            "nick_name",
            "unique_id",
            "short_id",
            "signature",
            "avatar",
            "avatar_url",
            "follower_count",
            "fans_cnt",
        )
    )
    return has_id and has_profile


def looks_like_post(obj: dict[str, Any]) -> bool:
    has_id = any(key in obj for key in POST_ID_KEYS)
    has_content = any(key in obj for key in ("desc", "title", "caption", "statistics", "stats", "video", "images_list"))
    has_metric = any(key in obj for key in ("digg_count", "like_count", "comment_count", "share_count", "collect_count"))
    return has_id and (has_content or has_metric)


def normalize_account(obj: dict[str, Any], platform: str, raw_path: Path, retrieved_at: str) -> dict[str, Any]:
    stats = nested_first(obj, (("statistics",), ("stats",)), {}) or {}
    account_id = first_value(obj, ("sec_uid", "sec_user_id", "uid", "user_id", "id"), "")
    sec_user_id = first_value(obj, ("sec_uid", "sec_user_id"), "")
    if not sec_user_id and str(account_id).startswith("MS4w"):
        sec_user_id = account_id
    return {
        "platform": platform,
        "account_id": str(account_id),
        "sec_user_id": str(sec_user_id),
        "handle": str(first_value(obj, ("unique_id", "short_id", "user_name", "handle"), "")),
        "display_name": str(first_value(obj, ("nickname", "nick_name", "name", "display_name"), "")),
        "profile_url": str(first_value(obj, ("share_url", "profile_url", "url"), "")),
        "bio": str(first_value(obj, ("signature", "desc", "description", "bio"), "")),
        "follower_count": to_int(
            first_value(obj, ("follower_count", "fans_count", "fans_cnt"))
            or first_value(stats, ("follower_count", "fans_count", "fans_cnt"))
        ),
        "following_count": to_int(first_value(obj, ("following_count", "follow_count")) or first_value(stats, ("following_count", "follow_count"))),
        "total_likes": to_int(
            first_value(obj, ("total_favorited", "liked_count", "total_likes", "like_cnt"))
            or first_value(stats, ("total_favorited", "liked_count", "total_likes", "like_cnt"))
        ),
        "post_count": to_int(
            first_value(obj, ("aweme_count", "note_count", "video_count", "post_count", "publish_cnt"))
            or first_value(stats, ("aweme_count", "note_count", "video_count", "post_count", "publish_cnt"))
        ),
        "verified": first_value(obj, ("enterprise_verify_reason", "custom_verify", "verified"), None),
        "vertical_tags": [],
        "discovered_by": [],
        "retrieved_at": retrieved_at,
        "raw_path": str(raw_path),
    }


def normalize_post(obj: dict[str, Any], platform: str, raw_path: Path, retrieved_at: str) -> dict[str, Any]:
    stats = nested_first(obj, (("statistics",), ("stats",), ("interact_info",)), {}) or {}
    author = nested_first(obj, (("author",), ("user",), ("note_card", "user"), ("basic", "owner")), {}) or {}
    video = nested_first(obj, (("video",), ("video_info",)), {}) or {}
    post_id = first_value(obj, POST_ID_KEYS, "")
    account_id = first_value(author, ("sec_uid", "sec_user_id", "uid", "user_id", "id"), first_value(obj, ("author_user_id", "user_id"), ""))
    cover = nested_first(video, (("cover", "url_list"), ("origin_cover", "url_list"), ("dynamic_cover", "url_list")), [])
    media = nested_first(video, (("play_addr", "url_list"), ("download_addr", "url_list"), ("bit_rate",)), [])
    if isinstance(cover, list):
        cover_url = str(cover[0]) if cover else ""
    else:
        cover_url = str(cover or "")
    if isinstance(media, list):
        media_url = str(media[0]) if media and isinstance(media[0], str) else ""
    else:
        media_url = str(media or "")
    hashtags = first_value(obj, ("text_extra", "hashtags", "tag_list", "topics"), [])
    return {
        "platform": platform,
        "post_id": str(post_id),
        "account_id": str(account_id),
        "handle": str(first_value(author, ("unique_id", "short_id", "user_name", "handle"), "")),
        "url": str(first_value(obj, ("share_url", "url", "web_url"), "")),
        "title": str(first_value(obj, ("title", "desc"), "")),
        "caption": str(first_value(obj, ("desc", "caption", "content"), "")),
        "publish_time": str(first_value(obj, ("create_time", "time", "publish_time"), "")),
        "duration_seconds": duration_to_seconds(
            first_value(video, ("duration", "duration_seconds")) or first_value(obj, ("duration", "duration_seconds"))
        ),
        "like_count": to_int(first_value(stats, ("digg_count", "like_count", "liked_count")) or first_value(obj, ("digg_count", "like_count", "liked_count"))),
        "comment_count": to_int(first_value(stats, ("comment_count", "comments_count")) or first_value(obj, ("comment_count", "comments_count"))),
        "share_count": to_int(first_value(stats, ("share_count", "repost_count")) or first_value(obj, ("share_count", "repost_count"))),
        "favorite_count": to_int(first_value(stats, ("collect_count", "favorite_count", "fav_count")) or first_value(obj, ("collect_count", "favorite_count", "fav_count"))),
        "play_count": to_int(first_value(stats, ("play_count", "view_count")) or first_value(obj, ("play_count", "view_count"))),
        "cover_url": cover_url,
        "media_url": media_url,
        "local_media_path": "",
        "hashtags": as_list(hashtags),
        "retrieved_at": retrieved_at,
        "raw_path": str(raw_path),
    }


def value_quality(value: Any) -> int:
    if value in ("", None, [], {}):
        return 0
    if isinstance(value, (int, float)) and value == 0:
        return 1
    if isinstance(value, list):
        return 2 + len(value)
    if isinstance(value, str):
        return 2 + min(len(value), 80)
    return 2


def merge_record(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in incoming.items():
        if key == "raw_path":
            old = merged.get(key)
            if not old:
                merged[key] = value
            elif value and value != old:
                paths = merged.get("raw_paths")
                if not isinstance(paths, list):
                    paths = [old]
                if value not in paths:
                    paths.append(value)
                merged["raw_paths"] = paths
            continue
        if value_quality(value) > value_quality(merged.get(key)):
            merged[key] = value
    return merged


def dedupe(records: list[dict[str, Any]], key_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for record in records:
        key = tuple(record.get(field, "") for field in key_fields)
        if not any(key):
            continue
        if key in by_key:
            by_key[key] = merge_record(by_key[key], record)
        else:
            by_key[key] = record
    return list(by_key.values())


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize raw TikHub/platform JSON into JSONL account and post tables.")
    parser.add_argument("--raw-dir", required=True, help="Directory containing raw JSON files.")
    parser.add_argument("--platform", required=True, help="Platform label, e.g. douyin, xiaohongshu, bilibili.")
    parser.add_argument("--output-dir", required=True, help="Directory for accounts.jsonl and posts.jsonl.")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    if not raw_dir.is_dir():
        raise SystemExit(f"raw dir does not exist: {raw_dir}")

    retrieved_at = now_iso()
    accounts: list[dict[str, Any]] = []
    posts: list[dict[str, Any]] = []
    for path in sorted(raw_dir.rglob("*.json")):
        try:
            data = load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"skip unreadable JSON {path}: {exc}")
            continue
        rel = path.relative_to(output_dir) if path.is_relative_to(output_dir) else path
        for obj in iter_objects(data):
            if looks_like_account(obj):
                accounts.append(normalize_account(obj, args.platform, rel, retrieved_at))
            if looks_like_post(obj):
                posts.append(normalize_post(obj, args.platform, rel, retrieved_at))

    accounts = dedupe(accounts, ("platform", "account_id"))
    posts = dedupe(posts, ("platform", "post_id"))
    write_jsonl(output_dir / "accounts.jsonl", accounts)
    write_jsonl(output_dir / "posts.jsonl", posts)
    print(json.dumps({"accounts": len(accounts), "posts": len(posts), "output_dir": str(output_dir)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
