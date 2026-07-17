<div align="center">

# Capsule Cinema

**An AI video production factory for turning proven workflows into reusable video recipes.**

Capsule Cinema is for creators and teams who make short videos repeatedly. It organizes briefs, assets, tool capabilities, and quality rules into reusable video recipes, so a proven format can keep its structure while the topic, material, and style change.

<p>
  <a href="./README.md">中文</a> ·
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-PolyForm%20Noncommercial-111827.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/Agent-Skills-16A34A.svg" alt="Agent Skills">
  <img src="https://img.shields.io/badge/video-recipes-2563EB.svg" alt="Video recipes">
  <img src="https://img.shields.io/badge/custom-tools-475569.svg" alt="Custom tools">
  <img src="https://img.shields.io/badge/quality-gates-0F172A.svg" alt="Quality gates">
</p>

<p>
  <strong>This is a Skills project for agents such as Codex, Claude Code, Hermes, WorkBuddy, OpenClaw, Coze, and others. It is ready to use after simple installation and configuration.</strong><br>
  After installation in a supported agent environment, an AI agent reads <code>skill.md</code>, <code>references/</code>, the recipe directory, and the local tool entrypoints to produce storyboards, generated media, edits, subtitles, BGM, and QA from reusable video recipes.
</p>

<p>
  <a href="#demo">Demo</a> ·
  <a href="#why-capsule-cinema">Why</a> ·
  <a href="#what-it-does">What it does</a> ·
  <a href="#video-capability-map">Capability map</a> ·
  <a href="#video-recipes">Recipes</a> ·
  <a href="#custom-tools">Custom tools</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#community">Community</a>
</p>

<img src="docs/assets/readme-hero-en.svg" width="100%" alt="Capsule Cinema: turn one successful video workflow into a reusable capsule">

</div>

In plain terms, Capsule Cinema is an installable AI agent Skills package. It includes agent instructions, a video production runtime, capability matching rules, and reusable video recipes. You do not use it by opening a web app directly; you install it into an agent environment that supports Skills, such as Codex, Claude Code, Hermes, WorkBuddy, OpenClaw, or Coze, then drive video production through conversation.

Capsule Cinema is not a one-shot video generator. It is a reusable production system: it breaks creation into storyboards, tool routes, audio strategy, quality rules, and rework lessons, then stores the stable parts as a recipe.

## Demo

These samples come from built-in starter recipes, and their matching capsules ship with the public repository. Public execution uses official Volcengine Ark image and Seedance video channels, with official MiniMax or Doubao Speech (API Key + bidirectional WebSocket) available for narration; RunningHub action-transfer and lip-sync workflows remain as code examples.

<table>
  <tbody>
    <tr>
      <td width="62%" valign="top">
        <video width="100%" controls src="https://github.com/user-attachments/assets/d81e88b3-a567-4835-9784-c2a65f4fe977"></video>
      </td>
      <td width="38%" valign="top">
        <strong>Life-sim short drama</strong>
        <br>
        Recipe: <code>life_sim</code>
        <br><br>
        Workplace drama, everyday empathy, animated narration, and fast multi-scene cuts.
        <br><br>
        Best for strong hooks, continuous emotional progression, unified TTS pacing, and repeatable series formats.
      </td>
    </tr>
  </tbody>
</table>

<table width="100%">
  <tbody>
    <tr>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/c7722195-0c14-4478-aeb8-b5e950518669"></video>
        <br>
        <strong>Commerce product showcase</strong>
        <br>
        Recipe: <code>ecommerce_product_showcase</code>
        <br>
        Selling-point breakdowns, scene demos, product seeding, and short commerce videos.
      </td>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/5fff44fe-97e5-41e4-a966-2c8565926d89"></video>
        <br>
        <strong>Art image motion</strong>
        <br>
        Recipe: <code>art_motion</code>
        <br>
        Turns illustrations, posters, reference frames, and stylized images into video.
      </td>
    </tr>
    <tr>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/b5c672be-cacb-4877-a688-e6d7baa1a3b5"></video>
        <br>
        <strong>Chinese history explainer</strong>
        <br>
        Recipe: <code>guofeng_history</code>
        <br>
        Chinese visual style, historical stories, cultural knowledge, and narrated explainers.
      </td>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/59f4c71c-9634-4b9f-8b48-e47f7a7c1d5f"></video>
        <br>
        <strong>Felt ASMR craft</strong>
        <br>
        Recipe: <code>felt_asmr</code>
        <br>
        Felt baking, soft handmade food, healing craft, and stylized ASMR clips.
      </td>
    </tr>
  </tbody>
