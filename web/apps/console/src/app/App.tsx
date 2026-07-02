import { useReducer, useEffect, useCallback } from "react";
import {
  connectionReducer,
  initialState,
  type SourceRecord,
} from "./state.js";
import { connectToServer, callOperation } from "../connection/api.js";
import { ConnectionHeader } from "../components/ConnectionHeader.js";
import { SourceInventory } from "../components/SourceInventory.js";
import { ProtocolEvidence } from "../components/ProtocolEvidence.js";

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

export const App = () => {
  const [state, dispatch] = useReducer(connectionReducer, null, initialState);

  const loadSources = useCallback(
    async (target: string) => {
      const result = await callOperation(
        "workflow.sources.list",
        target,
        { limit: 50 },
      );
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
    },
    [],
  );

  useEffect(() => {
    if (state.phase === "connected" && state.connectedTarget) {
      void loadSources(state.connectedTarget);
    }
  }, [state.phase, state.connectedTarget, loadSources]);

  const onSubmit = (target: string) => {
    dispatch({ type: "submit", target });
    void connectToServer(target).then(
      (response) => {
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
        dispatch({
          type: "failure",
          code: "rpc_protocol_error",
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
      <SourceInventory
        sources={state.sources}
        loading={state.sourcesLoading}
        error={state.sourceError}
      />
      <ProtocolEvidence evidence={state.evidence} />
    </div>
  );
};
