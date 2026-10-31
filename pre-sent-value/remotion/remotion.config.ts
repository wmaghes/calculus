import path from 'path';
import {Config} from '@remotion/cli/config';

Config.setVideoImageFormat('jpeg');
Config.setOverwriteOutput(true);
Config.setConcurrency(null);

// Use a pre-installed Chrome if provided (pv sets this automatically when it
// finds one); otherwise Remotion downloads its own headless shell.
if (process.env.REMOTION_BROWSER) {
  Config.setBrowserExecutable(process.env.REMOTION_BROWSER);
}

// brand/ lives outside remotion/, so let files there resolve packages
// (react, remotion, @fontsource) from remotion/node_modules.
Config.overrideWebpackConfig((config) => ({
  ...config,
  resolve: {
    ...config.resolve,
    modules: [path.join(process.cwd(), 'node_modules'), 'node_modules'],
  },
}));
