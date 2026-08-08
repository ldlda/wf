import { describe, expect, it, vi } from "vitest";
import {
  decodeArtifactDetail,
  decodeArtifactList,
  decodeDeploymentDetail,
  decodeDeploymentList,
  decodeDeploymentValidation,
  decodeRunDetail,
  decodeRunList,
  decodeTracePage,
} from "../../lifecycle/models.js";
import { createLifecycleClients } from "./lifecycle-clients.js";
import type { ConsoleReadExecutor } from "./read-executor.js";

const executor = () =>
  ({ run: vi.fn().mockResolvedValue({}) }) as unknown as ConsoleReadExecutor;

describe("lifecycle clients", () => {
  it("omits undefined artifact list parameters", async () => {
    const readExecutor = executor();
    const { artifacts } = createLifecycleClients(readExecutor);

    await artifacts.list({ cursor: "artifact-next" });

    expect(readExecutor.run).toHaveBeenCalledWith(
      "workflow.artifacts.list",
      { cursor: "artifact-next" },
      decodeArtifactList,
    );
  });

  it("lowers lifecycle inspection and validation reads", async () => {
    const readExecutor = executor();
    const { artifacts, deployments, runs } = createLifecycleClients(readExecutor);

    await artifacts.inspect("  report  ", 2);
    await deployments.inspect("  report.default  ");
    await deployments.validate("  report.default  ");
    await runs.inspect("  run_123  ");

    expect(readExecutor.run).toHaveBeenNthCalledWith(
      1,
      "workflow.artifacts.inspect",
      { artifact_id: "report", version: 2 },
      decodeArtifactDetail,
    );
    expect(readExecutor.run).toHaveBeenNthCalledWith(
      2,
      "workflow.deployments.inspect",
      { deployment_id: "report.default" },
      decodeDeploymentDetail,
    );
    expect(readExecutor.run).toHaveBeenNthCalledWith(
      3,
      "workflow.deployments.validate",
      { deployment_id: "report.default" },
      decodeDeploymentValidation,
    );
    expect(readExecutor.run).toHaveBeenNthCalledWith(
      4,
      "workflow.runs.inspect",
      { run_id: "run_123" },
      decodeRunDetail,
    );
  });

  it("lowers an explicit run trace range", async () => {
    const readExecutor = executor();
    const { runs } = createLifecycleClients(readExecutor);

    await runs.trace("  run_123  ", 50, 50);

    expect(readExecutor.run).toHaveBeenCalledWith(
      "workflow.runs.trace",
      { run_id: "run_123", trace_range: { start: 50, limit: 50 } },
      decodeTracePage,
    );
  });

  it("rejects invalid lifecycle identifiers, versions, and ranges", async () => {
    const readExecutor = executor();
    const { artifacts, deployments, runs } = createLifecycleClients(readExecutor);

    await expect(artifacts.inspect("", 1)).rejects.toMatchObject({ kind: "operation" });
    await expect(artifacts.inspect("report", 0)).rejects.toMatchObject({ kind: "operation" });
    await expect(deployments.inspect(" ")).rejects.toMatchObject({ kind: "operation" });
    await expect(runs.trace("run_123", -1, 50)).rejects.toMatchObject({ kind: "operation" });
    await expect(runs.trace("run_123", 0, 0)).rejects.toMatchObject({ kind: "operation" });
    expect(readExecutor.run).not.toHaveBeenCalled();
  });

  it("omits undefined run list parameters", async () => {
    const readExecutor = executor();
    const { deployments, runs } = createLifecycleClients(readExecutor);

    await deployments.list();
    await runs.list({ limit: 10 });

    expect(readExecutor.run).toHaveBeenNthCalledWith(
      1,
      "workflow.deployments.list",
      {},
      decodeDeploymentList,
    );
    expect(readExecutor.run).toHaveBeenNthCalledWith(
      2,
      "workflow.runs.list",
      { limit: 10 },
      decodeRunList,
    );
  });
});
