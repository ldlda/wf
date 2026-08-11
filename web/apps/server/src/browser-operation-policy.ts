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
  "workflow.draft_workspaces.create_empty",
  "workflow.draft_workspaces.create_from_capability",
  "workflow.draft_workspaces.add_step_from_capability",
  "workflow.draft_workspaces.update_capability_step",
  "workflow.draft_workspaces.set_route",
  "workflow.draft_workspaces.set_step_input_bindings",
  "workflow.draft_workspaces.set_step_output_bindings",
  "workflow.draft_workspaces.validate",
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

const conditionalOperations = new Set<OperationName>([
  "workflow.capabilities.call",
]);

export type BrowserOperationDecision = "allowed" | "disabled" | "unknown";

export type BrowserOperationPolicy = {
  readonly classify: (operation: string) => BrowserOperationDecision;
};

export const createBrowserOperationPolicy = (options: {
  readonly enableCapabilityCalls: boolean;
}): BrowserOperationPolicy => ({
  classify: (operation) => {
    if (browserAllowedOperationNameSet.has(operation)) return "allowed";
    if (conditionalOperations.has(operation as OperationName)) {
      return options.enableCapabilityCalls ? "allowed" : "disabled";
    }
    return "unknown";
  },
});

const loopbackHostnames = new Set(["127.0.0.1", "localhost", "::1"]);

export const capabilityCallsEnabledForHost = (
  hostname: string,
  override: string | undefined,
): boolean => loopbackHostnames.has(hostname) || override === "1";

export const isBrowserAllowedOperationName = (
  value: string,
): value is BrowserAllowedOperationName =>
  browserAllowedOperationNameSet.has(value);
