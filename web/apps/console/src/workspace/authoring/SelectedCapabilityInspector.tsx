import { useState, type ReactNode } from "react";
import type { CapabilityDetail } from "../domain/capability-models.js";
import type { DraftDiagnostic, DraftWorkspace } from "../domain/draft-workspace-models.js";
import { CapabilitySetupForm } from "./CapabilitySetupForm.js";
import { StepInputBindingsForm } from "./StepInputBindingsForm.js";
import { StepOutputBindingsForm } from "./StepOutputBindingsForm.js";
import {
  bindingDiagnosticsForStep,
  inputBindingRows,
  outputBindingRows,
  projectSelectedStepDataflow,
} from "./selected-step-dataflow.js";
import type { DraftAuthoringController } from "./useDraftAuthoring.js";

type InspectorTab = "setup" | "inputs" | "outputs";

export type SelectedCapabilityInspectorProps = {
  readonly draft: DraftWorkspace;
  readonly stepId: string;
  readonly nodeKind?: string;
  readonly nodeRef: string | null;
  readonly controller: DraftAuthoringController;
  readonly capabilityDetail: CapabilityDetail | null;
  readonly capabilityDetailPhase: "disconnected" | "loading" | "ready" | "error";
  readonly capabilityDetailMessage: string | null;
};

type JsonRecord = Readonly<Record<string, unknown>>;

const isRecord = (value: unknown): value is JsonRecord =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const selectedStep = (draft: DraftWorkspace, stepId: string): JsonRecord | null => {
  if (!isRecord(draft.draft)) return null;
  if (Array.isArray(draft.draft.nodes)) {
    const node = draft.draft.nodes.find((candidate) => isRecord(candidate) && candidate.id === stepId);
    return isRecord(node) ? node : null;
  }
  const steps = draft.draft.steps;
  return isRecord(steps) && isRecord(steps[stepId]) ? steps[stepId] : null;
};

const diagnosticParts = (path: string): ReadonlyArray<string> => {
  const normalized = path.startsWith("/")
    ? path.slice(1).replaceAll("~1", "/").replaceAll("~0", "~")
    : path.replace(/\[([^\]]+)\]/g, ".$1");
  return normalized.split(".").filter((part) => part.length > 0);
};

const setupDiagnostics = (
  diagnostics: ReadonlyArray<DraftDiagnostic>,
  stepId: string,
): ReadonlyArray<{ readonly path: ReadonlyArray<string>; readonly message: string }> =>
  diagnostics.flatMap((diagnostic) => {
    if (diagnostic.stepId !== null && diagnostic.stepId !== stepId) return [];
    const parts = diagnosticParts(diagnostic.path);
    const stepIndex = parts.indexOf(stepId);
    if (stepIndex >= 0 && parts[stepIndex - 1] !== "steps" && parts[stepIndex - 1] !== "nodes") return [];
    const field = parts.at(-1);
    return field === "desc" || field === "retry" || field === "timeout_seconds"
      ? [{ path: [field], message: diagnostic.message }]
      : [];
  });

const emptyStateSchema = { type: "object", properties: {} };
const tabLabels: Record<InspectorTab, string> = { setup: "Setup", inputs: "Inputs", outputs: "Outputs" };
const tabPanelId = (tab: InspectorTab): string => `selected-step-panel-${tab}`;
const tabId = (tab: InspectorTab): string => `selected-step-tab-${tab}`;

const TabPanel = ({
  activeTab,
  children,
  tab,
}: {
  readonly activeTab: InspectorTab;
  readonly children: ReactNode;
  readonly tab: InspectorTab;
}) => (
  <section
    aria-labelledby={tabId(tab)}
    className="selected-capability-inspector__panel"
    hidden={activeTab !== tab}
    id={tabPanelId(tab)}
    role="tabpanel"
  >
    {children}
  </section>
);

