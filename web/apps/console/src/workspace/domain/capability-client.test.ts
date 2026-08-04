import { describe, expect, it, vi } from "vitest";
import {
  decodeCapabilityDetail,
  decodeCapabilityPage,
} from "./capability-models.js";
import { createCapabilityClient } from "./capability-client.js";
import type { ConsoleReadExecutor } from "./read-executor.js";

const executor = () =>
  ({ run: vi.fn().mockResolvedValue({}) }) as unknown as ConsoleReadExecutor;

describe("CapabilityClient", () => {
  it("lowers list filters to the capability operation payload", async () => {
    const readExecutor = executor();
    const client = createCapabilityClient(readExecutor);

    await client.list({
      query: "document",
      sourceId: "local.lda_docs",
      limit: 50,
    });

    expect(readExecutor.run).toHaveBeenCalledWith(
      "workflow.capabilities.list",
      { query: "document", source_id: "local.lda_docs", limit: 50 },
      decodeCapabilityPage,
    );
  });

  it("lowers a qualified capability name for inspection", async () => {
    const readExecutor = executor();
    const client = createCapabilityClient(readExecutor);

    await client.inspect("local.lda_docs.read_documents");

    expect(readExecutor.run).toHaveBeenCalledWith(
      "workflow.capabilities.inspect",
      { qualified_name: "local.lda_docs.read_documents" },
      decodeCapabilityDetail,
    );
  });

  it("rejects blank capability names before invoking the executor", async () => {
    const readExecutor = executor();
    const client = createCapabilityClient(readExecutor);

    await expect(client.inspect("  ")).rejects.toMatchObject({
      kind: "operation",
      operation: "workflow.capabilities.inspect",
    });
    expect(readExecutor.run).not.toHaveBeenCalled();
  });
});
