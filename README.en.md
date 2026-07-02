<div align="center">

# Capsule Cinema

**Turn a working AI video process into a reusable video recipe.**

Capsule Cinema is for creators and teams who make short videos repeatedly. It does not stop at one generated video; it saves reusable topic structure, storyboard rhythm, tool routes, quality gates, and rework lessons as portable Capsules.

<p>
  <a href="./README.md">中文</a> ·
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-PolyForm%20Noncommercial-111827.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/video-recipes-0EA5E9.svg" alt="Video recipes">
  <img src="https://img.shields.io/badge/custom-tools-14B8A6.svg" alt="Custom tools">
  <img src="https://img.shields.io/badge/local-QA-F97316.svg" alt="Local QA">
</p>

<p>
  <a href="#demo">Demo</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#why-capsule-cinema">Why</a> ·
  <a href="#core-capabilities">Capabilities</a> ·
  <a href="#video-recipes">Recipes</a> ·
  <a href="#custom-tools">Custom tools</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#community">Community</a>
</p>

<img src="docs/assets/readme-hero-en.svg" width="100%" alt="Capsule Cinema workflow from brief to release package">

</div>

Capsule Cinema is built for repeatable video production: change the topic, material, or episode copy while keeping the structure that already worked. It turns the process into reviewable storyboards, replaceable tool capabilities, reusable Capsule packages, and local QA artifacts.

## Demo

These samples come from built-in starter recipes. They show the channel, commerce, art-motion, and stylized short-video directions Capsule Cinema can cover, with the matching capsule ID shown for each demo.

<table>
  <tbody>
    <tr>
      <td width="62%" valign="top">
        <video width="100%" controls src="https://github.com/user-attachments/assets/d81e88b3-a567-4835-9784-c2a65f4fe977"></video>
      </td>
      <td width="38%" valign="top">
        <strong>Life-sim short drama</strong>
        <br>
        Capsule: <code>life_sim</code>
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
        Capsule: <code>ecommerce_product_showcase</code>
        <br>
        Selling-point breakdowns, scene demos, product seeding, and short commerce videos.
      </td>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/5fff44fe-97e5-41e4-a966-2c8565926d89"></video>
        <br>
        <strong>Art image motion</strong>
        <br>
        Capsule: <code>art_motion</code>
        <br>
        Turns illustrations, posters, start/end frames, and stylized images into video.
      </td>
    </tr>
    <tr>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/b5c672be-cacb-4877-a688-e6d7baa1a3b5"></video>
        <br>
        <strong>Chinese history explainer</strong>
        <br>
        Capsule: <code>guofeng_history</code>
        <br>
        Chinese visual style, historical stories, cultural knowledge, and narrated explainers.
      </td>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/59f4c71c-9634-4b9f-8b48-e47f7a7c1d5f"></video>
        <br>
        <strong>Felt ASMR craft</strong>
        <br>
        Capsule: <code>felt_asmr</code>
        <br>
        Felt baking, soft handmade food, healing craft, and stylized ASMR clips.
      </td>
    </tr>
  </tbody>
</table>

## Quick Start

After installing the repository as an OpenClaw skill, you do not need to run scripts yourself. Describe the goal, material, style, and constraints in natural language; Capsule Cinema selects the storyboard, recipe, tool route, and QA flow for the request.

> Use Capsule Cinema to make a 30-second vertical video about `<topic>` for `<audience>` in `<style>`.

You can name these built-in capsules directly:

| Capsule | Best for |
| --- | --- |
| `life_sim` | Life simulation, workplace drama, empathy narration |
| `ecommerce_product_showcase` | Product showcase, selling points, commerce clips |
| `art_motion` | Art image animation and start/end-frame clips |
| `guofeng_history` | Chinese historical and cultural explainers |
| `felt_asmr` | Felt craft, soft food, ASMR handmade videos |

Common ways to start:

| Goal | Say this |
| --- | --- |
| Review the plan first | “Only create the storyboard for now. Do not generate images, video, or voice yet. The topic is `<topic>`.” |
| Make a full video | “Use Capsule Cinema to make a 30-second vertical video about `<topic>` for `<audience>` in `<style>`.” |
| Pick a capsule | “Use the `ecommerce_product_showcase` capsule for a product video. The product is `<product>` and the key selling points are `<points>`.” |
| Rework one scene | “I do not like scene 3 from the last version. Keep everything else and regenerate only that scene: `<change request>`.” |
| Save the method | “I am happy with this video. Save this structure as `<recipe name>` for future `<use case>` videos.” |

After a run, Capsule Cinema keeps the final video, storyboard, timeline, QA, repair suggestions, and release checkpoint together in the local workspace so you can rework the result or promote the method into a recipe.

## Why Capsule Cinema

One-off prompts can make a single video, but they do not scale well into repeatable formats. Real channel, product, and team work usually needs stronger boundaries:

| Real problem | Capsule Cinema approach |
| --- | --- |
| Every episode starts from scratch | Save the working format in a Capsule |
| Video providers change quickly | Recipes declare capabilities; runtime matches available tools |
| Direction is hard to review before generation | Create a reviewable storyboard before media generation |
| One bad shot forces a full rerun | Regenerate one scene, swap BGM, subtitles, or edit plan locally |
| Release quality is mostly manual | Produce local QA, repair suggestions, and a release checkpoint |
| Reference videos are easy to copy too closely | Analyze structure, rhythm, style, and audio strategy before writing a capsule draft |

