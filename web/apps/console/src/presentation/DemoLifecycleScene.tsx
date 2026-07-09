import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import { projectDemoLifecycleFacts } from "./demo-lifecycle-facts.js";
import { StageCaption } from "./StageCaption.js";
import type { SceneBeatDefinition, SceneDefinition } from "./storyboard.js";

type DemoLifecycleSceneProps = {
  readonly scene: SceneDefinition;
  readonly beat: SceneBeatDefinition;
  readonly demo: DemoTimelineController;
};

const stages = [
  { id: "draft", label: "Draft", description: "Prepared authoring context" },
  { id: "artifact", label: "Artifact", description: "Immutable versioned workflow" },
  { id: "deployment", label: "Deployment", description: "Configured source bindings" },
  { id: "ready-run", label: "Run-ready", description: "Persisted run can start" },
] as const;

export const DemoLifecycleScene = ({ scene, beat, demo }: DemoLifecycleSceneProps) => {
  const facts = projectDemoLifecycleFacts(demo);

  return (
    <>
      <StageCaption eyebrow="Product lifecycle" title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <section
        className="demo-lifecycle-scene"
        aria-label="prepared workflow lifecycle"
        data-active-lifecycle={beat.id}
      >
        <ol className="demo-lifecycle-scene__rail">
          {stages.map((stage) => (
            <li key={stage.id} data-active={stage.id === beat.id ? "true" : "false"}>
              <strong>{stage.label}</strong>
              <span>{stage.description}</span>
            </li>
          ))}
        </ol>

        <article className="demo-lifecycle-scene__proof">
          <h3>{stages.find((stage) => stage.id === beat.id)?.label ?? "Lifecycle"}</h3>
          {beat.id === "draft" && (
            <dl>
              <dt>Workflow</dt><dd>{facts.draft.label}</dd>
              <dt>Status</dt><dd>{facts.draft.status}</dd>
              <dt>Source</dt><dd>{facts.draft.source}</dd>
            </dl>
          )}
          {beat.id === "artifact" && (
            <dl>
              <dt>Artifact</dt><dd>{facts.artifact.id}</dd>
              <dt>Version</dt><dd>{facts.artifact.version ?? "unavailable"}</dd>
            </dl>
          )}
          {beat.id === "deployment" && (
            <dl>
              <dt>Deployment</dt><dd>{facts.deployment.id}</dd>
              <dt>Drift policy</dt><dd>{facts.deployment.driftPolicy}</dd>
              <dt>Bindings</dt>
              <dd>
                <ul>
                  {facts.deployment.bindings.map(([from, to]) => (
                    <li key={`${from}:${to}`}>{from} -&gt; {to}</li>
                  ))}
                </ul>
              </dd>
            </dl>
          )}
          {beat.id === "ready-run" && (
            <dl>
              <dt>Run</dt><dd>{facts.run.id ?? "not started"}</dd>
              <dt>Status</dt><dd>{facts.run.status}</dd>
              <dt>Deployment</dt><dd>{facts.deployment.id}</dd>
            </dl>
          )}
        </article>
      </section>
    </>
  );
};
