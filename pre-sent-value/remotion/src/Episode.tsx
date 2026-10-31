import React, {useMemo} from 'react';
import {AbsoluteFill, Audio, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Captions, Word} from '../../brand/Captions';
import {Intro, INTRO_FRAMES} from '../../brand/intro';
import {Outro, OUTRO_FRAMES} from '../../brand/outro';
import {audio, brand, colors, dbToGain, fonts} from '../../brand/theme';
import {MotionWrap} from './components/MotionWrap';
import {SceneVisual} from './components/SceneVisual';
import type {Episode as EpisodeT, EpisodeProps, Scene} from './types';

const TAIL_SECONDS = 0.6; // breath after the last word before the outro
const CLIP_CTA_FRAMES = 75; // 2.5 s "full story" card at the end of a short
const XFADE = 6; // frames of crossfade between scenes

export const bodySeconds = (ep: EpisodeT, words: Word[]) =>
  ep.narration_duration ??
  Math.max(0, ...ep.scenes.map((s) => s.end ?? 0), ...words.map((w) => w.end));

// Total frames, used by calculateMetadata in Root.tsx
export const episodeFrames = (props: EpisodeProps, fps: number) => {
  const {episode, words, clipId} = props;
  if (clipId) {
    const c = episode.clips.find((x) => x.id === clipId);
    if (!c) throw new Error(`clip ${clipId} not found`);
    return Math.round((c.end - c.start) * fps) + CLIP_CTA_FRAMES;
  }
  return INTRO_FRAMES + Math.round((bodySeconds(episode, words) + TAIL_SECONDS) * fps) + OUTRO_FRAMES;
};

const mergeSpeech = (words: Word[], pad = 0.15) => {
  const out: [number, number][] = [];
  for (const w of words) {
    const a = w.start - pad;
    const b = w.end + pad;
    if (out.length && a <= out[out.length - 1][1] + 0.4) out[out.length - 1][1] = Math.max(out[out.length - 1][1], b);
    else out.push([a, b]);
  }
  return out;
};

// Music bed: -22 dB under narration, rises softly in gaps, intro and outro.
const MusicBed: React.FC<{src: string; words: Word[]; narrationOffset: number; total: number; fromSec?: number}> = ({
  src,
  words,
  narrationOffset,
  total,
  fromSec = 0,
}) => {
  const {fps} = useVideoConfig();
  const speech = useMemo(() => mergeSpeech(words), [words]);
  return (
    <Audio
      src={src}
      loop
      volume={(f) => {
        const t = f / fps - narrationOffset + fromSec; // narration time
        let dist = Infinity;
        for (const [a, b] of speech) {
          if (t >= a && t <= b) {
            dist = 0;
            break;
          }
          dist = Math.min(dist, t < a ? a - t : t - b);
        }
        const k = Math.max(0, Math.min(1, 1 - dist / audio.duckAttackSec));
        const db = audio.musicDbNoVoice + (audio.musicDb - audio.musicDbNoVoice) * k;
        const fade = interpolate(f, [0, 12, total - 24, total], [0, 1, 1, 0], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
        return dbToGain(db) * fade;
      }}
    />
  );
};

const Scenes: React.FC<{scenes: Scene[]; slug: string; offsetFrames: number; fromSec?: number; toSec?: number}> = ({
  scenes,
  slug,
  offsetFrames,
  fromSec = 0,
  toSec = Infinity,
}) => {
  const {fps} = useVideoConfig();
  return (
    <>
      {scenes
        .filter((s) => s.start != null && s.end != null && s.end! > fromSec && s.start! < toSec)
        .map((s, i) => {
          const a = Math.max(s.start!, fromSec) - fromSec;
          const b = Math.min(s.end!, toSec) - fromSec;
          const from = offsetFrames + Math.round(a * fps) - (i ? XFADE : 0);
          const dur = Math.max(1, Math.round((b - a) * fps) + (i ? XFADE : 0));
          return (
            <Sequence key={s.id} from={from} durationInFrames={dur} name={s.id}>
              <SceneFade first={i === 0}>
                <MotionWrap motion={s.motion} durationInFrames={dur} seed={s.id}>
                  <SceneVisual scene={s} slug={slug} durationInFrames={dur} />
                </MotionWrap>
              </SceneFade>
              {s.sfx && <Audio src={staticFile(`brand/sfx/${s.sfx}`)} volume={dbToGain(-12)} />}
            </Sequence>
          );
        })}
    </>
  );
};

const SceneFade: React.FC<{first: boolean; children: React.ReactNode}> = ({first, children}) => {
  const f = useCurrentFrame();
  const o = first ? 1 : interpolate(f, [0, XFADE], [0, 1], {extrapolateRight: 'clamp'});
  return <AbsoluteFill style={{opacity: o}}>{children}</AbsoluteFill>;
};

const Vignette = () => (
  <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 50%, transparent 55%, rgba(8,17,31,0.55) 100%)', pointerEvents: 'none'}} />
);

