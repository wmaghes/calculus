import type {Word} from '../../brand/Captions';

export type {Word};

export type VisualType = 'archival_image' | 'map' | 'animated_graphic' | 'text_card';
export type Motion = 'kenburns' | 'pan' | 'zoom' | 'reveal';

export type Visual = {
  type: VisualType;
  // archival_image: path relative to the episode folder, e.g. "assets/byblos.jpg"
  file?: string;
  // free-text description / generation brief (used for sourcing + as alt text)
  prompt?: string;
  // animated_graphic / map: which reusable component + its parameters
  graphic?: string;
  params?: Record<string, unknown>;
  // text_card
  text?: string;
  subtext?: string;
};

export type Scene = {
  id: string;
  act: number;
  narration: string;
  start: number | null; // seconds from narration start (filled by `pv captions`)
  end: number | null;
  visual: Visual;
  motion: Motion;
  sfx?: string | null; // file name in brand/sfx, e.g. "whoosh.mp3"
  source_ref?: string | null;
  clip_candidate?: string | null;
};

export type Clip = {id: string; start: number; end: number; hook: string; cta: string};

export type Episode = {
  slug: string;
  number: number;
  title: string;
  hook: string;
  hook_alternatives?: string[];
  lesson: string;
  runtime_target_seconds: number;
  acts: {act: number; name: string; start: number | null; end: number | null}[];
  clips: Clip[];
  scenes: Scene[];
  music?: string; // file name in brand/music
  narration_file?: string; // relative to episode folder
  narration_duration?: number | null;
};

export type EpisodeProps = {
  episode: Episode;
  words: Word[];
  // set by pv when narration audio exists
  narrationSrc?: string | null;
  musicSrc?: string | null;
  // when set, render only this short-form clip
  clipId?: string | null;
};
