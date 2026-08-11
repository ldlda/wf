import { describe, expect, it, vi } from "vitest";
import {
  decodeCapabilityCallResult,
  type CapabilityCallResult,
} from "./capability-models.js";
import {
  callCapability,
  type CapabilityCallRequest,
} from "./capability-call-client.js";
import type { ConsoleExecutor } from "./executor-protocol.js";

const result: CapabilityCallResult = {
  qualifiedName: "local.docs.read_documents",
  sourceId: "local.docs",
  kind: "node_spec",
  deploymentId: null,
  outcome: "ok",
  output: { documents: [] },
  diagnostics: [],
};

describe("callCapability", () => {
  it("lowers the request to the executor operation payload", async () => {
    const executor = {
      run: vi.fn().mockResolvedValue(result),
    } as unknown as ConsoleExecutor;
    const request: CapabilityCallRequest = {
      qualifiedName: "local.docs.read_documents",
      payload: { names: ["README.md"] },
      deploymentId: "docs.default",
    };

    await callCapability(executor, request);

    expect(executor.run).toHaveBeenCalledWith(
      "workflow.capabilities.call",
      {
        qualified_name: "local.docs.read_documents",
        payload: { names: ["README.md"] },
        deployment_id: "docs.default",
      },
      decodeCapabilityCallResult,
    );
  });

  it("omits a blank deployment ID", async () => {
    const executor = {
      run: vi.fn().mockResolvedValue(result),
    } as unknown as ConsoleExecutor;

    await callCapability(executor, {
      qualifiedName: "local.docs.read_documents",
      payload: {},
      deploymentId: "  ",
    });

    expect(executor.run).toHaveBeenCalledWith(
      "workflow.capabilities.call",
      {
        qualified_name: "local.docs.read_documents",
        payload: {},
      },
      decodeCapabilityCallResult,
    );
  });
});
