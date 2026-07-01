# Life Sim Sun Wukong Video Design

## Summary

Create a `life_sim` capsule creative package for a short-form Chinese narrated video:

- Topic: `如果你抽到孙悟空的一生`
- Platform: Douyin-style vertical short video
- Aspect ratio: `9:16`
- Duration target: 4:10-4:40, hard maximum under 5:00
- Narrative mode: second person, viewer-as-protagonist
- Image route: Krill AI `Image2` through the capsule's Image2-capable tool route
- Opening: `life_shaker`
- Body subtitles: off by default; use only sparse opening text, scene labels, cover text, and optional emotional cards
- Visual style: soft Chinese picture-book watercolor with delicate linework, negative space, dreamlike myth landscapes, and lonely-but-luminous emotional tone. Do not ask the model to directly imitate a specific living artist's exact style.

The creative promise is "爽点藏在眼泪里": the first half delivers escalating power-fantasy highs, the middle crashes into five hundred years of immobility, and the final act reframes power as restraint, protection, and the survival of an untamed heart.

## Goals

1. Make the viewer feel "you are Sun Wukong," not that they are watching a detached biography.
2. Deliver clear emotional peaks: birth, first recognition, learned power, dragon palace weapon, underworld name deletion, humiliation, rebellion, furnace rebirth, heavenly battle, mountain punishment, being seen again, choosing restraint.
3. Keep the mythic scale, but ground each major turn in bodily or spatial details: stone dust on palms, waterfall pressure, cold metal staff, ink on the life register, horse stable smell, furnace heat, rain in the eyes, tightness of the golden headband.
4. Maintain a gentle picture-book atmosphere even during action scenes. The video should feel tender and poetic, not like a heavy armored action game trailer.
5. Fit under 5 minutes while preserving rhythm. Targeting about 4.5 minutes avoids rushing the five-hundred-year emotional turn.

## Non-Goals

- Do not create a literal biography of "he did this, then he did that."
- Do not copy character designs from modern films, games, animation series, or a specific living illustrator.
- Do not turn the ending into a moral lecture.
- Do not burn full body subtitles by default.
- Do not reuse one generated body image across multiple micro-cuts unless the user explicitly accepts a quality downgrade.

## Creative Approaches Considered

### Recommended: Power Fantasy With A Wound

This is the chosen approach. The video starts with miraculous self-invention and fast victories, then reveals that nobody can beat the protagonist by force, so the world beats him through immobility and time. The ending makes the greatest "爽点" not rebellion itself, but the fact that rebellion survives after punishment.

Trade-off: Needs more careful pacing than a pure hype edit, but it best matches the `life_sim` second-person contract and the requested emotional pull.

### Alternative: Pure Rebellion Hype

Focus on dragon palace, underworld, heavenly rebellion, and the furnace. This would be punchier and cheaper to make because it needs fewer quiet emotional scenes.

Trade-off: Less unique, less "picture-book," and the five-hundred-year loneliness would feel like an afterthought.

### Alternative: Lonely Mythic Fable

Lean hard into birth, abandonment, mountain rain, and being seen by Tang Sanzang.

Trade-off: Stronger authorial emotion, but weaker short-video retention because the early "爽点" density drops.

## Viewer Experience

The first 3 seconds use the `life_shaker` ritual to lock identity: "每天一个模拟人生，今天你抽到孙悟空。"

The first 40 seconds must hook through miracle and recognition:

- You are not born. You wake from stone.
- No one gives you a name.
- You earn your first title by jumping through the waterfall.

The next 90 seconds are an escalation ladder:

- You learn impossible skills.
- You find a weapon that finally matches your scale.
- You delete your name from death's book.
- Heaven humiliates you with a tiny position.
- You answer with "齐天大圣."

The middle high is deliberately overpowered:

- Banquet exclusion.
- Furnace rebirth.
- Heavenly battle.
- The feeling that all contempt can be hit back into the clouds.

Then the story drops:

- The world stops trying to defeat you and instead makes you unable to move.
- Five hundred years pass through rain, grass, snow, and footsteps.
- This section should be quiet, spacious, and painful.

The final act turns power into restraint:

- A human calls you by name.
- You carry power again, but now with a person to protect.
- The golden headband hurts.
- You want to smash the world again, but you lower the staff.
- The ending lands in a concrete image, not a lecture: cloud, rain over Flower-Fruit Mountain, and the monkey who still refuses to kneel inside you.

## Opening Design

Use `opening_style=life_shaker`.

Opening candidate terms:

- `石头里醒来`
- `水帘洞称王`
- `海底借棍`
- `地府划名`
- `火炉不死`
- `五百年雨`

