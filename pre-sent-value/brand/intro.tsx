import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {Coin} from './Coin';
import {brand, colors, fonts} from './theme';

// Signature opening (~2 s): a coin flips through the air and settles into the
// "$" of "Pre$ent", then the tagline appears.
export const INTRO_FRAMES = 60;

export const Intro: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const portrait = height > width;
  const fontSize = portrait ? 118 : 150;
  const coinSize = fontSize * 1.0;

  // Drop: coin falls from above into its slot with a little bounce.
  const drop = spring({frame, fps, config: {damping: 11, stiffness: 120, mass: 0.9}, durationInFrames: 26});
  const y = interpolate(drop, [0, 1], [-height * 0.55, 0]);

  // Flip: several turns that decelerate and end face-on.
  const turns = interpolate(frame, [0, 28], [4.0, 0], {
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const faceScale = Math.cos(turns * Math.PI * 2);

  // Landing flash + wordmark reveal.
  const textIn = interpolate(frame, [4, 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const flash = interpolate(frame, [22, 26, 38], [0, 0.85, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const tagIn = interpolate(frame, [22, 34], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const outFade = interpolate(frame, [INTRO_FRAMES - 6, INTRO_FRAMES], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const textStyle: React.CSSProperties = {
    fontFamily: fonts.display,
    fontWeight: 900,
    fontSize,
    color: colors.parchment,
    lineHeight: 1,
    letterSpacing: '-0.01em',
  };

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 45%, ${colors.navySoft} 0%, ${colors.navy} 55%, ${colors.navyDeep} 100%)`,
        justifyContent: 'center',
        alignItems: 'center',
        opacity: outFade,
      }}
    >
      <div
        style={{
          fontFamily: fonts.sans,
          fontWeight: 700,
          fontSize: fontSize * 0.22,
          letterSpacing: '0.45em',
          color: colors.gold,
          opacity: textIn,
          marginBottom: fontSize * 0.18,
          textTransform: 'uppercase',
        }}
      >
        {brand.wordmarkPrefix}
      </div>
      <div
        style={{
          display: 'flex',
          flexDirection: portrait ? 'column' : 'row',
          alignItems: 'center',
          gap: portrait ? fontSize * 0.1 : fontSize * 0.28,
        }}
      >
        <div style={{display: 'flex', alignItems: 'center'}}>
          <span style={{...textStyle, opacity: textIn}}>{brand.wordmarkBefore}</span>
          <div style={{width: coinSize * 0.86, height: coinSize, position: 'relative', margin: `0 ${fontSize * 0.02}px`}}>
            <div
              style={{
                position: 'absolute',
                left: (coinSize * 0.86 - coinSize) / 2,
                top: fontSize * 0.04,
                transform: `translateY(${y}px)`,
                filter: `drop-shadow(0 ${fontSize * 0.06}px ${fontSize * 0.1}px rgba(0,0,0,0.45)) brightness(${1 + flash * 0.5})`,
              }}
            >
              <Coin size={coinSize} faceScale={faceScale} />
            </div>
          </div>
          <span style={{...textStyle, opacity: textIn}}>{brand.wordmarkAfter.split(' ')[0]}</span>
        </div>
        <span style={{...textStyle, opacity: textIn}}>{brand.wordmarkAfter.split(' ').slice(1).join(' ')}</span>
      </div>
      <div
        style={{
          marginTop: fontSize * 0.42,
          fontFamily: fonts.display,
          fontStyle: 'italic',
          fontWeight: 700,
          fontSize: fontSize * (portrait ? 0.34 : 0.3),
          color: colors.goldLight,
          opacity: tagIn,
          transform: `translateY(${(1 - tagIn) * 16}px)`,
          textAlign: 'center',
          padding: '0 8%',
        }}
      >
        {brand.tagline}
      </div>
    </AbsoluteFill>
  );
};
