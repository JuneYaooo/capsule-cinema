# Account Distillation Schemas

Use these fields to keep account research auditable. JSONL is preferred for raw normalized tables; Markdown is preferred for human-readable capsules.

## Artifact Layout

```text
<run_dir>/
├── raw/
│   ├── searches/
│   ├── accounts/
│   ├── posts/
│   └── comments/
├── media/
│   ├── videos/
│   ├── covers/
│   └── frames/
├── multimodal/
│   └── <post_id>.md
├── derived/
│   ├── accounts.jsonl
│   ├── posts.jsonl
│   ├── comments.jsonl
│   ├── scored_posts.jsonl
│   └── winner_matrix.csv
├── reports/
│   ├── account_registry.jsonl
│   ├── account_capsules/
│   ├── hook_library.md
│   ├── format_playbook.md
│   └── topic_lanes.md
├── logs/
└── evidence_map.json
```

## Account Record

Required:

```json
{
  "platform": "douyin",
  "account_id": "",
  "sec_user_id": "",
  "handle": "",
  "display_name": "",
  "profile_url": "",
  "bio": "",
  "follower_count": null,
  "following_count": null,
  "total_likes": null,
  "post_count": null,
  "verified": null,
  "vertical_tags": ["ai_tools"],
  "discovered_by": ["search:AI工具"],
  "retrieved_at": "2026-06-08T00:00:00-07:00",
  "raw_path": "raw/accounts/<id>.json"
}
```

Optional:

- `location`
- `mcn`
- `external_links`
- `commerce_links`
- `recent_post_cadence`
- `account_size_tier`
- `notes`

## Post Record

Required:

```json
{
  "platform": "douyin",
  "post_id": "",
  "account_id": "",
  "handle": "",
  "url": "",
  "title": "",
  "caption": "",
  "publish_time": "",
  "duration_seconds": null,
  "like_count": null,
  "comment_count": null,
  "share_count": null,
  "favorite_count": null,
  "play_count": null,
  "cover_url": "",
  "media_url": "",
  "local_media_path": "",
  "hashtags": [],
  "retrieved_at": "2026-06-08T00:00:00-07:00",
  "raw_path": "raw/posts/<id>.json"
}
```

Derived fields added during scoring:

- `total_interactions`
- `engagement_per_follower`
- `account_median_interactions`
- `account_winner_index`
- `score`
- `winner_tier`

## Multimodal Record

Each reviewed video should have either a Markdown report or JSON record with:

```json
{
  "post_id": "",
  "media_path": "media/videos/<post_id>.mp4",
  "model": "gemini-or-equivalent",
  "reviewed_at": "",
  "multimodal_status": "complete",
  "first_frame": "",
  "first_1s": "",
  "first_3s": "",
  "first_5s": "",
  "visible_hook_text": "",
  "spoken_opening": "",
  "timeline_beats": [
    {"time": "0:00-0:03", "role": "hook", "evidence": "", "effect": ""}
  ],
  "visual_devices": [],
  "audio_devices": [],
  "hook_tags": [],
  "format_tags": [],
  "interaction_hypothesis": {
    "likes": "",
    "comments": "",
    "saves": "",
    "shares": ""
  },
  "reusable_structure": "",
  "confidence": "high",
  "evidence_gaps": []
}
```

Use `multimodal_status: limited` if only cover/screenshots are available, and `missing` if no original media or screenshot evidence exists.

## Account Capsule

Use this outline for `account_capsules/<handle>.md`:

```markdown
# <display_name>

## Snapshot
- Platform:
- Handle:
- URL:
- Followers:
- Vertical:
- Sample window:
- Evidence:

## Positioning
Observed:
Inferred:

## Content Lanes
| Lane | Promise | Proof style | Typical hook | Evidence posts |

## Winner Patterns
| Post | Score | Hook | Structure | Visual proof | Comment driver |

## Multimodal Style
- Opening visuals:
- Subtitle/cover style:
- Screen/demo usage:
- Pace and edit rhythm:
- Audio/BGM:

## Reusable Templates
Do not copy scripts. Abstract the mechanism.

## Risks And Limits
```

## Evidence Map

`evidence_map.json` should connect every output to source artifacts:

```json
{
  "run": {
    "created_at": "",
    "platforms": ["douyin"],
    "queries": ["AI工具"],
    "sample_limits": ""
  },
  "accounts": {
    "<account_id>": {
      "profile_raw": "raw/accounts/<id>.json",
      "posts": ["<post_id>"],
      "capsule": "account_capsules/<handle>.md"
    }
  },
  "posts": {
    "<post_id>": {
      "post_raw": "raw/posts/<id>.json",
      "comments_raw": "raw/comments/<post_id>.json",
      "media": "media/videos/<post_id>.mp4",
      "multimodal": "multimodal/<post_id>.md"
    }
  }
}
```
