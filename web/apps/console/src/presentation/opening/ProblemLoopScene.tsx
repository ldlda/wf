import type { AgentMessage } from "../../demo/agent/events.js";
import { AssistantOperatorThread } from "../chat/AssistantOperatorThread.js";
import { StageCaption } from "../StageCaption.js";
import type { SceneBeatDefinition, SceneDefinition } from "../storyboard.js";
import { ConceptNode, ConceptRail } from "./ConceptPrimitives.js";

const oneOffToolLoopMessages: ReadonlyArray<AgentMessage> = [
  {
    id: "scene-2-user",
    role: "user",
    parts: [{ type: "text", text: "Can you finish this workspace task?" }],
  },
  {
    id: "scene-2-assistant",
    role: "assistant",
    parts: [
      { type: "text", text: "I can solve the immediate request." },
      {
        type: "tool-call",
        call: {
          id: "scene-2-tool-1",
          name: "fetchData",
          input: { source: "api", endpoint: "/tasks" },
        },
      },
      {
        type: "tool-call",
        call: {
          id: "scene-2-tool-2",
          name: "transformPayload",
          input: { format: "json", validate: true },
        },
      },
      {
        type: "tool-call",
        call: {
          id: "scene-2-tool-3",
          name: "writeOutput",
          input: { destination: "file", path: "/tmp/result.json" },
        },
      },
      { type: "text", text: "Done. But none of this is recorded in a durable workflow." },
    ],
  },
];

const automationProof = ["schemas", "bindings", "records"] as const;

type ProblemLoopSceneProps = {
  readonly scene: SceneDefinition;
  readonly beat: SceneBeatDefinition;
};

export const ProblemLoopScene = ({ scene, beat }: ProblemLoopSceneProps) => {
  const automationBeat = beat.id === "missing-contracts";
  return (
    <>
      <StageCaption eyebrow="Problem shape" title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <section
        className="problem-loop-scene"
        aria-label="chat tool loop versus reusable automation"
        data-problem-focus={automationBeat ? "workflow-blueprint" : "tool-loop"}
        data-support-state={automationBeat ? "receded" : "quiet"}
      >
        <article
          className="problem-chat-card"
          data-problem-active={automationBeat ? "false" : "true"}
          data-problem-role="tool-loop"
          aria-label="one-off chat and tool loop"
        >
          <header className="problem-artifact-header">
            <span>One-off</span>
            <h2>Chat + tool loop</h2>
            <p>Good at getting through one request.</p>
          </header>
          <div className="problem-chat-card__transcript" aria-label="one-off assistant transcript" role="group">
            <AssistantOperatorThread mode="dock" messages={oneOffToolLoopMessages} ariaLabel="one-off assistant transcript" />
          </div>
          <p className="problem-artifact-note">The useful work lives in the conversation history.</p>
        </article>

        <div className="problem-loop-scene__bridge" aria-hidden="true">one request → durable definition</div>

        <article
          className="problem-blueprint"
          role="group"
          aria-label="durable workflow blueprint"
          data-blueprint-active={automationBeat ? "true" : "false"}
          data-problem-role="workflow-blueprint"
        >
          <header className="problem-artifact-header">
            <span>Reusable</span>
            <h2>Workflow blueprint</h2>
            <p>Good at preserving how the work should run again.</p>
          </header>
          <ConceptRail label="Reusable automation">
            <ConceptNode title="design" icon="design" emphasis={automationBeat ? "primary" : "normal"} />
            <ConceptNode title="save" icon="save" emphasis={automationBeat ? "primary" : "normal"} />
            <ConceptNode title="connect" icon="connect" emphasis={automationBeat ? "primary" : "normal"} />
            <ConceptNode title="run" icon="run" emphasis={automationBeat ? "primary" : "normal"} />
            <ConceptNode title="inspect" icon="inspect" emphasis={automationBeat ? "primary" : "normal"} />
          </ConceptRail>
          <ul className="problem-blueprint__proof" aria-label="reusable automation proof points">
            {automationProof.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      </section>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};
