import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import type {Motion} from '../types';

// Camera move applied to any scene visual. Deterministic per scene id so
// consecutive Ken Burns shots drift in different directions.
export const MotionWrap: React.FC<{
  motion: Motion;
  durationInFrames: number;
  seed: string;
  children: React.ReactNode;
}> = ({motion, durationInFrames, seed, children}) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame, [0, Math.max(1, durationInFrames)], [0, 1], {
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.sin),
  });
  const h = [...seed].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7);
  const dir = h % 2 ? 1 : -1;
  const dirY = (h >> 1) % 2 ? 1 : -1;

  let transform = '';
  let clipPath: string | undefined;
  switch (motion) {
    case 'kenburns': {
      const s = 1.06 + 0.1 * t;
      transform = `scale(${s}) translate(${dir * 2.2 * t}%, ${dirY * 1.4 * t}%)`;
      break;
    }
    case 'pan':
      transform = `scale(1.18) translateX(${dir * (-6 + 12 * t)}%)`;
      break;
    case 'zoom':
      transform = `scale(${1 + 0.22 * t})`;
      break;
    case 'reveal': {
      const r = interpolate(frame, [0, 18], [0, 100], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
      clipPath = `inset(0 ${100 - r}% 0 0)`;
      transform = `scale(${1.02 + 0.04 * t})`;
      break;
    }
  }
  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <AbsoluteFill style={{transform, clipPath, transformOrigin: '50% 50%'}}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};
