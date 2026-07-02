import type { FormEvent } from "react";
import type { ConnectionState } from "../app/state.js";

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

type Props = {
  readonly state: ConnectionState;
  readonly onSubmit: (target: string) => void;
  readonly onDraftChange: (value: string) => void;
};

export const ConnectionHeader = ({ state, onSubmit, onDraftChange }: Props) => {
  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit(state.draftTarget);
  };

  return (
    <section aria-label="Connection">
      <form onSubmit={handleSubmit}>
        <label htmlFor="target-input">Workflow JSON-RPC URL</label>
        <input
          id="target-input"
          type="text"
          value={state.draftTarget}
          onChange={(e) => onDraftChange(e.target.value)}
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