</table>

## Why Capsule Cinema

One-off prompts can make a single video, but they do not scale well into repeatable formats. Real channel, product, and team work usually runs into these problems:

| Real problem | Capsule Cinema approach |
| --- | --- |
| Every episode starts from scratch | Save the working format as a video template |
| Video tools change quickly | Recipes describe required capabilities; runtime matches available tools |
| Direction is hard to review before generation | Create a reviewable storyboard before media generation |
| One bad shot forces a full rerun | Rework one shot, BGM, subtitles, or edit plan without restarting |
| Release quality is mostly manual | Produce quality checks, repair suggestions, and release checkpoints |
| Reference videos are easy to copy too closely | Analyze structure, rhythm, style, and audio strategy before creating a recipe draft |

## What it does

<img src="docs/assets/readme-workflow-en.svg" width="100%" alt="Capsule Cinema workflow">

| Video direction | Creative capabilities |
| --- | --- |
| Real-footage editing | Turns existing clips, references, subtitles, BGM, and pacing requirements into a reviewable edit plan |
| General AI video creation | Builds storyboards, images, video shots, voice, subtitles, edits, and QA from a topic and audience |
| Commerce videos | Structures selling points, product scenes, narration rhythm, product images, and demo shots |
| AI music videos | Designs shots around lyrics, beats, mood sections, and visual style for music videos and vibe clips |
| Digital-human explainers | Combines digital-human narration, product B-roll, subtitle cards, visual information, and real footage |
| Action mimicry and dance | Uses reference motion, character consistency, beat timing, and shot continuity for motion-led videos |
| Reference-to-recipe drafting | Analyzes shot rhythm, copy structure, visual style, and audio strategy, then creates a reviewable recipe draft |
| Targeted rework | Changes one shot, voice, BGM, or edit plan without remaking the whole video |

## Video capability map

This capability map breaks video work into content types, generation capabilities, and delivery checks. It also makes the tool boundary clear: image generation, AI video generation, TTS, AI music, real-footage editing, digital humans, action mimicry, and QA can be combined instead of locked to one platform.

<img src="docs/assets/readme-capability-map-en.svg" width="100%" alt="Capsule Cinema video capability map">

## Video recipes

A video recipe is a portable workflow, not a finished video. It stores the reusable parts of a format: use case, storyboard structure, visual style, audio strategy, tool route, quality rules, rework lessons, and safety boundaries.

<img src="docs/assets/readme-capsule-anatomy-en.svg" width="100%" alt="Video recipe structure">

Common recipe directions:

| Recipe direction | Best for |
| --- | --- |
| Channel formats | Repeatable series, narrative voiceover, explainers, and recurring topics |
| Product showcase | Selling points, use cases, comparison shots, and commerce clips |
| Art motion | Illustration motion, poster motion, start/end-frame transitions, and visual experiments |
| Chinese history | Historical stories, cultural explainers, stylized visuals, and narrated short videos |
| Craft and ASMR | Felt craft, handmade food, close-up detail, and soft audio-visual pacing |
| AI music videos | Lyric visualization, beat-driven cuts, concept films, and mood clips |
| Digital-human mixes | Presenter narration, product footage, subtitle cards, brand explainers, and B-roll edits |
| Action mimicry | Dance, pose transfer, character performance, and beat-led challenge videos |

Recipes can come from three places:

| Source | Use |
| --- | --- |
| Starter recipes | Begin quickly from seed examples included in the project |
| Personal recipes | Distill successful work into channel, brand, or project know-how |
| Community recipes | Share, test, and improve public production methods |

