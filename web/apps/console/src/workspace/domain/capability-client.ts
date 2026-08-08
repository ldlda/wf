import type { OperationName } from "../../connection/contracts.js";
import {
  decodeCapabilityDetail,
  decodeCapabilityPage,
  type CapabilityDetail,
  type CapabilityPage,
} from "./capability-models.js";
import { ConsoleClientError } from "./errors.js";
import type { ConsoleReadExecutor } from "./read-executor.js";

export interface CapabilityClient {
  list(input: {
    readonly query?: string;
    readonly sourceId?: string;
    readonly cursor?: string;
    readonly limit?: number;
  }): Promise<CapabilityPage>;
  inspect(qualifiedName: string): Promise<CapabilityDetail>;
}

const invalidInput = (operation: OperationName, message: string): ConsoleClientError =>
  new ConsoleClientError("operation", operation, message);

export const createCapabilityClient = (
  executor: ConsoleReadExecutor,
): CapabilityClient => ({
  list: (input) => {
    const params: Record<string, string | number> = {};
    if (input.query !== undefined) params.query = input.query;
    if (input.sourceId !== undefined) params.source_id = input.sourceId.trim();
    if (input.cursor !== undefined) params.cursor = input.cursor;
    if (input.limit !== undefined) params.limit = input.limit;
    return executor.run(
      "workflow.capabilities.list",
      params,
      decodeCapabilityPage,
    );
  },

  inspect: (qualifiedName) => {
    const normalizedQualifiedName = qualifiedName.trim();
    if (!normalizedQualifiedName) {
      return Promise.reject(
        invalidInput(
          "workflow.capabilities.inspect",
          "qualified capability name must not be blank",
        ),
      );
    }
    return executor.run(
      "workflow.capabilities.inspect",
      { qualified_name: normalizedQualifiedName },
      decodeCapabilityDetail,
    );
  },
});
