import { useOutletContext } from "react-router-dom";
import type { ConnectionState, EvidenceRecord } from "../app/state.js";
import type { ConsoleReadExecutor } from "./domain/read-executor.js";

export type ConsoleWorkspaceContextValue = {
  readonly connection: ConnectionState;
  readonly connectedTarget: string | null;
  readonly recordEvidence: (record: EvidenceRecord) => void;
  readonly readExecutor: ConsoleReadExecutor | null;
};

export const useConsoleWorkspace = (): ConsoleWorkspaceContextValue =>
  useOutletContext<ConsoleWorkspaceContextValue>();