When you reuse a recipe, swap the topic, assets, and episode copy while keeping the proven structure. A recipe should not store API keys, cookies, client data, private assets, temporary links, or one-off run outputs.

## Custom tools

AI video tools change quickly, so recipes do not bind themselves to one platform or channel. The public README describes capability layers only: a recipe says what it needs, and the local runtime chooses from the tools currently available.

### Included channel examples

The repository ships with a small set of runnable, readable, and extensible channel implementations. They are public examples of how to turn an official API into an agent-callable production tool; they do not mean Capsule Cinema is limited to these providers.

| Capability | Example channel and tool | What the example covers |
| --- | --- | --- |
| Image generation | Volcengine Ark `VolcengineImageGeneratorTool` | Seedream text/image generation, single and multiple references, size/format controls, and local result downloads |
| Video generation | Volcengine Ark `Seedance20VideoGeneratorTool` | Seedance text/image/first-last-frame/multimodal generation, asynchronous polling, and local downloads; the Model ID can select standard or Fast |
| Speech synthesis | Doubao Speech `DoubaoTTSTool` | Official API-Key authentication, bidirectional WebSocket, Speech Synthesis 2.0, voices, and subtitle timestamps |
| Speech synthesis | MiniMax route in `UniversalTTSTool` | Official MiniMax TTS, voice/speed controls, and local audio artifacts |
| Action transfer and lip sync | RunningHub example tools | Inspectable workflow parameters, asynchronous tasks, downloads, and local QA boundaries |

Each example preserves the parts needed to operate the channel: adapter code, tool registration, capability tags, environment-variable names, runnable recipes, known failure modes, retry boundaries, cost notes, and delivery QA. API keys, cookies, signed URLs, and temporary result URLs never belong in the repository.

### Give new API documentation directly to the AI

When you need another image, video, TTS, music, digital-human, action-transfer, or lip-sync provider, you do not need to wait for hard-coded project support. Give the AI the official API documentation URL or full documentation and state the desired models, task types, and cost preference. Personal channels belong in the Git-ignored `local-channels/` overlay by default and do not alter the public allowlist. For example:

> Here is the API documentation for [provider]: [link or local file]. Add it to Capsule Cinema so I can use this provider when making videos.

A useful document set includes the Base URL, authentication headers, Model/Endpoint IDs, accepted media formats, task-creation request, synchronous response or asynchronous query API, success/failure states, result URL fields, limits and pricing notes, and official request/response examples. Ask the AI to verify missing fields against official documentation instead of guessing private protocols.

The AI can then distill the integration into the same project surfaces as the included examples:

1. Put private adapters in Git-ignored `lib/custom_tools/<category>/local_*_adapter.py`, and put registration, capability tags, and local tests in `local-channels/`; use non-`local_` modules and change the public registry only for an explicit public contribution.
2. Record status, I/O, limits, tags, environment-variable names, cost tier, failure modes, QA, and an approved same-role fallback without hard-coding credentials.
3. Keep a runnable local recipe, known failure modes, and QA requirements; synchronize `references/` only for a public contribution.
4. Validate request structures with non-billed checks and mocks, then run the lowest-cost real smoke test after user approval.
5. Mark the channel `approved` only after its first real test passes; keep unproven routes `suspended` so the runtime cannot select them silently.

For example, a recipe can ask for text-to-image, image-to-video, TTS narration, BGM, subtitles, and release checks. The runtime picks a local tool route; if one capability is missing, it explains the fallback and how it changes the output.

That separation comes from a shared capability vocabulary and tool tags. A recipe does not name a specific tool; it states the capabilities each role needs. Each tool declares its capability tags, hard limits, and local credential status. For example, one tool may declare "image-to-video, strong motion, vertical output, short clips", while another may declare "first/last frames, cinematic motion, native audio". The runtime filters by hard requirements first, then uses tags to choose the better fit.

### Capability tag matching

