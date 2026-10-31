import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {colors, fonts} from '../../../brand/theme';

// Parchment card with a display line (dates, quotes, the lesson).
export const TextCard: React.FC<{text: string; subtext?: string}> = ({text, subtext}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const portrait = height > width;
  const inT = interpolate(frame, [0, 12], [0, 1], {extrapolateRight: 'clamp'});
  const sub = interpolate(frame, [10, 22], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const size = (portrait ? 96 : 110) * (text.length > 40 ? 0.7 : 1);
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 40%, ${colors.parchment} 0%, ${colors.parchmentDark} 100%)`,
        justifyContent: 'center',
        alignItems: 'center',
        padding: portrait ? '0 9%' : '0 12%',
      }}
    >
      <div style={{width: '22%', height: 4, background: colors.gold, marginBottom: size * 0.45, transform: `scaleX(${inT})`}} />
      <div
        style={{
          fontFamily: fonts.display,
          fontWeight: 900,
          fontSize: size,
          lineHeight: 1.1,
          color: colors.ink,
          textAlign: 'center',
          opacity: inT,
          transform: `translateY(${(1 - inT) * 24}px)`,
        }}
      >
        {text}
      </div>
      {subtext && (
        <div
          style={{
            fontFamily: fonts.sans,
            fontWeight: 700,
            fontSize: size * 0.32,
            letterSpacing: '0.18em',
            textTransform: 'uppercase',
            color: colors.goldDark,
            marginTop: size * 0.4,
            textAlign: 'center',
            opacity: sub,
          }}
        >
          {subtext}
        </div>
      )}
    </AbsoluteFill>
  );
};
