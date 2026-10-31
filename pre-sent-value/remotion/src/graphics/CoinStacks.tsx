import React from 'react';
import {AbsoluteFill, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {colors, fonts} from '../../../brand/theme';

// Columns of coins that rise (or drain away). params:
//  stacks: number[]   coins per column at the end state
//  from:   number[]   optional starting counts (animate from -> stacks)
//  labels: string[]   optional caption under each column
export type CoinStacksParams = {stacks: number[]; from?: number[]; labels?: string[]; title?: string};

export const CoinStacks: React.FC<{params: CoinStacksParams}> = ({params}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const portrait = height > width;
  const coinW = portrait ? 200 : 210;
  const coinH = coinW * 0.26;
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 60%, ${colors.navySoft}, ${colors.navyDeep})`,
        justifyContent: 'center',
        alignItems: 'center',
        paddingBottom: height * (portrait ? 0.42 : 0.12),
      }}
    >
      {params.title && (
        <div style={{position: 'absolute', top: height * 0.14, fontFamily: fonts.display, fontWeight: 900, fontSize: portrait ? 80 : 72, color: colors.parchment}}>
          {params.title}
        </div>
      )}
      <div style={{display: 'flex', alignItems: 'flex-end', gap: coinW * 0.5, height: height * (portrait ? 0.35 : 0.55)}}>
        {params.stacks.map((target, i) => {
          const start = params.from?.[i] ?? 0;
          const t = spring({frame: frame - 6 - i * 6, fps, config: {damping: 200}, durationInFrames: 40});
          const n = Math.round(start + (target - start) * t);
          return (
            <div key={i} style={{display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
              <div style={{display: 'flex', flexDirection: 'column-reverse'}}>
                {Array.from({length: n}).map((_, j) => (
                  <div
                    key={j}
                    style={{
                      width: coinW,
                      height: coinH,
                      marginTop: -coinH * 0.45,
                      borderRadius: '50%',
                      background: `linear-gradient(${colors.goldLight}, ${colors.gold} 55%, ${colors.goldDark})`,
                      border: `3px solid ${colors.goldDark}`,
                    }}
                  />
                ))}
              </div>
              {params.labels?.[i] && (
                <div style={{fontFamily: fonts.sans, fontWeight: 800, fontSize: portrait ? 42 : 36, color: colors.parchment, marginTop: 24}}>
                  {params.labels[i]}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