const ClipHook: React.FC<{text: string}> = ({text}) => {
  const f = useCurrentFrame();
  const {height} = useVideoConfig();
  const o = interpolate(f, [0, 6, 80, 95], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{alignItems: 'center', paddingTop: height * 0.13, opacity: o}}>
      <div
        style={{
          background: colors.gold,
          color: colors.navy,
          fontFamily: fonts.display,
          fontWeight: 900,
          fontSize: 64,
          lineHeight: 1.1,
          padding: '22px 36px',
          borderRadius: 18,
          maxWidth: '80%',
          textAlign: 'center',
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};

const ClipCta: React.FC<{text: string}> = ({text}) => (
  <AbsoluteFill style={{background: colors.navy, justifyContent: 'center', alignItems: 'center', padding: '0 10%'}}>
    <div style={{fontFamily: fonts.display, fontWeight: 900, fontSize: 84, color: colors.gold, textAlign: 'center', lineHeight: 1.1}}>
      {text}
    </div>
    <div style={{fontFamily: fonts.sans, fontWeight: 700, fontSize: 40, color: colors.parchment, marginTop: 40, letterSpacing: '0.1em'}}>
      {brand.channelName}
    </div>
  </AbsoluteFill>
);

export const Episode: React.FC<EpisodeProps> = (props) => {
  const {episode, words, narrationSrc, musicSrc, clipId} = props;
  const {fps, durationInFrames} = useVideoConfig();
  const music = musicSrc ? staticFile(musicSrc) : null;
  const narration = narrationSrc ? staticFile(narrationSrc) : null;

  if (clipId) {
    const c = episode.clips.find((x) => x.id === clipId)!;
    const bodyFrames = durationInFrames - CLIP_CTA_FRAMES;
    const clipWords = words.filter((w) => w.start >= c.start - 0.05 && w.end <= c.end + 0.05);
    return (
      <AbsoluteFill style={{background: colors.navy}}>
        <Scenes scenes={episode.scenes} slug={episode.slug} offsetFrames={0} fromSec={c.start} toSec={c.end} />
        <Vignette />
        <Captions words={clipWords} offsetSeconds={-c.start} />
        <Sequence durationInFrames={95}>
          <ClipHook text={c.hook} />
        </Sequence>
        <Sequence from={bodyFrames}>
          <ClipCta text={c.cta} />
        </Sequence>
        {narration && (
          <Sequence durationInFrames={bodyFrames}>
            <Audio src={narration} startFrom={Math.round(c.start * fps)} />
          </Sequence>
        )}
        {music && <MusicBed src={music} words={clipWords} narrationOffset={0} fromSec={c.start} total={durationInFrames} />}
      </AbsoluteFill>
    );
  }

  const off = INTRO_FRAMES;
  const outroAt = durationInFrames - OUTRO_FRAMES;
  return (
    <AbsoluteFill style={{background: colors.navy}}>
      <Sequence from={off} durationInFrames={outroAt - off}>
        <Scenes scenes={episode.scenes} slug={episode.slug} offsetFrames={0} />
        <Vignette />
        <Captions words={words} />
      </Sequence>
      <Sequence durationInFrames={INTRO_FRAMES + 2}>
        <Intro />
      </Sequence>
      <Sequence from={outroAt}>
        <Outro />
      </Sequence>
      {narration && (
        <Sequence from={off}>
          <Audio src={narration} />
        </Sequence>
      )}
      <Sequence from={22} durationInFrames={30}>
        <Audio src={staticFile('brand/sfx/coin.mp3')} volume={dbToGain(-8)} />
      </Sequence>
      {music && <MusicBed src={music} words={words} narrationOffset={off / fps} total={durationInFrames} />}
    </AbsoluteFill>
  );
};
