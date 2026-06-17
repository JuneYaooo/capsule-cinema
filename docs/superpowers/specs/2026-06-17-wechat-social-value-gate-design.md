# WeChat Social Value Gate Design

## Goal

Improve the `github_skills_showcase` capsule so WeChat Channels titles and body copy prioritize a distinctive, user-valuable angle without hard-coding any one project type, example, or content niche.

## Scope

The change applies first to platform publishing copy, especially `wechat_channels.md`-style title and body copy. It may influence the in-video first-screen title and bottom fact-chain cards, but only as a weak preference when the project facts naturally support it.

## Method

Add a capsule method block named `wechat_social_value_gate`.

Before writing WeChat Channels title/body copy, the agent should identify at least one of these value angles:

- `hard_value`: concrete method, checklist, judgment, diagnostic point, avoidable mistake, or reusable action.
- `distinctive_view`: a supported interpretation, classification, tradeoff, or counter-obvious angle beyond project summary.
- `unexpected_use`: a factual but less obvious use of the same repo, tool, or skill.

Then evaluate two social behaviors:

- `like_signal`: whether liking the content publicly helps the viewer signal judgment, professionalism, taste, information advantage, or domain fluency.
- `share_target`: whether a viewer can imagine a specific friend, colleague, team, or group that would receive practical value from the content.

The recommended emphasis is `distinctive_view` first, then user value. This keeps the capsule from becoming generic interaction bait.

## Boundaries

Do not encode specific examples as rules. Do not force Agent, code quality, token cost, team workflow, GitHub stars, or any other sample angle into unrelated projects. Do not expose internal terms such as `like_signal`, `share_target`, `hard_value`, or `distinctive_view` in public copy. All claims must map back to repo facts, docs, screenshots, demos, source files, or clearly marked editorial inference.

## QA

Add quality rules requiring WeChat Channels title/body copy to include a real social-value reason, avoid generic "like/save/share" calls, and pass an abstraction boundary check so concrete examples do not become universal rules.
