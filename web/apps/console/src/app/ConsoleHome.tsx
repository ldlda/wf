import { useReducer, useEffect, useCallback, useRef } from "react";
import {
  connectionReducer,
  initialState,
  type EvidenceRecord,
  type SourceRecord,
} from "./state.js";
import { connectToServer, callOperation } from "../connection/api.js";
import { ConnectionHeader } from "../components/ConnectionHeader.js";
import { SourceInventory } from "../components/SourceInventory.js";
import { LifecycleExplorer } from "../lifecycle/LifecycleExplorer.js";
import { useLifecycleExplorer } from "../lifecycle/useLifecycleExplorer.js";
import { LdaReportDemoPanel } from "../demo/LdaReportDemoPanel.js";
import { useDemoTimeline } from "../demo/useDemoTimeline.js";

const parseSources = (
  data: unknown,
): SourceRecord[] => {
  if (!data || typeof data !== "object") return [];
  const obj = data as Record<string, unknown>;
  if (!Array.isArray(obj.sources)) return [];

  return obj.sources.map((entry: unknown, i: number) => {
    const s = entry as Record<string, unknown>;
    const id = typeof s.id === "string" ? s.id : `source-${i}`;
    const kind = typeof s.kind === "string" ? s.kind : "unknown";
    const enabled = s.enabled !== false;
    const description =
      typeof s.description === "string" ? s.description : null;
    const counts = (s.counts ?? {}) as Record<string, number>;
    return {
      id,
      kind,
      enabled,
      description,
      toolCount: typeof counts.tools === "number" ? counts.tools : 0,
      nodeSpecCount: typeof counts.nodeSpecs === "number" ? counts.nodeSpecs : 0,
      reducerCount: typeof counts.reducers === "number" ? counts.reducers : 0,
      promptCount: typeof counts.prompts === "number" ? counts.prompts : 0,
      resourceCount:
        typeof counts.resources === "number" ? counts.resources : 0,
    };
  });
};

export const ConsoleHome = () => {
  const [state, dispatch] = useReducer(connectionReducer, null, initialState);
  const connectGeneration = useRef(0);
  const sourcesGeneration = useRef(0);

  const connectedTarget = state.phase === "connected" ? state.connectedTarget : null;

  const recordEvidence = useCallback(
    (record: EvidenceRecord) => dispatch({ type: "evidence_recorded", record }),
    [],
  );

  const lifecycleController = useLifecycleExplorer(connectedTarget, recordEvidence);
  const demoController = useDemoTimeline(connectedTarget, recordEvidence);

  const loadSources = useCallback(
    async (target: string) => {
      const generation = ++sourcesGeneration.current;
      dispatch({ type: "sources_loading" });
      try {
        const result = await callOperation(
          "workflow.sources.list",
          target,
          { limit: 50 },
        );
        if (sourcesGeneration.current !== generation) return;
        if (result.ok) {
          const sources = parseSources(result.interpreted);
          dispatch({
            type: "sources_loaded",
            sources,
            evidence: {
              id: `sources-${Date.now()}`,
              operation: "workflow.sources.list",
              label: "Source inventory",
              equivalentCli: result.equivalentCli,
              request: result.exchange.request,
              response: result.exchange.response,
              durationMs: result.durationMs,
            },
          });
        } else {
          dispatch({
            type: "sources_error",
            message: result.error.message,
            evidence: {
              id: `sources-${Date.now()}`,
              operation: "workflow.sources.list",
              label: "Source inventory",
              equivalentCli: "uv run wf source list --limit 50",
              request: result.exchange.request,
              response: result.exchange.response,
              durationMs: 0,
            },
          });
        }
      } catch (e: unknown) {
        if (sourcesGeneration.current !== generation) return;
        dispatch({
          type: "sources_error",
          message: e instanceof Error ? e.message : "unknown error",
        });
      }
    },
    [],
  );

  useEffect(() => {
    if (state.phase === "connected" && state.connectedTarget) {
      void loadSources(state.connectedTarget);
    }
  }, [state.phase, state.connectedTarget, loadSources]);

  const onSubmit = (target: string) => {
    const generation = ++connectGeneration.current;
    sourcesGeneration.current++;
    dispatch({ type: "submit", target });
    void connectToServer(target).then(
      (response) => {
        if (connectGeneration.current !== generation) return;
        if (response.ok) {
          dispatch({ type: "success", data: response });
          dispatch({
            type: "evidence_recorded",
            record: {
              id: `health-${Date.now()}`,
              operation: "workflow.health",
              label: "Health check",
              equivalentCli: "uv run wf status",
              request: response.exchange.request,
              response: response.exchange.response,
              durationMs: response.connection.durationMs,
            },
          });
        } else {
          dispatch({
            type: "failure",
            code: response.error.code,
            message: response.error.message,
          });
        }
      },
      (e: unknown) => {
        if (connectGeneration.current !== generation) return;
        dispatch({
          type: "failure",
          code: errorCodeFromThrown(e),
          message: e instanceof Error ? e.message : "unknown error",
        });
      },
    );
  };

  return (
    <div className="app-layout">
      <ConnectionHeader
        state={state}
        onSubmit={onSubmit}
        onDraftChange={(value) => dispatch({ type: "draft_changed", value })}
      />
      <LdaReportDemoPanel controller={demoController} />
      <SourceInventory
        sources={state.sources}
        loading={state.sourcesLoading}
        error={state.sourceError}
      />
      <section aria-label="Lifecycle Explorer" data-testid="lifecycle-explorer" data-panel="lifecycle-explorer">
        <LifecycleExplorer controller={lifecycleController} />
      </section>
    </div>
  );
};

const errorCodeFromThrown = (error: unknown): string => {
  if (!(error instanceof Error)) return "rpc_protocol_error";
  return error.message.toLowerCase().includes("malformed")
    ? "malformed_response"
    : "rpc_protocol_error";
};
