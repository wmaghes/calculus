import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {colors, fonts} from '../../../brand/theme';

// Stylised map of the Eastern Mediterranean. Coastlines are simplified
// hand-entered approximations (lon, lat in degrees) — good for storytelling,
// not for navigation. Extend PLACES / LAND when an episode needs more.

type LonLat = [number, number];

type Side = 'left' | 'right' | 'below' | 'above';
export const PLACES: Record<string, {pos: LonLat; label: string; side: Side}> = {
  thebes: {pos: [32.65, 25.7], label: 'Thebes', side: 'right'},
  tanis: {pos: [31.88, 30.98], label: 'Tanis', side: 'left'},
  memphis: {pos: [31.25, 29.85], label: 'Memphis', side: 'left'},
  dor: {pos: [34.92, 32.62], label: 'Dor', side: 'right'},
  tyre: {pos: [35.2, 33.27], label: 'Tyre', side: 'right'},
  sidon: {pos: [35.37, 33.56], label: 'Sidon', side: 'right'},
  byblos: {pos: [35.65, 34.12], label: 'Byblos', side: 'right'},
  cyprus: {pos: [33.2, 35.05], label: 'Cyprus', side: 'below'},
};

const COAST_SOUTH: LonLat[] = [
  [10, 32.6], [22, 32.6], [25, 31.6], [27.3, 31.35], [29.9, 31.2], [30.4, 31.45], [31.0, 31.6],
  [31.6, 31.5], [32.3, 31.26], [33.2, 31.1], [34.45, 31.5], [34.75, 32.05], [34.92, 32.62],
  [34.99, 32.82], [35.2, 33.27], [35.37, 33.56], [35.5, 33.9], [35.65, 34.12], [35.84, 34.44],
  [35.95, 34.9], [35.78, 35.52], [35.95, 35.95], [36.17, 36.6], [35.6, 36.7], [34.6, 36.8],
  [33.6, 36.2], [32.6, 36.1], [32.0, 36.55], [30.7, 36.88], [30.5, 36.3], [29.1, 36.6],
  [28.0, 36.8], [27.3, 37.4], [26.5, 38.5], [22, 38.5], [10, 38.5],
];
const CYPRUS: LonLat[] = [
  [32.27, 35.1], [32.9, 35.4], [33.9, 35.35], [34.6, 35.7], [34.0, 35.0], [33.6, 34.95],
  [33.0, 34.6], [32.4, 34.75],
];
const NILE: LonLat[] = [
  [32.65, 25.7], [32.72, 26.16], [32.2, 26.4], [31.18, 27.18], [30.75, 28.1], [31.1, 29.3],
  [31.23, 30.04], [31.0, 30.6], [30.6, 31.1], [30.4, 31.45],
];
const NILE_EAST: LonLat[] = [[31.23, 30.04], [31.6, 30.7], [32.0, 31.15], [32.3, 31.26]];

export type MapParams = {
  route?: string[]; // place keys in travel order
  markers?: string[]; // extra places to label
  bbox?: [number, number, number, number]; // lonMin, latMin, lonMax, latMax
  title?: string;
  danger?: boolean; // red dashed route (e.g. pirates)
  drawStart?: number; // 0..1 of scene where drawing starts
  drawEnd?: number;
};

