import { useReducer, type FormEvent } from "react";
import {
  connectionReducer,
  initialState,
  type ConnectionAction,
} from "../app/state.js";
import { connectToServer } from "../connection/api.js";

const handleSubmit = async (
  dispatch: React.Dispatch<ConnectionAction>,
  target: string,
) => {
  dispatch({ type: "submit", target });
  try {
    const response = await connectToServer(target);
    if (response.ok) {
      dispatch({ type: "success", data: response });
    } else {
      dispatch({
        type: "failure",
        code: response.error.code,
        message: response.error.message,
      });
    }
  } catch (e: unknown) {
    dispatch({
      type: "failure",
      code: "rpc_protocol_error",
      message: e instanceof Error ? e.message : "unknown error",
    });
  }
};

const phaseLabel = (phase: string): string => {
  switch (phase) {
    case "not_configured":
      return "Not connected";
    case "connecting":
      return "Connecting\u2026";
    case "connected":
      return "Connected";
    case "invalid_target":
      return "Invalid target";
    case "unreachable":
      return "Server unreachable";
    case "rpc_error":
      return "RPC error";
    case "malformed_response":
      return "Malformed response";
    default:
      return phase;
  }
};

export const ConnectionHeader = () => {
  const [state, dispatch] = useReducer(connectionReducer, null, initialState);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void handleSubmit(dispatch, state.draftTarget);
  };

  return (
    <section aria-label="Connection">
      <form onSubmit={onSubmit}>
        <label htmlFor="target-input">Workflow JSON-RPC URL</label>
        <input
          id="target-input"
          type="text"
          value={state.draftTarget}
          onChange={(e) =>
            dispatch({ type: "draft_changed", value: e.target.value })
          }
          disabled={state.phase === "connecting"}
        />
        <button type="submit" disabled={state.phase === "connecting"}>
          {state.connectedTarget ? "Reconnect" : "Connect"}
        </button>
      </form>

      <div aria-live="polite" role="status">
        <span data-testid="phase-label">{phaseLabel(state.phase)}</span>
        {state.phase === "connected" && (
          <>
            <span data-testid="server-status">
              {" "}
              &middot; {state.serverStatus}
            </span>
            <span data-testid="store-root">
              {" "}
              &middot; {state.storeRoot}
            </span>
            <span data-testid="duration-ms">
              {" "}
              &middot; {state.durationMs}ms
            </span>
          </>
        )}
        {state.message && (
          <span data-testid="error-message">
            {" "}
            &middot; {state.message}
          </span>
        )}
      </div>
    </section>
  );
};
