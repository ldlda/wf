import type { ConsoleExecutor } from "./executor-protocol.js";
import {
  decodeCapabilityCallResult,
  type CapabilityCallResult,
} from "./capability-models.js";

export type CapabilityCallRequest = {
  readonly qualifiedName: string;
  readonly payload: Record<string, unknown>;
  readonly deploymentId?: string;
};

export const callCapability = (
  executor: ConsoleExecutor,
  request: CapabilityCallRequest,
): Promise<CapabilityCallResult> => {
  const deploymentId = request.deploymentId?.trim();
  return executor.run(
    "workflow.capabilities.call",
    {
      qualified_name: request.qualifiedName,
      payload: request.payload,
      ...(deploymentId ? { deployment_id: deploymentId } : {}),
    },
    decodeCapabilityCallResult,
  );
};
