import { useCallback, useMemo, useReducer, useRef } from "react";
import { Outlet } from "react-router-dom";
import { connectToServer } from "../connection/api.js";
import {
  connectionReducer,
  initialState,
  type EvidenceRecord,
} from "../app/state.js";
import { createConsoleReadExecutor } from "./domain/read-executor.js";
import { createConsoleWriteExecutor } from "./domain/write-executor.js";
import { ConsoleShell } from "./ConsoleShell.js";
import type { ConsoleWorkspaceContextValue } from "./context.js";

export const ConsoleWorkspace = () => {
  const [state, dispatch] = useReducer(connectionReducer, null, initialState);
  const connectGeneration = useRef(0);
  const evidenceSequence = useRef(0);
  const connectedTarget = state.phase === "connected" ? state.connectedTarget : null;

  const recordEvidence = useCallback(
    (record: EvidenceRecord) => dispatch({ type: "evidence_recorded", record }),
    [],
  );

  const allocateEvidenceId = useCallback(
    (operation: string): string => `${operation}-${evidenceSequence.current++}`,
    [],
  );

  const readExecutor = useMemo(
    () => {
      if (!connectedTarget) return null;
      const executorGeneration = connectGeneration.current;
      return createConsoleReadExecutor({
        target: connectedTarget,
        recordEvidence,
        allocateEvidenceId,
        shouldRecordEvidence: () =>
          connectGeneration.current === executorGeneration,
      });
    },
    [allocateEvidenceId, connectedTarget, recordEvidence],
  );

  const writeExecutor = useMemo(
    () => {
      if (!connectedTarget) return null;
      const executorGeneration = connectGeneration.current;
      return createConsoleWriteExecutor({
        target: connectedTarget,
        recordEvidence,
        allocateEvidenceId,
        shouldRecordEvidence: () =>
          connectGeneration.current === executorGeneration,
      });
    },
    [allocateEvidenceId, connectedTarget, recordEvidence],
  );

  const onDraftChange = useCallback(
    (value: string) => dispatch({ type: "draft_changed", value }),
    [],
  );

  const onConnect = useCallback((target: string) => {
    const generation = ++connectGeneration.current;
    dispatch({ type: "submit", target });

    void connectToServer(target).then(
      (response) => {
        if (connectGeneration.current !== generation) return;
        if (response.ok) {
          dispatch({ type: "success", data: response });
          dispatch({
            type: "evidence_recorded",
            record: {
              id: allocateEvidenceId("workflow.health"),
              target: response.connection.target,
              operation: "workflow.health",
              label: "Health check",
              equivalentCli: response.equivalentCli,
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
      (error: unknown) => {
        if (connectGeneration.current !== generation) return;
        dispatch({
          type: "failure",
          code: errorCodeFromThrown(error),
          message: error instanceof Error ? error.message : "unknown error",
        });
      },
    );
  }, [allocateEvidenceId]);

  const workspaceContext = useMemo<ConsoleWorkspaceContextValue>(
    () => ({
      connection: state,
      connectedTarget,
      recordEvidence,
      readExecutor,
      writeExecutor,
    }),
    [connectedTarget, readExecutor, recordEvidence, state, writeExecutor],
  );

  return (
    <ConsoleShell
      connection={state}
      onConnect={onConnect}
      onDraftChange={onDraftChange}
    >
      <Outlet context={workspaceContext} />
    </ConsoleShell>
  );
};

const errorCodeFromThrown = (error: unknown): string => {
  if (!(error instanceof Error)) return "rpc_protocol_error";
  return error.message.toLowerCase().includes("malformed")
    ? "malformed_response"
    : "rpc_protocol_error";
};
