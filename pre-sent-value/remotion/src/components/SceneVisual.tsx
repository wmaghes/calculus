import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {colors, fonts} from '../../../brand/theme';
import {CoinStacks, CoinStacksParams} from '../graphics/CoinStacks';
import {MapRoute, MapParams} from '../graphics/MapRoute';
import {TextCard} from '../graphics/TextCard';
import type {Scene} from '../types';

// Registry of reusable animated graphics. Add new components here and
// reference them from episode.json via visual.graphic.
const GRAPHICS: Record<string, React.FC<{params: any; durationInFrames: number}>> = {
  map_route: ({params, durationInFrames}) => <MapRoute params={params as MapParams} durationInFrames={durationInFrames} />,
  coin_stacks: ({params}) => <CoinStacks params={params as CoinStacksParams} />,
};

const Missing: React.FC<{label: string}> = ({label}) => (
  <AbsoluteFill style={{background: colors.navySoft, justifyContent: 'center', alignItems: 'center'}}>
    <div style={{fontFamily: fonts.sans, color: colors.parchment, fontSize: 40, opacity: 0.7, padding: 80, textAlign: 'center'}}>
      [missing visual] {label}
    </div>
  </AbsoluteFill>
);

export const SceneVisual: React.FC<{scene: Scene; slug: string; durationInFrames: number}> = ({scene, slug, durationInFrames}) => {
  const v = scene.visual;
  switch (v.type) {
    case 'archival_image':
      if (!v.file) return <Missing label={v.prompt ?? scene.id} />;
      return (
        <AbsoluteFill style={{background: colors.navyDeep}}>
          <Img src={staticFile(`episodes/${slug}/${v.file}`)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
          {/* gentle navy grade so archival images sit in the brand palette */}
          <AbsoluteFill style={{background: `linear-gradient(180deg, rgba(8,17,31,0.15), rgba(8,17,31,0.55))`}} />
        </AbsoluteFill>
      );
    case 'text_card':
      return <TextCard text={v.text ?? ''} subtext={v.subtext} />;
    case 'map':
    case 'animated_graphic': {
      const G = GRAPHICS[v.graphic ?? (v.type === 'map' ? 'map_route' : '')];
      if (!G) return <Missing label={`${v.graphic ?? '?'} — ${v.prompt ?? ''}`} />;
      return <G params={v.params ?? {}} durationInFrames={durationInFrames} />;
    }
  }
};
