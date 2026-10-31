import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {Coin} from '../../brand/Coin';
import {brand, colors, fonts} from '../../brand/theme';

export type ThumbnailProps = {title: string; kicker?: string; episodeSlug: string | null; image: string | null};

// High-contrast thumbnail: big two-line serif title, gold accent, coin badge.
export const Thumbnail: React.FC<ThumbnailProps> = ({title, kicker, episodeSlug, image}) => (
  <AbsoluteFill style={{background: colors.navy}}>
    {image && episodeSlug && (
      <Img
        src={staticFile(`episodes/${episodeSlug}/${image}`)}
        style={{position: 'absolute', right: 0, width: '62%', height: '100%', objectFit: 'cover', filter: 'contrast(1.1) saturate(0.9)'}}
      />
    )}
    <AbsoluteFill style={{background: `linear-gradient(90deg, ${colors.navy} 38%, rgba(14,27,51,0.65) 62%, rgba(14,27,51,0.1) 100%)`}} />
    <AbsoluteFill style={{padding: '90px 100px', justifyContent: 'center'}}>
      {kicker && (
        <div style={{fontFamily: fonts.sans, fontWeight: 800, fontSize: 52, letterSpacing: '0.2em', color: colors.gold, textTransform: 'uppercase'}}>
          {kicker}
        </div>
      )}
      <div
        style={{
          fontFamily: fonts.display,
          fontWeight: 900,
          fontSize: 170,
          lineHeight: 0.98,
          color: colors.parchment,
          maxWidth: '62%',
          marginTop: 24,
          textShadow: `0 6px 24px ${colors.navyDeep}`,
        }}
      >
        {title}
      </div>
    </AbsoluteFill>
    <div style={{position: 'absolute', left: 100, bottom: 70, display: 'flex', alignItems: 'center', gap: 20}}>
      <Coin size={84} />
      <div style={{fontFamily: fonts.display, fontWeight: 900, fontSize: 48, color: colors.parchment}}>{brand.channelName}</div>
    </div>
  </AbsoluteFill>
);
