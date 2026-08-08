import {
  createConsoleExecutor,
  type ConsoleExecutor,
  type ConsoleExecutorOptions,
} from "./executor-protocol.js";

export interface ConsoleWriteExecutor extends ConsoleExecutor {}

export const createConsoleWriteExecutor = (
  options: ConsoleExecutorOptions,
): ConsoleWriteExecutor => createConsoleExecutor(options);
