import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import type { DemoEvent } from "../demo/timeline/models.js";

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

const deploymentInspect = (demo: DemoTimelineController): DemoEvent | undefined =>
  demo.state.events.find((event) => event.stage === "deployment_check");

const runStart = (demo: DemoTimelineController): DemoEvent | undefined =>
  demo.state.events.find((event) => event.stage === "run_start");

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const stringField = (record: Record<string, unknown> | undefined, field: string): string | undefined => {
  const value = record?.[field];
  return typeof value === "string" ? value : undefined;
};

const numberField = (record: Record<string, unknown> | undefined, field: string): number | undefined => {
  const value = record?.[field];
  return typeof value === "number" ? value : undefined;
};

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
  const deploymentInterpreted = isRecord(deployment?.interpreted) ? deployment.interpreted : undefined;
  const run = runStart(demo);
  const runInterpreted = isRecord(run?.interpreted) ? run.interpreted : undefined;

  return {
    draft: {
      label: "lda report workflow",
      source: "examples/lda_report_workflow",
      status: "prepared context",
    },
    artifact: {
      id: stringField(deploymentInterpreted, "artifactId") ?? "unavailable",
      version: numberField(deploymentInterpreted, "artifactVersion") ?? null,
    },
    deployment: {
      id: stringField(deploymentInterpreted, "id") ?? "unavailable",
      driftPolicy: stringField(deploymentInterpreted, "driftPolicy") ?? "unavailable",
      bindings: readBindings(deploymentInterpreted?.["bindings"]),
    },
    run: {
      id: stringField(runInterpreted, "runId") ?? run?.resultingIds.runId ?? null,
      status: stringField(runInterpreted, "status") ?? "not started",
    },
  };
};