export const MapRoute: React.FC<{params: MapParams; durationInFrames: number}> = ({params, durationInFrames}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const portrait = height > width;
  const [lonMin, latMin, lonMax, latMax] =
    params.bbox ?? (portrait ? [30.0, 24.8, 37.5, 36.4] : [27.0, 24.6, 40.0, 36.4]);
  // equirectangular with cos(lat) correction, fit to frame
  const k = Math.cos((((latMin + latMax) / 2) * Math.PI) / 180);
  const sx = width / ((lonMax - lonMin) * k);
  const sy = height / (latMax - latMin);
  const s = Math.min(sx, sy); // contain: whole bbox visible, land polygons extend past it
  const ox = (width - (lonMax - lonMin) * k * s) / 2;
  const oy = (height - (latMax - latMin) * s) / 2;
  const P = ([lon, lat]: LonLat): [number, number] => [ox + (lon - lonMin) * k * s, oy + (latMax - lat) * s];
  const path = (pts: LonLat[], close = false) =>
    pts.map((p, i) => `${i ? 'L' : 'M'}${P(p)[0].toFixed(1)},${P(p)[1].toFixed(1)}`).join(' ') + (close ? ' Z' : '');

  // land = everything "below" the south coast line + the northern block (Anatolia)
  const landSouth = path([...COAST_SOUTH.slice(0, 20), [50, 35.52], [50, 10], [10, 10], [10, 32.6]], true);
  const landNorth = path([...COAST_SOUTH.slice(19), [10, 38.5], [10, 50], [50, 50], [50, 35.52]], true);

  const route = (params.route ?? []).map((k2) => PLACES[k2]).filter(Boolean);
  const routeD = route.length > 1 ? path(route.map((r) => r.pos)) : '';
  const p0 = Math.round((params.drawStart ?? 0.1) * durationInFrames);
  const p1 = Math.round((params.drawEnd ?? 0.8) * durationInFrames);
  const progress = interpolate(frame, [p0, Math.max(p0 + 1, p1)], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.quad),
  });
  const routeColor = params.danger ? colors.danger : colors.gold;
  const labelSize = portrait ? 46 : 40;
  const labelled = Array.from(new Set([...(params.route ?? []), ...(params.markers ?? [])]));

  return (
    <AbsoluteFill style={{background: colors.navySoft}}>
      <svg width={width} height={height}>
        <defs>
          <pattern id="waves" width="60" height="30" patternUnits="userSpaceOnUse">
            <path d="M0 15 Q15 8 30 15 T60 15" fill="none" stroke={colors.navy} strokeWidth="2" opacity="0.5" />
          </pattern>
          <filter id="paper">
            <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" result="n" />
            <feColorMatrix type="saturate" values="0" />
            <feBlend in="SourceGraphic" mode="multiply" />
          </filter>
        </defs>
        <rect width={width} height={height} fill="url(#waves)" />
        <g fill={colors.parchment} stroke={colors.parchmentDark} strokeWidth={3} strokeLinejoin="round">
          <path d={landSouth} />
          <path d={landNorth} />
          <path d={path(CYPRUS, true)} />
        </g>
        <g fill="none" stroke="#6E8FB5" strokeWidth={portrait ? 6 : 5} strokeLinecap="round" strokeLinejoin="round">
          <path d={path(NILE)} />
          <path d={path(NILE_EAST)} />
        </g>
        {routeD && (
          <path
            d={routeD}
            fill="none"
            stroke={routeColor}
            strokeWidth={portrait ? 10 : 8}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray={params.danger ? '22 16' : undefined}
            pathLength={1}
            style={{strokeDasharray: params.danger ? undefined : 1, strokeDashoffset: params.danger ? 0 : 1 - progress}}
            opacity={params.danger ? progress : 1}
          />
        )}
        {labelled.map((key) => {
          const pl = PLACES[key];
          if (!pl) return null;
          const [x, y] = P(pl.pos);
          const idx = route.indexOf(pl);
          const appearAt = idx < 0 ? 0 : route.length < 2 ? 0 : idx / (route.length - 1);
          const o = interpolate(progress, [appearAt - 0.05, appearAt + 0.02], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          });
          const op = idx < 0 ? 1 : idx === 0 ? 1 : o;
          return (
            <g key={key} opacity={op}>
              <circle cx={x} cy={y} r={labelSize * 0.32} fill={colors.gold} stroke={colors.navy} strokeWidth={4} />
              <text
                x={pl.side === 'left' ? x - labelSize * 0.6 : pl.side === 'right' ? x + labelSize * 0.6 : x}
                y={pl.side === 'below' ? y + labelSize * 1.3 : pl.side === 'above' ? y - labelSize * 0.7 : y + labelSize * 0.35}
                textAnchor={pl.side === 'left' ? 'end' : pl.side === 'right' ? 'start' : 'middle'}
                fontFamily={fonts.display}
                fontWeight={700}
                fontSize={labelSize}
                fill={colors.ink}
                stroke={colors.parchment}
                strokeWidth={8}
                paintOrder="stroke"
              >
                {pl.label}
              </text>
            </g>
          );
        })}
      </svg>
      {params.title && (
        <div
          style={{
            position: 'absolute',
            top: height * (portrait ? 0.2 : 0.07),
            left: width * 0.06,
            padding: '14px 26px',
            borderRadius: 12,
            background: 'rgba(8,17,31,0.8)',
            fontFamily: fonts.sans,
            fontWeight: 800,
            letterSpacing: '0.3em',
            textTransform: 'uppercase',
            fontSize: portrait ? 40 : 34,
            color: colors.parchment,
            textShadow: `0 2px 8px ${colors.navyDeep}`,
          }}
        >
          {params.title}
        </div>
      )}
    </AbsoluteFill>
  );
};
