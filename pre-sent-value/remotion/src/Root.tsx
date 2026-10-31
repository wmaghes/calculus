import React from 'react';
import {Composition, Still} from 'remotion';
import {Intro, INTRO_FRAMES} from '../../brand/intro';
import {Outro, OUTRO_FRAMES} from '../../brand/outro';
import {video} from '../../brand/theme';
import {Episode, episodeFrames} from './Episode';
import {Thumbnail, ThumbnailProps} from './Thumbnail';
import type {EpisodeProps} from './types';

// Content always comes in through input props written by `pv render`
// (episode.json + words.json). These defaults only make the Studio open.
const emptyProps: EpisodeProps = {
  episode: {
    slug: 'preview',
    number: 0,
    title: 'Preview',
    hook: '',
    lesson: '',
    runtime_target_seconds: 10,
    acts: [],
    clips: [],
    scenes: [],
  },
  words: [],
  narrationSrc: null,
  musicSrc: null,
  clipId: null,
};

const calc = ({props}: {props: EpisodeProps}) => ({durationInFrames: Math.max(1, episodeFrames(props, video.fps))});

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="Episode16x9" component={Episode} fps={video.fps} {...video.landscape} durationInFrames={300} defaultProps={emptyProps} calculateMetadata={calc} />
    <Composition id="Episode9x16" component={Episode} fps={video.fps} {...video.portrait} durationInFrames={300} defaultProps={emptyProps} calculateMetadata={calc} />
    <Composition id="Intro16x9" component={Intro} fps={video.fps} {...video.landscape} durationInFrames={INTRO_FRAMES} />
    <Composition id="Intro9x16" component={Intro} fps={video.fps} {...video.portrait} durationInFrames={INTRO_FRAMES} />
    <Composition id="Outro16x9" component={Outro} fps={video.fps} {...video.landscape} durationInFrames={OUTRO_FRAMES} />
    <Composition id="Outro9x16" component={Outro} fps={video.fps} {...video.portrait} durationInFrames={OUTRO_FRAMES} />
    <Still id="Thumbnail" component={Thumbnail} {...video.landscape} defaultProps={{title: 'The Story of Wenamun', kicker: 'Episode 1', episodeSlug: null, image: null} as ThumbnailProps} />
  </>
);
