import type { OperationName } from "@lda/workflow-rpc";

const defineBrowserOperationNames = <
  const Names extends ReadonlyArray<OperationName>,
>(names: Names): Names => names;

// Keep this security boundary independent: adding RPC client support must not
// automatically expose the operation through the browser proxy.
export const browserAllowedOperationNames = defineBrowserOperationNames([
  "workflow.health",
  "workflow.sources.list",
  "workflow.capabilities.list",
  "workflow.capabilities.inspect",
  "workflow.draft_workspaces.list",
  "workflow.draft_workspaces.get",
  "workflow.artifacts.list",
  "workflow.artifacts.inspect",
  "workflow.deployments.list",
  "workflow.deployments.inspect",
  "workflow.deployments.validate",
  "workflow.runs.list",
  "workflow.runs.inspect",
  "workflow.runs.start",
  "workflow.runs.resume",
  "workflow.runs.trace",
]);

export type BrowserAllowedOperationName =
  (typeof browserAllowedOperationNames)[number];

const browserAllowedOperationNameSet: ReadonlySet<string> = new Set(
  browserAllowedOperationNames,
);

export const isBrowserAllowedOperationName = (
  value: string,
): value is BrowserAllowedOperationName =>
  browserAllowedOperationNameSet.has(value);