Result title:

- `孙悟空`

Result tail:

- `的一生`

Opening TTS:

```text
每天一个模拟人生，今天你抽到孙悟空。
```

Opening visual tone:

- Life-object shaker/gacha machine adapted with mythic objects rather than gambling signals.
- Floating capsules contain stone dust, peach petals, a tiny red-gold staff, a torn heavenly notice, rain drops, and a mountain silhouette.
- No casino, slot machine, coin shower, jackpot, betting, or victory-payout SFX.

## Structure And Timing

Total target: about 4:25.

| Section | Target Time | Beat | Emotional Function |
|---|---:|---|---|
| Opening | 0:00-0:04 | Life shaker identity lock | Ritual hook |
| Stone Birth | 0:04-0:28 | You wake from stone and face a world with no place for you | Wonder and loneliness |
| First Recognition | 0:28-0:55 | You leap through the waterfall and become king | First爽点 |
| Learning Power | 0:55-1:22 | You chase immortality and learn transformation/cloud travel | Growth rush |
| Weapon And Death | 1:22-1:55 | Dragon palace staff and underworld name deletion | Destiny-breaking爽点 |
| Humiliation | 1:55-2:18 | Heaven gives you the stable job | Anger and class insult |
| Rebellion | 2:18-2:58 | Self-title, banquet exclusion, furnace, heavenly battle | Peak爽点 |
| Punishment | 2:58-3:32 | Five-Finger Mountain and five hundred years | Emotional crash |
| Being Seen | 3:32-3:52 | Tang Sanzang calls you Wukong | Warmth and rescue |
| Restraint | 3:52-4:22 | Golden headband, protecting the mortal, lowering the staff | Mature power |
| Aftertaste | 4:22-4:35 | Cloud-top return to Flower-Fruit Mountain rain | Quiet resonance |

If TTS measurement pushes the edit near 5 minutes, shorten the rebellion section first, not the mountain section. The five-hundred-year silence is the emotional hinge.

## Image Budget Estimate

For a 4:25 total duration with a 3.7-4.3 second opening and 1.0-3.0 second body micro-cuts, the body will likely need about 115-135 independent Krill `Image2` keyframes.

The estimate assumes:

- Average body micro-cut duration: about 2.0-2.3 seconds
- Longer holds for complex emotional scenes: 2.5-3.0 seconds
- Fast cuts for impact and reaction shots: 1.0-1.4 seconds

This is a high-image-count run. Generation should not start until the user accepts the image budget and the final tool chain.

## Visual Direction

Style prompt base:

```text
soft hand-drawn Chinese picture-book watercolor illustration, delicate pencil linework, textured paper grain, low-saturation warm palette, poetic negative space, dreamlike Chinese myth landscape, lonely but luminous mood, small expressive monkey protagonist, vast sky and mountains, gentle cinematic composition, no text, no logo, no watermark, vertical 9:16
```

Style notes:

- Use small figures in huge spaces to create mythic loneliness.
- Keep action scenes readable but not hyper-real. The staff can become a red-gold brushstroke cutting through clouds.
- Avoid heavy armor, game-like VFX, chrome weapons, sharp anime battle lighting, or movie-poster realism.
- Let emptiness carry emotion: sky, rain, mountain, blank paper, mist, and distance.
- All Chinese text, title cards, scene labels, and cover text should be added in post, not generated inside images.

## Character Continuity

Create reference images before body keyframes.

Sun Wukong reference anchors:

- A small golden-brown stone monkey with amber eyes.
- Red scarf, red cord, or red cloth strip as a consistent visual anchor.
- Expressive face: curious, defiant, wounded, then quietly steady.
- The staff is red-gold, elegant, and slightly brushlike.
- Do not design him as a direct copy of any known modern adaptation.

Three life-stage variants:

1. Stone monkey: bare, small, wet fur, red cord only, bright eyes.
2. Great Sage: red scarf/cloak, staff, confident posture, still compact and nimble rather than over-armored.
3. Pilgrimage Wukong: golden headband, dust on fur, calmer eyes, red anchor still visible.

Tang Sanzang reference anchors:

- Ordinary, fragile, human warmth.
- Not too grand or holy. The key contrast is that this vulnerable person sees you as someone with a name.
- Simple robe, umbrella or travel pack, soft lamp/warm light motif.

## Detailed Storyboard

Each row below is a story beat. During production, each beat should split into 1-3 second micro-cuts with unique Image2 frames.

