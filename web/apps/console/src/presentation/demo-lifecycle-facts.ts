import type { DemoTimelineController } from "../demo/useDemoTimeline.js";

export type DemoLifecycleFacts = {
  readonly draft: {
    readonly label: string;
    readonly source: string;
    readonly status: string;
  };
  readonly artifact: {
    readonly id: string;
    readonly version: number | null;
  };
  readonly deployment: {
    readonly id: string;
    readonly driftPolicy: string;
    readonly bindings: ReadonlyArray<readonly [string, string]>;
  };
  readonly run: {
    readonly id: string | null;
    readonly status: string;
  };
};

const deploymentInspect = (demo: DemoTimelineController) =>
  demo.state.events.find((event) => event.stage === "deployment_check");

const runStart = (demo: DemoTimelineController) =>
  demo.state.events.find((event) => event.stage === "run_start");

const readBindings = (value: unknown): ReadonlyArray<readonly [string, string]> => {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) => {
    if (!Array.isArray(entry) || entry.length !== 2) return [];
    const [from, to] = entry;
    return typeof from === "string" && typeof to === "string" ? [[from, to] as const] : [];
  });
};

/**
 * Presentation-only lifecycle facts. Draft context is prepared example context;
 * artifact/deployment/run facts come from replay evidence when available.
 */
export const projectDemoLifecycleFacts = (demo: DemoTimelineController): DemoLifecycleFacts => {
  const deployment = deploymentInspect(demo);
  const deploymentInterpreted = deployment?.interpreted as
    | {
        id?: string;
        artifactId?: string;
        artifactVersion?: number;
        driftPolicy?: string;
        bindings?: unknown;
      }
    | undefined;
  const run = runStart(demo);
  const runInterpreted = run?.interpreted as
    | { runId?: string; status?: string }
    | undefined;

  return {
    draft: {
      label: "lda report workflow",
      source: "examples/lda_report_workflow",
      status: "prepared context",
    },
    artifact: {
      id: deploymentInterpreted?.artifactId ?? "unavailable",
      version: typeof deploymentInterpreted?.artifactVersion === "number"
        ? deploymentInterpreted.artifactVersion
        : null,
    },
    deployment: {
      id: deploymentInterpreted?.id ?? "unavailable",
      driftPolicy: deploymentInterpreted?.driftPolicy ?? "unavailable",
      bindings: readBindings(deploymentInterpreted?.bindings),
    },
    run: {
      id: runInterpreted?.runId ?? run?.resultingIds.runId ?? null,
      status: runInterpreted?.status ?? "not started",
    },
  };
};
