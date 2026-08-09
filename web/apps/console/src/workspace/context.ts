import { useOutletContext } from "react-router-dom";
import { initialState, type ConnectionState, type EvidenceRecord } from "../app/state.js";
import type { ConsoleReadExecutor } from "./domain/read-executor.js";
import type { ConsoleWriteExecutor } from "./domain/write-executor.js";

export type ConsoleWorkspaceContextValue = {
  readonly connection: ConnectionState;
  readonly connectedTarget: string | null;
  readonly recordEvidence: (record: EvidenceRecord) => void;
  readonly readExecutor: ConsoleReadExecutor | null;
  readonly writeExecutor: ConsoleWriteExecutor | null;
};

const STANDALONE_CONTEXT: ConsoleWorkspaceContextValue = {
  connection: initialState(),
  connectedTarget: null,
  recordEvidence: () => undefined,
  readExecutor: null,
  writeExecutor: null,
};

export const useConsoleWorkspace = (): ConsoleWorkspaceContextValue =>
  useOutletContext<ConsoleWorkspaceContextValue>() ?? STANDALONE_CONTEXT;
