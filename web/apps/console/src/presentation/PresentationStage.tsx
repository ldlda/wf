import { presentationBeats, type BeatId } from "./beats.js";
import { BeatRail } from "./BeatRail.js";
import { OperatorChat } from "./OperatorChat.js";
import { StageCaption } from "./StageCaption.js";
import type { PresentationState } from "./presentation-state.js";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";

type PresentationStageProps = {
  readonly state: PresentationState;
  readonly demo: DemoTimelineController;
  readonly jump: (beat: BeatId) => void;
};

export const PresentationStage = ({ state, demo, jump }: PresentationStageProps) => {
  const beat = presentationBeats.find((candidate) => candidate.id === state.beat) ?? presentationBeats[0]!;

  return (
    <div className="presentation-stage" data-beat={state.beat}>
      <OperatorChat state={state} />
      <section className="presentation-stage__main">
        <StageCaption eyebrow="lda.chat defense" title={beat.title}>
          <p>{beat.caption}</p>
        </StageCaption>
        <p className="presentation-stage__mode">
          {demo.state.mode === "replay" ? "Replay" : "Live"} · {demo.state.phase}
        </p>
      </section>
      <BeatRail activeBeat={state.beat} jump={jump} />
    </div>
  );
};
