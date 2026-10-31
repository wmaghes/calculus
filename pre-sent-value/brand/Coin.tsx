import React from 'react';
import {colors, fonts} from './theme';

// A flat-vector gold coin with an embossed "$". Reused by the intro, the
// "coins and ledger" graphics, and thumbnails.
export const Coin: React.FC<{
  size: number;
  symbol?: string;
  // 0..1 — how much of the face is visible (cos of the flip angle). Negative = back.
  faceScale?: number;
  style?: React.CSSProperties;
}> = ({size, symbol = '$', faceScale = 1, style}) => {
  const showFace = faceScale >= 0;
  const sx = Math.max(Math.abs(faceScale), 0.04);
  return (
    <div style={{width: size, height: size, position: 'relative', ...style}}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 100 100"
        style={{transform: `scaleX(${sx})`, overflow: 'visible'}}
      >
        <defs>
          <radialGradient id="coinFace" cx="38%" cy="32%" r="75%">
            <stop offset="0%" stopColor={colors.goldLight} />
            <stop offset="55%" stopColor={colors.gold} />
            <stop offset="100%" stopColor={colors.goldDark} />
          </radialGradient>
        </defs>
        <circle cx="50" cy="50" r="49" fill={colors.goldDark} />
        <circle cx="50" cy="50" r="46" fill="url(#coinFace)" />
        <circle
          cx="50"
          cy="50"
          r="39"
          fill="none"
          stroke={colors.goldDark}
          strokeWidth="1.6"
          strokeDasharray="2 2.2"
          opacity={0.7}
        />
        {showFace ? (
          <text
            x="50"
            y="51"
            textAnchor="middle"
            dominantBaseline="central"
            fontFamily={fonts.display}
            fontWeight={900}
            fontSize="62"
            fill={colors.navy}
            opacity={0.88}
          >
            {symbol}
          </text>
        ) : (
          <g fill="none" stroke={colors.goldDark} strokeWidth="3" opacity={0.8}>
            <path d="M30 60 L50 32 L70 60 Z" />
            <line x1="26" y1="66" x2="74" y2="66" />
          </g>
        )}
      </svg>
    </div>
  );
};