## Core Capabilities

<img src="docs/assets/readme-workflow-en.svg" width="100%" alt="Capsule Cinema workflow">

| What you need | How Capsule Cinema helps |
| --- | --- |
| Start from a short brief | Turns audience, topic, style, and assets into a storyboard, media plan, audio plan, edit, and QA flow |
| Review before generation | Lets you create only the storyboard first, then continue after approval |
| Rework one part | Regenerates one shot, swaps BGM, or re-edits existing assets without restarting the whole video |
| Make a repeatable format | Saves the working structure, rhythm, style, and quality rules as a video recipe |
| Learn from a reference video | Analyzes shot rhythm, copy structure, visual style, and audio strategy, then creates a capsule draft for approval |
| Use your own tools | Matches recipe needs with image, video, TTS, BGM, subtitle, editing, and QA tools |
| Check release readiness | Produces local QA, quality scores, repair suggestions, and release checkpoints |

## Video Recipes

A Capsule is a portable video workflow, not a finished video. It stores the reusable parts of a format: use case, input requirements, storyboard structure, visual style, audio strategy, tool route, quality rules, rework lessons, and safety boundaries.

<img src="docs/assets/readme-capsule-anatomy-en.svg" width="100%" alt="Capsule package anatomy">

Starter capsules included in this repository:

| Capsule | Best for | Execution |
| --- | --- | --- |
| `life_sim` | Life simulation, workplace drama, empathy narration | local script |
| `ecommerce_product_showcase` | Product showcase, selling points, commerce clips | preset |
| `art_motion` | Art image animation and start/end-frame clips | local script |
| `guofeng_history` | Chinese historical and cultural explainers | preset |
| `felt_asmr` | Felt craft, soft food, ASMR handmade videos | preset |

Recipes can come from three places:

- Starter recipes: seed examples included in the project.
- Personal recipes: formats distilled from your own successful work.
- Community recipes: shareable methods others can try, adapt, and improve.

When you reuse a recipe, swap the topic, assets, and episode copy while keeping the proven structure. A recipe should not store API keys, cookies, client data, private assets, temporary links, or one-off run outputs.

## Custom Tools

AI video tools change quickly, so recipes do not bind themselves to one vendor. A recipe describes the capability it needs, each tool declares what it can do, and the runtime matches them.

You can connect tools for:

| Tool type | Uses |
| --- | --- |
| Image generation | Text-to-image, image-to-image, style transfer, cover images |
| Video generation | Text-to-video, image-to-video, start/end-frame video, action transfer, lip sync |
| Audio generation | TTS, voices, BGM, sound effects, music generation |
| Post production | Subtitles, concatenation, transcoding, covers, intros and outros |
| Quality checks | Black frames, aspect ratio, subtitle occlusion, loudness, release checks |

Before a run, Capsule Cinema checks credentials and matches capabilities. If a tool is unavailable, it can list fallback routes; downgrades that need user approval pause first.

## Architecture

Capsule Cinema is an OpenClaw skill with two layers: executable runtime and production methodology.

| Layer | Path | Role |
| --- | --- | --- |
| Plugin entry | `index.js` | OpenClaw inputs, env allowlist, subprocess dispatch |
| Script entry points | `scripts/` | Storyboard, full video, scene rework, concat, QA, capsule management |
| Video workflow | `lib/video_workflows/general_video/` | Planning, storyboard, media generation, post production, state handoff |
| Tool library | `lib/custom_tools/` | Image, video, TTS, BGM, subtitle, and QA provider wrappers |
| Capsule packages | `capsules/*.capsule/` | Reusable video recipes, contracts, assets, and quality rules |
| Production references | `references/` | Route policy, channel policy, storyboard rules, delivery standards |

See [references/architecture.md](references/architecture.md) for the full runtime map.

### Video Capability Map

<img src="docs/assets/readme-capability-map-en.svg" width="100%" alt="Capsule Cinema video capability map">

## Useful Prompts

| Goal | Say this |
| --- | --- |
| Storyboard first | “Only create the storyboard for now. Do not generate images, video, or voice yet. The topic is `<topic>`.” |
| Full video | “Use Capsule Cinema to make a `<duration>` second `<landscape/vertical>` video about `<topic>`, focusing on `<value point>`.” |
| Rework one shot | “I do not like scene `<number>` from the last video. Keep everything else and regenerate only that scene: `<change request>`.” |
| Reuse assets | “These scene assets are good. Re-edit them with the new subtitle, BGM, and pacing requirements.” |
| Check release readiness | “Check whether this video is publishable. Focus on visuals, audio, subtitles, duration, language match, and recipe quality rules.” |
| Save as a recipe | “I am happy with this video. Save it as `<recipe name>` for future `<use case>` videos.” |
| Analyze a reference video | “Analyze this local reference video `<video path>`, extract reusable structure, style, pacing, copy, and quality rules, then create a capsule draft called `<recipe name>`.” |
| Add a tool channel | “Add a new `<tool/channel name>`. Here is the API documentation: `<paste docs>`. Connect it to Capsule Cinema and include a simple user example.” |

## Community

Use [GitHub Issues](https://github.com/JuneYaooo/capsule-cinema/issues) to share recipe ideas, run problems, sample videos, or improvement requests.

Chinese developer community: [LINUX DO](https://linux.do/)

## License

PolyForm Noncommercial License 1.0.0. See [LICENSE](./LICENSE).
