import React from "react";
import { Composition, Series } from "remotion";
import { VIDEO } from "./theme";

import { Intro } from "./scenes/Intro";
import { Scene1Search } from "./scenes/Scene1Search";
import { Scene2Dashboard } from "./scenes/Scene2Dashboard";
import { Scene3Portfolio } from "./scenes/Scene3Portfolio";
import { Scene4Insurance } from "./scenes/Scene4Insurance";
import { Scene5IDD } from "./scenes/Scene5IDD";
import { Scene6AI } from "./scenes/Scene6AI";
import { Outro } from "./scenes/Outro";

const SCENE_FRAMES = VIDEO.fps * VIDEO.sceneDuration; // 150 frames = 5s per scene

/** Full demo video: Intro + 6 scenes + Outro */
const DemoVideo: React.FC = () => (
  <Series>
    <Series.Sequence durationInFrames={SCENE_FRAMES}>
      <Intro />
    </Series.Sequence>
    <Series.Sequence durationInFrames={SCENE_FRAMES}>
      <Scene1Search />
    </Series.Sequence>
    <Series.Sequence durationInFrames={SCENE_FRAMES}>
      <Scene2Dashboard />
    </Series.Sequence>
    <Series.Sequence durationInFrames={SCENE_FRAMES}>
      <Scene3Portfolio />
    </Series.Sequence>
    <Series.Sequence durationInFrames={SCENE_FRAMES}>
      <Scene4Insurance />
    </Series.Sequence>
    <Series.Sequence durationInFrames={SCENE_FRAMES}>
      <Scene5IDD />
    </Series.Sequence>
    <Series.Sequence durationInFrames={SCENE_FRAMES}>
      <Scene6AI />
    </Series.Sequence>
    <Series.Sequence durationInFrames={SCENE_FRAMES}>
      <Outro />
    </Series.Sequence>
  </Series>
);

export const RemotionRoot: React.FC = () => {
  const totalFrames = SCENE_FRAMES * 8; // 8 segments

  return (
    <>
      {/* Full 40-second demo video */}
      <Composition
        id="DemoVideo"
        component={DemoVideo}
        durationInFrames={totalFrames}
        fps={VIDEO.fps}
        width={VIDEO.width}
        height={VIDEO.height}
      />

      {/* Individual scenes for preview / iteration */}
      <Composition id="Intro" component={Intro} durationInFrames={SCENE_FRAMES} fps={VIDEO.fps} width={VIDEO.width} height={VIDEO.height} />
      <Composition id="Scene1-Search" component={Scene1Search} durationInFrames={SCENE_FRAMES} fps={VIDEO.fps} width={VIDEO.width} height={VIDEO.height} />
      <Composition id="Scene2-Dashboard" component={Scene2Dashboard} durationInFrames={SCENE_FRAMES} fps={VIDEO.fps} width={VIDEO.width} height={VIDEO.height} />
      <Composition id="Scene3-Portfolio" component={Scene3Portfolio} durationInFrames={SCENE_FRAMES} fps={VIDEO.fps} width={VIDEO.width} height={VIDEO.height} />
      <Composition id="Scene4-Insurance" component={Scene4Insurance} durationInFrames={SCENE_FRAMES} fps={VIDEO.fps} width={VIDEO.width} height={VIDEO.height} />
      <Composition id="Scene5-IDD" component={Scene5IDD} durationInFrames={SCENE_FRAMES} fps={VIDEO.fps} width={VIDEO.width} height={VIDEO.height} />
      <Composition id="Scene6-AI" component={Scene6AI} durationInFrames={SCENE_FRAMES} fps={VIDEO.fps} width={VIDEO.width} height={VIDEO.height} />
      <Composition id="Outro" component={Outro} durationInFrames={SCENE_FRAMES} fps={VIDEO.fps} width={VIDEO.width} height={VIDEO.height} />
    </>
  );
};