| Layer | What it says | Why it matters |
| --- | --- | --- |
| Recipe role | Which image, video, voice, music, subtitle, and QA capabilities this part of the video needs | Recipes describe intent without binding to a tool |
| Capability vocabulary | Shared capabilities such as text-to-image, image-to-video, first/last frames, lip sync, action transfer, text-to-music, and reference-video analysis | Recipes and tools speak the same language |
| Tool tags | Each tool declares supported capabilities, aspect ratios, durations, audio strategy, style fit, and local credential state | The runtime knows which routes are available on this machine |
| Runtime matching | Filter by hard requirements first, then choose the best fit by tags | Enables tool replacement, fallback, and user confirmation |

| Capability layer | Boundary | Best for |
| --- | --- | --- |
| Image generation | Text-to-image, image-to-image, reference images, product images, covers, and stylized visuals | General AI video, commerce product images, covers, history visuals, and art styles |
| AI video generation | Text-to-video, image-to-video, first/last frames, shot extension, transitions, and native-audio strategy | General AI video, product demos, art shorts, and narrative shots |
| TTS narration | Multi-voice narration, speed control, language choice, and unified presenter pacing | Presenter narration, explainers, commerce narration, and story voiceover |
| AI music and BGM | Music generation, usable music assets, user-provided audio, sound effects, and mixing strategy | Music videos, mood clips, ASMR, scene transitions, and background music |
| Lip sync and digital humans | Image+audio lip sync, video+audio lip sync, digital presenters, and video dubbing | Digital-human presenters, product explainers, virtual hosts, and video dubbing |
| Action mimicry | Reference action, dance motion, single-person or multi-person transfer, and character consistency checks | Dance videos, motion transfer, character performance, and challenge clips |
| Editing and subtitles | Video concatenation, BGM mixing, burned subtitles, adaptive subtitles, and transcoding | Real-footage edits, AI scene assembly, presenter B-roll, and release packaging |
| QA and video analysis | Black frames, aspect ratio, duration, subtitle layout, loudness, language match, and reference-video breakdown | Release checks, reference-to-recipe drafting, and repair planning |

Credential checks, capability matching, fallback paths, and user confirmation are runtime orchestration, not standalone tools. If a tool is unavailable, Capsule Cinema can list available fallback routes; downgrades that change the promised output pause for approval.

## How it works

| Stage | What happens |
| --- | --- |
| Brief understanding | Organize audience, topic, assets, style, and publishing context into production requirements |
| Recipe selection | Choose an existing recipe, or draft a new one from a reference video and goal |
| Storyboard review | Confirm shot structure, copy rhythm, visual direction, and audio strategy first |
| Tool orchestration | Match image, video, TTS, music, editing, digital-human, and QA tools by capability tags |
| Quality gates | Check aspect ratio, duration, subtitles, audio, shot completeness, and recipe constraints |
| Experience writeback | Feed rework causes, useful structures, and release checks back into the recipe |

## Quick Start

You do not need to memorize any commands. Install it, make videos, add providers, and save capsules by talking to the AI normally.

### 1. Ask the AI to install it

Send this to Codex, Claude Code, OpenClaw, Cursor, Trae, Hermes Agent, or another agent that can read files, run commands, and discover Skills:

```text
Install Capsule Cinema for me:
https://raw.githubusercontent.com/JuneYaooo/capsule-cinema/main/docs/install.md

Tell me how to use it when it is ready.
```

Sending the prompt above is the entire user-side installation flow: you do not need to open a terminal or run installation code yourself. The agent clones the repository, selects the current environment, runs the installer, installs Python dependencies, and checks FFmpeg. Upgrades preserve `.env`, local channels, custom capsules, and historical output.

The AI will tell you if a restart is needed. Reopen it, then simply describe the video you want.

### 2. Configure only the channels you need

Browsing, validating, packing, and installing capsules do not require generation credentials. Video production needs a planning route; image, video, and voice production then need their respective media channels.

