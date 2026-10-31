# PROGRESS

## Done — Phase 1 (scaffold) → CHECKPOINT 1
- Repo layout, Python CLI (`pv new | script | voice | captions | render | qc | brand-assets`), API cache, pytest (5 passing).
- Remotion 4.0.539 project: `Episode16x9`, `Episode9x16` (clip mode with hook card + "full story" CTA), `Intro*`, `Outro*`, `Thumbnail`.
- Brand kit: `brand/theme.ts` (navy / gold / parchment, Playfair Display + Inter), coin-flip intro (2 s), "Value compounds" outro (3 s), word-by-word caption component, logo SVG.
- Reusable graphics so far: `map_route` (Egypt → Levant → Cyprus, animated route), `coin_stacks`, `text_card`; motions kenburns / pan / zoom / reveal.
- Placeholder music bed and SFX, synthesized locally (original, no licence needed).
- 10-second test render: `episodes/000-pipeline-test/out/final-16x9.mp4` (+ a 9:16 test clip and a thumbnail).

## Next — Phase 2 (Episode 1: Wenamun), after you approve Checkpoint 1
1. Research → `episodes/001-wenamun/research.md` with source URLs and uncertainty flags.
2. Script (420–480 words, 4 acts, 2 alternative hooks, 2–3 clip candidates) + scene list → **CHECKPOINT 2** (no audio before approval).
3. Voice → captions → images + more graphics (ledger, ship / cedar barge, timeline) → render → QC → **CHECKPOINT 3**.

## Needs you (by hand)
- [ ] Create `.env` from `.env.example` with `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID` (pick the one channel voice).
- [ ] **Network access in this cloud environment:** outbound requests to `huggingface.co` (Whisper model download), `api.elevenlabs.io`, `commons.wikimedia.org` / `upload.wikimedia.org`, `images.metmuseum.org`, `www.loc.gov` and `archive.org` are all blocked by the environment's network policy. Either allow those domains (environment settings → Network access → Allowed domains, see https://code.claude.com/docs/en/cloud-environments#network-access), or run `voice`, `captions` and image sourcing on your own machine.
- [ ] Licensed music: drop it in `brand/music/` (see README → "Music and SFX").
- [ ] Optional: `ANTHROPIC_API_KEY` if you want `pv script --draft`.
