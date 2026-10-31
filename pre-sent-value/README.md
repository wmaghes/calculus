# The Pre$ent Value — production pipeline

*Gaining the world's interest in business.* A faceless, animated finance-history channel.
One ~3-minute story per episode (16:9 master) plus 2–3 vertical 30–60 s clips.

Educational content only, not financial advice. No sponsorships or affiliate links.

## Quick start

```bash
# 1. Python (3.11+)
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# 2. Remotion (Node 18+), plus FFmpeg on PATH
cd remotion && npm install && cd ..

# 3. Keys
cp .env.example .env      # fill in ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID (ANTHROPIC_API_KEY optional)

# 4. Placeholder music + SFX (original, synthesized locally; no licensing needed)
python -m pv brand-assets

# 5. Smoke test: 10-second render (intro → map + coins with captions → outro)
python -m pv render 000-pipeline-test
```

## The CLI

| command | what it does | costs money? |
|---|---|---|
| `python -m pv new <slug> [--title T]` | scaffold `episodes/NNN-<slug>/` from `templates/episode/` | no |
| `python -m pv script <ep> --export` | `episode.json` → `script.md` for review | no |
| `python -m pv script <ep> --import` | your edited / pasted `script.md` → narration in `episode.json` | no |
| `python -m pv script <ep> --draft` | drafts `script.draft.md` from `research.md` with the Anthropic API | yes (cached) |
| `python -m pv voice <ep>` | ElevenLabs narration → `audio/narration.mp3`. Refuses until `"approved_script": true`, then asks before spending | yes (cached) |
| `python -m pv captions <ep>` | faster-whisper word timings → `audio/words.json`, then snaps scene/act/clip times to the narration | no (local) |
| `python -m pv render <ep> [--only master\|clips\|thumbnail]` | 16:9 master, 9:16 clips, thumbnail; loudness-normalised to −14 LUFS | no |
| `python -m pv qc <ep>` | runtime, clipping, caption/audio match, attribution, contiguity, LUFS → `out/qc.md` | no |
| `python -m pv brand-assets [--force]` | regenerate placeholder music + SFX | no |

`<ep>` can be `001-wenamun`, `001` or `wenamun`.

**Caching.** Every ElevenLabs and Anthropic request is hashed (text + voice + model + settings) and stored in `.cache/`.
Re-running `voice` or `render` with an unchanged script costs nothing. Whisper results are cached by audio hash.

## How an episode flows

```
research.md ─► script.md ◄─► episode.json ─► pv voice ─► pv captions ─► pv render ─► pv qc
                    (CHECKPOINT: approve script)          (scene times snapped to narration)
```

`episode.json` is the single source of truth. Remotion receives it (plus the word timings from
`audio/words.json`) as input props written by `pv render`, and reads nothing else for content.

Scene fields: `id`, `act`, `narration`, `start`/`end` (filled by `pv captions`), `visual`
(`type`: `archival_image | map | animated_graphic | text_card`, plus `file` / `prompt` / `graphic` + `params` / `text`),
`motion` (`kenburns | pan | zoom | reveal`), `sfx` (a file in `brand/sfx/`), `source_ref` (a source number in `research.md`).

Clips: `{"id", "from_scene", "to_scene", "hook", "cta"}`. `pv captions` fills in `start`/`end`.

## Layout

```
brand/        theme.ts (palette, fonts, safe zones, audio levels), Coin.tsx, intro.tsx, outro.tsx,
              Captions.tsx, logo/, music/, sfx/
episodes/NNN-slug/  episode.json, script.md, research.md, assets/ (+attribution.csv), audio/, out/
pv/           Python CLI
remotion/     compositions (Episode16x9, Episode9x16, Intro*, Outro*, Thumbnail) + reusable graphics
templates/    episode template used by `pv new`
tests/        pytest
```

## Brand kit