export const SelectedCapabilityInspector = ({
  draft,
  stepId,
  nodeKind,
  nodeRef,
  controller,
  capabilityDetail,
  capabilityDetailPhase,
  capabilityDetailMessage,
}: SelectedCapabilityInspectorProps) => {
  const [activeTab, setActiveTab] = useState<InspectorTab>("setup");
  const rawStep = selectedStep(draft, stepId);
  const projected = projectSelectedStepDataflow(draft, stepId);
  const preservedForm = controller.preservedCapabilityForm?.kind === "update" &&
    controller.preservedCapabilityForm.input.stepId === stepId
    ? controller.preservedCapabilityForm.input
    : null;
  // Forms receive raw-row projections so malformed persisted entries stay in order.
  const inputRows = inputBindingRows(rawStep?.input ?? preservedForm?.inputBindings);
  const outputRows = outputBindingRows(rawStep?.output);
  const inputDiagnostics = bindingDiagnosticsForStep(draft.diagnostics, stepId, "input", projected?.compiledNodeIndex ?? null);
  const outputDiagnostics = bindingDiagnosticsForStep(draft.diagnostics, stepId, "output", projected?.compiledNodeIndex ?? null);
  const setupInitialValue = projected === null
    ? preservedForm ?? {}
    : {
        ...(projected.description !== undefined ? { description: projected.description } : {}),
        ...(projected.retry !== undefined ? { retry: projected.retry } : {}),
        ...(projected.timeoutSeconds !== undefined ? { timeoutSeconds: projected.timeoutSeconds } : {}),
      };
  const detailReady = capabilityDetailPhase === "ready" && capabilityDetail !== null;
  const isUnsupported = nodeKind !== undefined && nodeKind !== "use";

  return (
    <section className="selected-capability-inspector" aria-label="Selected step editor">
      <section className="authoring-inspector__selection" aria-labelledby="node-selection-heading">
        <p className="workspace-route-pending__eyebrow">Selected step</p>
        <h2 id="node-selection-heading">{stepId}</h2>
        <dl className="authoring-inspector__facts">
          <div><dt>Kind</dt><dd>{nodeKind ?? "use"}</dd></div>
          <div><dt>Reference</dt><dd>{nodeRef ?? projected?.capabilityName ?? "none"}</dd></div>
        </dl>
        <label className="selected-capability-inspector__step-id">
          Step id
          <input aria-label="Step id" readOnly value={stepId} />
        </label>
        {isUnsupported && <p role="status">Read-only: unsupported step kind.</p>}
      </section>

      {!isUnsupported && (
        <>
          <div aria-label="Selected step views" className="selected-capability-inspector__tabs" role="tablist">
            {(Object.keys(tabLabels) as InspectorTab[]).map((tab) => (
              <button
                aria-controls={tabPanelId(tab)}
                aria-selected={activeTab === tab}
                className="selected-capability-inspector__tab"
                id={tabId(tab)}
                key={tab}
                onClick={() => setActiveTab(tab)}
                role="tab"
                tabIndex={activeTab === tab ? 0 : -1}
                type="button"
              >
                {tabLabels[tab]}
              </button>
            ))}
          </div>

          {!detailReady && capabilityDetailPhase === "loading" && <p role="status">Loading capability schema...</p>}
          {!detailReady && capabilityDetailPhase === "error" && (
            <p role="alert">{capabilityDetailMessage ?? "Capability schema failed to load."}</p>
          )}
          {!detailReady && capabilityDetailPhase === "disconnected" && (
            <p role="status">Connect to inspect the capability schema.</p>
          )}
          {detailReady && (
            <>
              <TabPanel activeTab={activeTab} tab="setup">
                <CapabilitySetupForm
                  key={`setup:${stepId}:${controller.resetGeneration}`}
                  diagnostics={setupDiagnostics(draft.diagnostics, stepId)}
                  initialValue={setupInitialValue}
                  onDirtyChange={controller.markDirty}
                  onSubmit={controller.updateSetup}
                />
              </TabPanel>
              <TabPanel activeTab={activeTab} tab="inputs">
                <StepInputBindingsForm
                  key={`inputs:${stepId}:${controller.resetGeneration}`}
                  initialRows={inputRows}
                  inputSchema={capabilityDetail.inputSchema}
                  onDirtyChange={controller.markDirty}
                  onSubmit={controller.setStepInputs}
                  rowDiagnostics={inputDiagnostics.rowIssues}
                />
              </TabPanel>
              <TabPanel activeTab={activeTab} tab="outputs">
                <StepOutputBindingsForm
                  key={`outputs:${stepId}:${controller.resetGeneration}`}
                  initialRows={outputRows}
                  onDirtyChange={controller.markDirty}
                  onSubmit={controller.setStepOutputs}
                  outputSchema={capabilityDetail.outputSchema}
                  rowDiagnostics={outputDiagnostics.rowIssues}
                  stateSchema={(isRecord(draft.draft) ? draft.draft.state_schema : null) ?? emptyStateSchema}
                />
              </TabPanel>
            </>
          )}
        </>
      )}
    </section>
  );
};