| Beat | Visual | Voiceover Intent | Duration |
|---|---|---|---:|
| Identity Lock | Shaker locks on Sun Wukong | "今天你抽到孙悟空" | 4s |
| Stone Opens | Sea cliff stone cracks at dawn | You are not born, you wake | 8s |
| First Breath | Tiny monkey touches stone dust on palm | No parents, no name, only sky | 6s |
| Waterfall Decision | You stand before roaring waterfall | You decide not to wait for a place | 7s |
| Water Curtain | You burst through water into blue cave light | You earn "大王" | 8s |
| Fear Of Death | Night on Flower-Fruit Mountain, monkeys asleep | You fear losing everything | 8s |
| Journey To Master | Small figure walking through moonlit mist | You chase a loophole in heaven and earth | 8s |
| Learning Transformation | Leaves become birds, monkey blurs into forms | The world suddenly has keys | 10s |
| Cloud Leap | A tiny body above an enormous cloud sea | One leap changes your sense of scale | 7s |
| Dragon Palace | Blue-green underwater palace | You enter a place too large for mortals | 8s |
| Staff Wakes | Red-gold staff glows in your hands | The weapon finally matches you | 10s |
| Underworld | Black scroll, red brushstroke, shadowy halls | You cross out your own death | 10s |
| Heavenly Stable | Vast empty palace, tiny monkey near horses | Heaven gives you a small insult | 10s |
| Laughter Turns | You laugh in a cold corridor | You understand they never planned to see you | 8s |
| Flag Rises | Flower-Fruit Mountain flag in storm light | You name yourself Equal to Heaven | 10s |
| Banquet Exclusion | Bright banquet far above, you outside the door | No seat for you | 8s |
| Furnace | Orange-red watercolor fire surrounds your eyes | Fire fails and gives you sight | 10s |
| Heavenly Battle | Staff as red-gold brushstroke through clouds | You hit contempt back into the sky | 14s |
| Sudden Stillness | Huge hand/mountain descends, sound drops | The world stops fighting and pins you | 8s |
| Mountain Rain | Only one amber eye under gray stone | Five hundred years pass over your face | 15s |
| Seasons | Grass, snow, dry leaves, footsteps passing | People stop fearing and remembering you | 16s |
| Name Again | Monk with umbrella kneels near mountain crack | Someone calls you Wukong | 10s |
| Staff Returns | Dusty hand grips staff again | You are free, but not the same | 8s |
| White Bone Wind | Small traveling party in a huge pale landscape | You protect a fragile human road | 12s |
| Headband Pain | Close-up hand shaking on staff, headband glow | You want to smash everything again | 12s |
| Lowering Staff | You see the monk's frightened hand and lower the staff | Power becomes restraint | 12s |
| Cloud Return | Wukong on cloud looking toward rainy Flower-Fruit Mountain | The untamed monkey survives | 13s |

## Voiceover Script Draft

This is the body script draft. It should be measured with TTS before final timing. The final edit follows TTS duration as the timing truth.