* **Palette:** deep navy `#0E1B33`, warm gold `#C9A227`, parchment `#F3EAD3` (see `brand/theme.ts`).
* **Type:** Playfair Display (display serif) and Inter (captions). Both SIL Open Font License, bundled through `@fontsource`.
* **Signature open (2 s):** a coin flips, drops and settles as the "$" in "Pre$ent", then the tagline appears.
* **Signature close (3 s):** "Value compounds. See you next time." with compounding coin stacks and a follow prompt.
* **Captions:** big word-by-word captions on a navy plate, with the current word highlighted in gold. Safe-zone aware: in 9:16 they sit at about 70% height, clear of the Shorts/Reels/TikTok UI.

### Music and SFX: where to drop licensed files

The included audio is **original and synthesized by `pv brand-assets`**. Nothing is downloaded, so there is no licence to track.
To replace it:

* **Music bed:** put the licensed track at `brand/music/<name>.mp3` and set `"music": "<name>.mp3"` in the episode's `episode.json`, or overwrite `brand/music/placeholder-bed.mp3` to change it for every episode. It is looped, held at −22 dB under narration, rises to −16 dB in gaps, intro and outro, and fades at both ends. Levels are in `brand/theme.ts → audio`.
* **SFX:** overwrite any of `brand/sfx/{coin,whoosh,impact,waves,quill}.mp3`, or add new files and reference them in a scene's `sfx`.
* Keep the licence or receipt for every track in `brand/music/LICENSES.md`. Use only sources whose licence covers YouTube monetisation, such as YouTube Audio Library or a paid library subscription.

## Images

Use only public-domain or openly licensed images: Wikimedia Commons, Met Open Access, Library of Congress, Smithsonian Open Access, or Internet Archive public-domain material.
Every image goes in `assets/` and gets a row in `assets/attribution.csv` (`file,title,source_url,license,author`).
`pv qc` fails if any image is missing its row. No photos of living public figures. Animated graphics fill the gaps.

## Adding a second channel

1. `cp -r brand ../brand-otherchannel` (or keep it inside this repo as `brand-otherchannel/`).
2. Edit `theme.ts` there: `brand` names, tagline, outro lines, `colors`, `fonts` (change the `@fontsource` imports too).
3. Swap `music/`, `sfx/` and `logo/`.
4. Run any command with `PV_BRAND_DIR=/path/to/brand-otherchannel`. Remotion components import from `brand/` by relative path, so for a fully separate look either point a copy of `remotion/` at the new folder or keep one repo per channel. One repo per channel is recommended: it is simplest and keeps histories apart.

## Decisions made (and why)

* **Location:** this repo started as a calculus textbook, so the pipeline lives in the `pre-sent-value/` subfolder on branch `claude/pre-sent-value`. It is fully self-contained. Move it to its own repo whenever you like.
* **Narration** is one ElevenLabs request for the whole script rather than one per scene. That gives consistent prosody, and Whisper recovers the per-scene timing. `eleven_multilingual_v2` with fixed voice settings, so every episode sounds the same.
* **Captions show the script's spelling** (e.g. "Pre$ent", "Wenamun"). Whisper only supplies the timing, aligned word-by-word with a diff, and any words it misses are interpolated.
* **Loudness:** two-pass FFmpeg `loudnorm` to −14 LUFS, −1.5 dBTP, video stream copied. It is skipped for renders with no narration (the music-only test), because normalising a quiet music bed would pump it up.
* **Rendered media** (`*.mp4`, narration mp3s) is git-ignored, except the tiny Phase 1 test render. Everything can be re-rendered for free from cache.
* **Maps** are hand-simplified coastlines (in `remotion/src/graphics/MapRoute.tsx`), drawn for storytelling, not cartographic precision.
* **Browser:** Remotion uses a pre-installed headless Chrome if `REMOTION_BROWSER` is set or one is found. Otherwise it downloads its own on first render.
* Default script-drafting model: `claude-opus-5-5` (override with `ANTHROPIC_MODEL`). Drafting is opt-in (`--draft`); pasting your own script is the default path.
