import {
  createConsoleExecutor,
  type ConsoleExecutor,
  type ConsoleExecutorOptions,
} from "./executor-protocol.js";

export interface ConsoleReadExecutor extends ConsoleExecutor {}

export const createConsoleReadExecutor = (
  options: ConsoleExecutorOptions,
): ConsoleReadExecutor => createConsoleExecutor(options);