```text
每天一个模拟人生，今天你抽到孙悟空。

你不是被生下来的。
你是从一块石头里，突然醒来的。

第一眼看见世界时，海在发亮，风从耳边穿过去。
没有人抱你，也没有人给你取名字。
你低头看着掌心的石粉，第一次明白：这一局，没人会替你安排位置。

所以你跳进瀑布。
水砸在脸上，像整座山都在拦你。
可你偏要往里冲。

当你从水帘后面站起来，洞里所有猴子都看着你。
那一刻，你终于拥有第一个名字。
他们叫你，大王。

可你很快发现，大王也会老，大王也会死。
夜里，花果山安静下来，你听见自己的心跳，比海浪还急。
你不想等天黑。
你想找到天地留下的漏洞。

于是你走很远的路，拜一个沉默的师父。
你学七十二变，学筋斗云，学把不可能折成一条小路。
第一次翻上云端时，你看见山河在脚下缩小。
你突然觉得，世界不是牢笼。
世界是一把还没打开的锁。

后来你下到龙宫。
海水压着耳膜，宫殿冷得像一场梦。
他们搬来金银，搬来铠甲，你都嫌轻。
直到那根沉在海底的铁柱醒过来。

它重得像一座山。
可落进你手里，轻得像命中注定。

你又闯进地府。
生死簿一页页翻开，黑字写着你的名字。
你没有求饶，也没有解释。
你只是拿起笔，一划。
从那天起，连阎王都留不住你。

你以为天庭终于会看见你。
可他们给你的第一个位置，叫弼马温。
一座天宫那么大，却只给你一间马厩。
他们要你低头，要你感恩，要你把羞辱当成赏赐。

你站在马槽旁边，忽然笑了。
因为你终于懂了。
不是你不够高。
是他们从来不想让你站起来。

所以你回到花果山，升起一面旗。
你说，我叫齐天大圣。
不是天封的。
是你自己把自己，放到天一样高。

蟠桃宴没有你的座位。
仙丹炉关住你的身体。
可火越烧，你的眼睛越亮。
等炉门炸开，你带着一双火眼金睛走出来。
那一刻，所有轻视你的声音，都像纸一样烧成灰。

十万天兵压下来。
云海翻卷，雷声贴着耳朵炸开。
你握紧金箍棒，一棍扫过去。
你不是只在打神仙。
你是在把所有说你不配的人，打回他们自己的高处。

可你后来才知道，世界最狠的地方，不是打不过你。
是它可以让你动不了。

那只巨大的手落下来时，天空突然安静。
山压住你的肩，泥土压住你的背。
你想抬头，却只能看见一条很窄的光。

五百年里，雨落在你的眼睛上。
草从石缝里长出来，又枯下去。
雪盖住你的耳朵，又慢慢化掉。
路人从你身边经过，先是害怕，后来好奇，最后连看都不看。

他们不再怕你。
也不再记得你。

直到有一天，一个凡人撑着伞，在山前蹲下来。
他不像天兵那样喊你妖猴。
也不像神仙那样喊你孽障。
他只是很轻地叫了一声：悟空。

你重新拿起金箍棒。
可这一次，棍子变重了。
因为它不只用来打碎天。
它还要护住一个会害怕、会走累、会念错经的凡人。

妖风来的时候，你还是想一棍打穿整片山河。
紧箍咒疼起来的时候，你恨得想把天地再砸一次。
可你看见师父发抖的手。
你看见他明明害怕，还是站在你身后。

于是你把棍子慢慢放低。

后来他们说，你成佛了。
可你站在云端，忽然想起花果山的第一场雨。
那时候你还没有名字，只有一双刚刚睁开的眼睛。

你终于明白，这一生最爽的一棍，
不是打上天庭那一棍。
是你被世界压弯过以后，
心里那只不肯认输的猴子，
还活着。
```

## Sample Image Prompts

Stone birth:

```text
a small golden-brown stone monkey standing beside a cracked sea cliff stone at sunrise, ocean mist, pale enormous sky, stone dust on tiny hands, soft hand-drawn Chinese picture-book watercolor illustration, delicate pencil linework, textured paper grain, lonely luminous mood, no text, no logo, vertical 9:16
```

Water Curtain Cave:

```text
a tiny monkey bursting through a roaring waterfall into a hidden cave glowing with blue light, other small monkeys watching in wonder, soft watercolor picture-book style, delicate pencil lines, poetic negative space, no text, no logo, vertical 9:16
```

Dragon palace staff:

```text
a small monkey king holding a glowing red-gold staff inside an underwater crystal palace, fish shadows drifting like paper cutouts, blue-green watercolor wash, dreamlike Chinese myth atmosphere, delicate pencil linework, no text, no logo, vertical 9:16
```

Underworld register:

```text
a small defiant monkey in a shadowy underworld hall, a long black life register scroll spread across the floor, a red brushstroke crossing a name area without readable text, ink mist, soft Chinese watercolor picture-book illustration, no text, no logo, vertical 9:16
```

Heavenly stable humiliation:

```text
a tiny monkey standing beside a quiet horse trough inside an enormous empty heavenly palace stable, high cold columns, pale gold distance, red scarf as the only warm color, delicate watercolor picture-book style, lonely mood, no text, no logo, vertical 9:16
```

Furnace rebirth:

```text
a small monkey silhouette inside swirling orange-red watercolor fire, amber eyes glowing brighter than the flames, soft paper texture, mythic but tender, no text, no logo, vertical 9:16
```

Heavenly battle:

```text
a small monkey sage sweeping a red-gold staff like a brushstroke through a vast cloud sea, tiny heavenly soldiers scattered as distant silhouettes, storm light, soft hand-drawn watercolor picture-book illustration, no text, no logo, vertical 9:16
```

Five-Finger Mountain:

```text
a small monkey trapped beneath a huge soft gray five-finger mountain, endless rain, only one amber eye visible from a stone crack, vast blank sky, poetic negative space, heartbreaking watercolor picture-book illustration, no text, no logo, vertical 9:16
```

Tang Sanzang arrives:

```text
a gentle monk kneeling with an umbrella before a mountain crack, warm lantern light touching the trapped monkey's face for the first time in centuries, rain falling softly, delicate Chinese picture-book watercolor, tender emotional composition, no text, no logo, vertical 9:16
```

Lowering the staff:

```text
a dust-covered monkey warrior lowering a red-gold staff while a fragile monk stands behind him with trembling hands, pale mountain road, quiet wind, soft watercolor picture-book style, restraint and tenderness, no text, no logo, vertical 9:16
```

Final cloud return:

```text
a small monkey sage standing on a cloud at dawn, looking toward distant Flower-Fruit Mountain under soft rain, red scarf moving in the wind, enormous pale sky, gentle hand-drawn watercolor picture-book illustration, lonely but hopeful mood, no text, no logo, vertical 9:16
```

## Audio Design

TTS:

- Provider: MiniMax via capsule default `male_narrator`
- Speed: `1.18`
- Tone: young, energetic, clear storytelling, not archival documentary
- Opening and body use the same voice/provider/speed/mix

BGM:

- Start with music-box, muted wood percussion, soft flute, and light strings.
- Add deeper drum and plucked string tension during rebellion.
- Strip back to rain, low drone, and sparse piano under Five-Finger Mountain.
- Return warm strings after Tang Sanzang appears.
- Keep BGM under narration, around 0.035-0.075 unless measured mix suggests otherwise.

SFX:

- Life shaker mechanical motion SFX from capsule asset.
- Stone crack, waterfall pressure, sea bubbles, brush crossing paper, stable ambience, furnace flame, cloud thunder, mountain impact, rain, headband high-frequency ring.
- Avoid jackpot, coin, casino, betting, victory payout, or gambling-adjacent sounds.

## On-Frame Text

Use sparse, large, readable text only.

Opening:

- `每天一个模拟人生`
- candidate terms
- `今天抽到`
- `孙悟空`
- `的一生`

Optional scene labels:

- `石头里醒来`
- `第一次被叫作大王`
- `把名字从死亡里划掉`
- `我叫齐天大圣`
- `五百年雨`
- `有人叫你：悟空`
- `把棍子慢慢放低`

Cover:

```text
你从石头里醒来
天地都不认你
```

Platform copy:

```text
如果你抽到孙悟空的一生，你会发现：
最爽的不是大闹天宫，
是五百年后，你还没有认输。
```

## Tool Chain Proposal

This is the proposed tool chain for a later generation run. It still requires explicit pre-generation confirmation before any paid or batch media generation.

| Role | Default Choice | Reason |
|---|---|---|
| Capsule route | `life_sim` local-script capsule | Matches second-person immersive life simulation and opening rules |
| Image keyframes | Krill AI `Image2` route | User requested default image channel; capsule requires unique Image2 keyframe per micro-cut |
| Style/character references | Krill `Image2` reference images first | Required for continuity across the high frame count |
| Motion/editing | Capsule local-script route with per-micro-cut storyboard package | Required by `life_sim` contract; no silent fallback to reused stills |
| Voice | MiniMax `male_narrator` | Capsule default, energetic male storytelling |
| BGM | Licensed online audio search/download first; generated music only if needed | Rights and release gate compliance |
| SFX | Capsule life-shaker SFX plus licensed/local SFX | Avoid gambling associations |
| Subtitles | Body subtitles off by default | Capsule default; only opening/labels visible |
| QA | Local video QA, visible copy lint, compliance review, micro-cut uniqueness report | Required release gates |

## Risks And Mitigations

- High image count: 115-135 unique body images is likely. Mitigation: keep the runtime below 4:40 and use longer 2.5-3.0 second holds for emotional paintings.
- Style drift: Sun Wukong may change across many images. Mitigation: generate reference images first and reuse stage-specific anchors.
- Over-action style: model may drift into game/anime battle poster. Mitigation: keep the style prompt anchored to picture-book watercolor and negative space.
- Text artifacts: image model may invent illegible Chinese text. Mitigation: every prompt says no text/logo/watermark; all text added in post.
- Detached biography: the myth is famous, so scripts can slip into "he did..." narration. Mitigation: script stays in second person and every major choice lands on "you."
- Ending moralization: the last line must be image-based and emotional, not a lesson.

## Acceptance Criteria

- Final planned duration remains under 5:00.
- Story is second-person throughout except brief outside pressure.
- The script contains a clear choice-consequence loop:
  - You reject an assigned place.
  - You seize power and self-name.
  - You enjoy short-term transcendence.
  - The world answers with immobility and time.
  - You later choose restraint while protecting another person.
- Every 10-15 seconds has a body, space, or object detail.
- Storyboard can be split into unique 1-3 second Krill Image2 keyframes.
- Opening text is readable and not gambling-coded.
- Body subtitles remain off by default.
- Visual direction avoids direct imitation of a specific living artist while preserving the requested tender picture-book mood.
