import React, {useMemo} from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {colors, fonts, safeZone} from './theme';

export type Word = {word: string; start: number; end: number};

type Page = {start: number; end: number; words: Word[]};

// Group words into short caption "pages": break on sentence-ending
// punctuation, on pauses, or when the page is full.
export const paginate = (words: Word[], maxWords: number, maxChars: number): Page[] => {
  const pages: Page[] = [];
  let cur: Word[] = [];
  const flush = () => {
    if (cur.length) pages.push({start: cur[0].start, end: cur[cur.length - 1].end, words: cur});
    cur = [];
  };
  words.forEach((w, i) => {
    const prev = words[i - 1];
    const chars = cur.reduce((n, x) => n + x.word.trim().length + 1, 0) + w.word.trim().length;
    if (cur.length && (cur.length >= maxWords || chars > maxChars || (prev && w.start - prev.end > 0.6))) flush();
    cur.push(w);
    if (/[.!?;:]["”’)]?$/.test(w.word.trim())) flush();
  });
  flush();
  // Hold each page until the next begins (no flicker in short gaps < 0.6 s).
  for (let i = 0; i < pages.length - 1; i++) {
    const gap = pages[i + 1].start - pages[i].end;
    if (gap < 0.6) pages[i].end = pages[i + 1].start;
  }
  return pages;
};

// Burned-in, word-by-word captions. `offsetSeconds` is where the narration
// starts within the composition (e.g. after the intro).
export const Captions: React.FC<{words: Word[]; offsetSeconds?: number}> = ({words, offsetSeconds = 0}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const portrait = height > width;
  const sz = portrait ? safeZone.portrait : safeZone.landscape;
  const pages = useMemo(
    () => paginate(words, portrait ? 3 : 6, portrait ? 18 : 34),
    [words, portrait],
  );
  const t = frame / fps - offsetSeconds;
  const page = pages.find((p) => t >= p.start && t < p.end + 0.15);
  if (!page) return null;

  const fontSize = portrait ? 84 : 70;
  return (
    <AbsoluteFill
      style={{
        justifyContent: 'flex-end',
        alignItems: 'center',
        paddingLeft: width * sz.left,
        paddingRight: width * sz.right,
        // portrait: sit in the lower-middle, above the platform UI
        paddingBottom: portrait ? height * 0.3 : height * sz.bottom,
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'center',
          gap: `${fontSize * 0.12}px ${fontSize * 0.26}px`,
          maxWidth: portrait ? '100%' : '82%',
          background: 'rgba(8,17,31,0.78)',
          padding: `${fontSize * 0.2}px ${fontSize * 0.38}px`,
          borderRadius: fontSize * 0.28,
          boxShadow: '0 8px 30px rgba(0,0,0,0.35)',
          fontFamily: fonts.sans,
          fontWeight: 800,
          fontSize,
          lineHeight: 1.15,
          textAlign: 'center',
        }}
      >
        {page.words.map((w, i) => {
          const active = t >= w.start && t < (page.words[i + 1]?.start ?? page.end + 0.15);
          const spoken = t >= w.start;
          return (
            <span
              key={i}
              style={{
                color: active ? colors.navy : colors.parchment,
                background: active ? colors.gold : 'transparent',
                borderRadius: fontSize * 0.14,
                padding: `0 ${fontSize * 0.1}px`,
                margin: `0 -${fontSize * 0.1}px`,
                opacity: spoken ? 1 : 0.55,
                transform: active ? 'scale(1.06)' : 'scale(1)',
                textShadow: active
                  ? 'none'
                  : `0 0 ${fontSize * 0.12}px ${colors.navyDeep}, 0 ${fontSize * 0.04}px ${fontSize * 0.08}px ${colors.navyDeep}, 0 0 2px ${colors.navyDeep}`,
              }}
            >
              {w.word.trim()}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
