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
): string => {
  const normalizedValue = value.trim();
  if (!normalizedValue) throw invalidInput(operation, `${label} must not be blank`);
  return normalizedValue;
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

export type LifecycleClients = {
  readonly artifacts: ArtifactClient;
  readonly deployments: DeploymentClient;
  readonly runs: RunClient;
};

export const createLifecycleClients = (executor: ConsoleReadExecutor): LifecycleClients => {
  const artifacts: ArtifactClient = {
    list: (input) => {
      const params: Record<string, string | number> = {};
      if (input.cursor !== undefined) params.cursor = input.cursor;
      if (input.limit !== undefined) params.limit = input.limit;
      return executor.run("workflow.artifacts.list", params, decodeArtifactList);
    },
    inspect: async (artifactId, version) => {
      const normalizedArtifactId = requireIdentifier(
        "workflow.artifacts.inspect",
        artifactId,
        "artifact id",
      );
      requirePositiveInteger("workflow.artifacts.inspect", version, "version");
      return executor.run(
        "workflow.artifacts.inspect",
        { artifact_id: normalizedArtifactId, version },
        decodeArtifactDetail,
      );
    },
  };

  const deployments: DeploymentClient = {
    list: () =>
      executor.run("workflow.deployments.list", {}, decodeDeploymentList),
    inspect: async (deploymentId) => {
      const normalizedDeploymentId = requireIdentifier(
        "workflow.deployments.inspect",
        deploymentId,
        "deployment id",
      );
      return executor.run(
        "workflow.deployments.inspect",
        { deployment_id: normalizedDeploymentId },
        decodeDeploymentDetail,
      );
    },
    validate: async (deploymentId) => {
      const normalizedDeploymentId = requireIdentifier(
        "workflow.deployments.validate",
        deploymentId,
        "deployment id",
      );
      return executor.run(
        "workflow.deployments.validate",
        { deployment_id: normalizedDeploymentId },
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
      const normalizedRunId = requireIdentifier(
        "workflow.runs.inspect",
        runId,
        "run id",
      );
      return executor.run(
        "workflow.runs.inspect",
        { run_id: normalizedRunId },
        decodeRunDetail,
      );
    },
    trace: async (runId, start, limit) => {
      const normalizedRunId = requireIdentifier(
        "workflow.runs.trace",
        runId,
        "run id",
      );
      requireTraceRange("workflow.runs.trace", start, limit);
      return executor.run(
        "workflow.runs.trace",
        { run_id: normalizedRunId, trace_range: { start, limit } },
        decodeTracePage,
      );
    },
  };

  return { artifacts, deployments, runs };
};
