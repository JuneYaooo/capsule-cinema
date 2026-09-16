# Custom tools

The tracked public tool surface contains:

- official Volcengine Ark image and video adapters;
- official Agnes free-tier image and short text-to-video adapters;
- official MiniMax H3 2K video and MiniMax/Doubao TTS adapters;
- RunningHub action-transfer and lip-sync workflow examples;
- RunningHub MiniMax H3 FL2VA first/last-frame, multi-image, and text-to-video workflow examples;
- local image/video processing, subtitles, audio assembly, and QA.

Additional cloud adapters are local-only. Their neutral adapter files and
`local-channels/` registry records are ignored by Git and merged at runtime.
See `references/channel-policy.md` for the public/runtime boundary.
