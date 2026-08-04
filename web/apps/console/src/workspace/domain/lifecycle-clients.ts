import type { OperationName } from "../../connection/contracts.js";
import {
  decodeArtifactDetail,
  decodeArtifactList,
  decodeDeploymentDetail,
  decodeDeploymentList,
  decodeDeploymentValidation,
  decodeRunDetail,
  decodeRunList,
  decodeTracePage,
  type ArtifactDetail,
  type ArtifactList,
  type DeploymentDetail,
  type DeploymentList,
  type DeploymentValidation,
  type RunDetail,
  type RunList,
  type TracePage,
} from "../../lifecycle/models.js";
import { ConsoleClientError } from "./errors.js";
import type { ConsoleReadExecutor } from "./read-executor.js";

export interface ArtifactClient {
  list(input: {
    readonly cursor?: string;
    readonly limit?: number;
  }): Promise<ArtifactList>;
  inspect(artifactId: string, version: number): Promise<ArtifactDetail>;
}

export interface DeploymentClient {
  list(): Promise<DeploymentList>;
  inspect(deploymentId: string): Promise<DeploymentDetail>;
  validate(deploymentId: string): Promise<DeploymentValidation>;
}

export interface RunClient {
  list(input: {
    readonly cursor?: string;
    readonly limit?: number;
  }): Promise<RunList>;
  inspect(runId: string): Promise<RunDetail>;
  trace(runId: string, start: number, limit: number): Promise<TracePage>;
}

const invalidInput = (
  operation: OperationName,
  message: string,
): ConsoleClientError =>
  new ConsoleClientError("operation", operation, message);

const requireIdentifier = (
  operation: OperationName,
  value: string,
  label: string,
): void => {
  if (!value.trim()) throw invalidInput(operation, `${label} must not be blank`);
};

const requirePositiveInteger = (
  operation: OperationName,
  value: number,
  label: string,
): void => {
  if (!Number.isInteger(value) || value < 1) {
    throw invalidInput(operation, `${label} must be a positive integer`);
  }
};

const requireTraceRange = (
  operation: OperationName,
  start: number,
  limit: number,
): void => {
  if (!Number.isInteger(start) || start < 0) {
    throw invalidInput(operation, "trace start must be a non-negative integer");
  }
  requirePositiveInteger(operation, limit, "trace limit");
};

export const createLifecycleClients = (executor: ConsoleReadExecutor): {
  readonly artifacts: ArtifactClient;
  readonly deployments: DeploymentClient;
  readonly runs: RunClient;
} => {
  const artifacts: ArtifactClient = {
    list: (input) => {
      const params: Record<string, string | number> = {};
      if (input.cursor !== undefined) params.cursor = input.cursor;
      if (input.limit !== undefined) params.limit = input.limit;
      return executor.run("workflow.artifacts.list", params, decodeArtifactList);
    },
    inspect: async (artifactId, version) => {
      requireIdentifier(
        "workflow.artifacts.inspect",
        artifactId,
        "artifact id",
      );
      requirePositiveInteger("workflow.artifacts.inspect", version, "version");
      return executor.run(
        "workflow.artifacts.inspect",
        { artifact_id: artifactId, version },
        decodeArtifactDetail,
      );
    },
  };

  const deployments: DeploymentClient = {
    list: () =>
      executor.run("workflow.deployments.list", {}, decodeDeploymentList),
    inspect: async (deploymentId) => {
      requireIdentifier(
        "workflow.deployments.inspect",
        deploymentId,
        "deployment id",
      );
      return executor.run(
        "workflow.deployments.inspect",
        { deployment_id: deploymentId },
        decodeDeploymentDetail,
      );
    },
    validate: async (deploymentId) => {
      requireIdentifier(
        "workflow.deployments.validate",
        deploymentId,
        "deployment id",
      );
      return executor.run(
        "workflow.deployments.validate",
        { deployment_id: deploymentId },
        decodeDeploymentValidation,
      );
    },
  };

  const runs: RunClient = {
    list: (input) => {
      const params: Record<string, string | number> = {};
      if (input.cursor !== undefined) params.cursor = input.cursor;
      if (input.limit !== undefined) params.limit = input.limit;
      return executor.run("workflow.runs.list", params, decodeRunList);
    },
    inspect: async (runId) => {
      requireIdentifier("workflow.runs.inspect", runId, "run id");
      return executor.run(
        "workflow.runs.inspect",
        { run_id: runId },
        decodeRunDetail,
      );
    },
    trace: async (runId, start, limit) => {
      requireIdentifier("workflow.runs.trace", runId, "run id");
      requireTraceRange("workflow.runs.trace", start, limit);
      return executor.run(
        "workflow.runs.trace",
        { run_id: runId, trace_range: { start, limit } },
        decodeTracePage,
      );
    },
  };

  return { artifacts, deployments, runs };
};
