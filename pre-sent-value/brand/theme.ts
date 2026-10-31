// The Pre$ent Value — brand theme.
// To launch a second channel: copy brand/ to a new folder, edit this file
// (colors, fonts, names, tagline), and point pv at it with PV_BRAND_DIR.

import '@fontsource/playfair-display/700.css';
import '@fontsource/playfair-display/900.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/700.css';
import '@fontsource/inter/800.css';

export const brand = {
  channelName: 'The Pre$ent Value',
  wordmarkBefore: 'Pre',
  wordmarkCoin: '$',
  wordmarkAfter: 'ent Value',
  wordmarkPrefix: 'The',
  tagline: "Gaining the world's interest in business",
  outroLine1: 'Value compounds.',
  outroLine2: 'See you next time.',
  followPrompt: 'Follow for the next story',
} as const;

export const colors = {
  navy: '#0E1B33', // deep navy — primary background
  navyDeep: '#08111F', // vignette / shadows
  navySoft: '#1A2B4C', // panels, map water
  gold: '#C9A227', // warm gold — accents, highlight word
  goldLight: '#E8C766',
  goldDark: '#8E6F12',
  parchment: '#F3EAD3', // parchment off-white — body text, cards
  parchmentDark: '#D9CBA3',
  ink: '#2A2118', // text on parchment
  danger: '#A23B2A', // sparing use: pirates, losses
} as const;

export const fonts = {
  display: "'Playfair Display', Georgia, 'DejaVu Serif', serif",
  sans: "'Inter', 'Helvetica Neue', Arial, sans-serif",
} as const;

export const video = {
  fps: 30,
  landscape: {width: 1920, height: 1080},
  portrait: {width: 1080, height: 1920},
  introSeconds: 2,
  outroSeconds: 3,
} as const;

// Title-safe margins as a fraction of frame size. Portrait leaves extra room at
// the bottom and right for Shorts/Reels/TikTok UI overlays.
export const safeZone = {
  landscape: {top: 0.06, bottom: 0.1, left: 0.06, right: 0.06},
  portrait: {top: 0.12, bottom: 0.26, left: 0.07, right: 0.16},
} as const;

export const audio = {
  musicDb: -22, // music bed level under narration
  musicDbNoVoice: -16, // music level in intro/outro/gaps (still soft)
  duckAttackSec: 0.25,
  targetLufs: -14,
} as const;

export const dbToGain = (db: number) => Math.pow(10, db / 20);

export type Orientation = 'landscape' | 'portrait';
