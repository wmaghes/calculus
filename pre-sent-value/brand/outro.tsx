import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Coin} from './Coin';
import {brand, colors, fonts} from './theme';

// Signature close (~3 s): "Value compounds. See you next time." + follow prompt.
// A small stack of coins grows beside the line — value compounding.
export const OUTRO_FRAMES = 90;

export const Outro: React.FC<{followPrompt?: string}> = ({followPrompt = brand.followPrompt}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const portrait = height > width;
  const base = portrait ? 92 : 104;

  const fade = (start: number, dur = 12) =>
    interpolate(frame, [start, start + dur], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const pop = spring({frame: frame - 44, fps, config: {damping: 12, stiffness: 160}});
  const out = interpolate(frame, [OUTRO_FRAMES - 8, OUTRO_FRAMES], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const coins = [0, 1, 2, 3, 4];
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 50%, ${colors.navySoft} 0%, ${colors.navy} 60%, ${colors.navyDeep} 100%)`,
        justifyContent: 'center',
        alignItems: 'center',
        opacity: out,
      }}
    >
      <div style={{display: 'flex', alignItems: 'flex-end', height: base * 2.0, marginBottom: base * 0.5}}>
        {coins.map((i) => {
          const s = spring({frame: frame - 4 - i * 5, fps, config: {damping: 14, stiffness: 180}});
          const stackHeight = [1, 2, 3, 5, 8][i]; // growth that compounds
          return (
            <div key={i} style={{display: 'flex', flexDirection: 'column-reverse', margin: `0 ${base * 0.06}px`}}>
              {Array.from({length: stackHeight}).map((_, j) => (
                <div
                  key={j}
                  style={{
                    width: base * 0.8,
                    height: base * 0.22,
                    marginTop: -base * 0.04,
                    borderRadius: '50%',
                    background: `linear-gradient(${colors.goldLight}, ${colors.gold} 50%, ${colors.goldDark})`,
                    border: `2px solid ${colors.goldDark}`,
                    transform: `translateY(${(1 - s) * -base * 0.8}px)`,
                    opacity: Math.min(1, s * 1.5),
                  }}
                />
              ))}
            </div>
          );
        })}
      </div>
      <div
        style={{
          fontFamily: fonts.display,
          fontWeight: 900,
          fontSize: base,
          color: colors.gold,
          opacity: fade(8),
          transform: `translateY(${(1 - fade(8)) * 20}px)`,
          textAlign: 'center',
        }}
      >
        {brand.outroLine1}
      </div>
      <div
        style={{
          fontFamily: fonts.display,
          fontWeight: 700,
          fontSize: base * 0.62,
          color: colors.parchment,
          opacity: fade(22),
          marginTop: base * 0.2,
          textAlign: 'center',
        }}
      >
        {brand.outroLine2}
      </div>
      <div
        style={{
          marginTop: base * 0.6,
          display: 'flex',
          alignItems: 'center',
          gap: base * 0.18,
          padding: `${base * 0.16}px ${base * 0.36}px`,
          borderRadius: base,
          background: colors.parchment,
          color: colors.navy,
          fontFamily: fonts.sans,
          fontWeight: 800,
          fontSize: base * 0.3,
          transform: `scale(${pop})`,
          letterSpacing: '0.02em',
        }}
      >
        <Coin size={base * 0.42} />
        {followPrompt}
      </div>
    </AbsoluteFill>
  );
};