| Task | Environment variables used by the public examples |
| --- | --- |
| Internal storyboard planner | `CREW_API_KEY`, `CREW_BASE_URL`, `CREW_MODEL_NAME` |
| Volcengine Ark Seedream image + Seedance video | `ARK_API_KEY`; Base URL and Model IDs are optional overrides |
| MiniMax narration | `MINIMAX_API_KEY`; some accounts also need `MINIMAX_GROUP_ID` |
| Doubao narration | `DOUBAO_TTS_API_KEY`; resource, model, and voice variables are optional |
| RunningHub action-transfer/lip-sync examples | `RUNNINGHUB_API_KEY` plus values declared by the selected workflow |

The default image model is `doubao-seedream-5-0-pro-260628`; the default video model is `doubao-seedance-2-0-260128`. Override them with `ARK_SEEDREAM_MODEL` / `ARK_SEEDANCE_MODEL`. Seedance 2.0 also requires account-level model access or an eligible balance/resource package.

Never paste secrets into conversation, capsules, prompts, scripts, or Git. Ask the agent to check only whether variables are present; inject values through agent settings, system environment variables, a secret manager, or the installation's local `.env`.

### 3. Make the first video storyboard-first

```text
Use Capsule Cinema to make a warm, comforting 25-second vertical video about an orange cat running a late-night street-food stand. Show me the storyboard first, and continue after I like it.
```

After the storyboard is approved:

```text
I like this direction. Make one scene first so I can see how it looks.
```

After that scene passes:

```text
This scene looks good. Go ahead and finish the whole video.
```

Final deliverables live under one `output/<run>/`: `release/` holds publishable artifacts, `work/` holds media and the edit plan, and `qa/` holds checks and repair recommendations.

### 4. Install your own API channel from documentation

Give the AI the provider's API documentation link or local file. More complete documentation usually makes the integration smoother.

```text
Here is the API documentation for [provider]: [link or local file].
Add it to Capsule Cinema so I can use this provider when making videos. Tell me if you need me to configure anything.
```

For a public contribution, explicitly ask the agent to update `lib/custom_tools/`, the public registries, capability vocabulary, env allowlist, recipes, docs, and QA. Private endpoints, account fields, and secrets must still stay local.

### 5. Distill a successful workflow into a capsule

A capsule stores what remains useful next episode, not a complete backup of the previous video. Separate stable `series_fixed` elements—character bible, visual skin, shot mechanism, subtitle layout, BGM/CTA rules, and release gates—from `episode_variable` material such as names, facts, figures, prices, titles, narration, shot copy, and temporary assets.

```text
I really like this video. Save this way of making it as a “Comforting Night Stand” capsule so I can reuse it for similar videos.
```

For a reference video, ask for a draft first: extract hook, shot rhythm, structure, visual style, motion, audio, and QA methods; explicitly separate sample-specific content from reusable craft before creating an active package.

### 6. Update a capsule only with stable learning

Do not promote a one-off preference automatically. Just tell the agent what worked in plain language. It will decide whether the lesson is reusable, check for conflicts with existing rules, and ask before applying the update.

```text
The product close-ups felt better at about two seconds. See if that is worth remembering in the commerce-video capsule.
```

The agent handles conflict review, generalization, safe updating, and package validation automatically; you do not need to enumerate those steps in the prompt.

You can also ask the agent to pack a capsule as `.video-capsule.zip` or install one. Packing must scan for secrets, remote URLs, absolute paths, run artifacts, and stale evidence. Installation must verify the manifest, SHA-256 values, safe paths, and package structure, and must not overwrite a same-name capsule without a version/diff review.

## Community

Use [GitHub Issues](https://github.com/JuneYaooo/capsule-cinema/issues) to share recipe ideas, run problems, sample videos, or improvement requests.

Chinese developer community: [LINUX DO](https://linux.do/)

WeChat group: discuss video production and share your own video recipes. Scan the QR code to join the capsule-cinema community.

<p align="left">
  <img src="docs/assets/wechat-group.jpg" alt="QR code for the capsule-cinema WeChat group" width="400">
</p>

## License

PolyForm Noncommercial License 1.0.0. See [LICENSE](./LICENSE).
