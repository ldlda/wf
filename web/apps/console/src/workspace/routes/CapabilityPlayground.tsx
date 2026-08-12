import { useState, type KeyboardEvent } from "react";
import { AlertCircle, CheckCircle2, Clock3, Play } from "lucide-react";
import type { EvidenceRecord } from "../../app/state.js";
import { formatBoundedJson } from "../domain/format-bounded-json.js";
import type {
  CapabilityCallResult,
  CapabilityDetail,
} from "../domain/capability-models.js";
import type { ConsoleWriteExecutor } from "../domain/write-executor.js";
import { useConsoleWorkspace } from "../context.js";
import { SchemaForm } from "../schema-form/SchemaForm.js";
import type { SchemaSerializationResult } from "../schema-form/schema-values.js";
import { useCapabilityPlayground } from "./useCapabilityPlayground.js";

export type CapabilityPlaygroundProps = {
  readonly capability: CapabilityDetail;
  readonly target: string | null;
  readonly executor: ConsoleWriteExecutor | null;
  readonly onAddToDraft?: () => void;
};

type PlaygroundTab = "contract" | "try";

type SubmittedCall = {
  readonly baselineEvidenceIds: ReadonlySet<string>;
  readonly deploymentId: string | null;
  readonly executor: ConsoleWriteExecutor | null;
  readonly payload: Record<string, unknown>;
  readonly payloadText: string;
  readonly qualifiedName: string;
  readonly target: string | null;
};

const PLAYGROUND_TABS: readonly PlaygroundTab[] = ["contract", "try"];
const TAB_IDS: Record<PlaygroundTab, string> = {
  contract: "capability-playground-tab-contract",
  try: "capability-playground-tab-try",
};
const PANEL_IDS: Record<PlaygroundTab, string> = {
  contract: "capability-playground-contract-panel",
  try: "capability-playground-try-panel",
};

const formatKind = (kind: CapabilityDetail["kind"]): string =>
  kind === "node_spec" ? "Node spec" : "Wrapper artifact";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

type CapabilityRequestProjection = {
  readonly deploymentId: string | null;
  readonly qualifiedName: string;
};

const normalizeDeploymentId = (value: unknown): string | null => {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized === "" ? null : normalized;
};

const capabilityRequestProjection = (
  request: unknown,
): CapabilityRequestProjection | null => {
  if (
    !isRecord(request) ||
    request.jsonrpc !== "2.0" ||
    request.method !== "workflow.capabilities.call" ||
    !isRecord(request.params)
  ) {
    return null;
  }
  const params = request.params;
  if (typeof params.qualified_name !== "string") return null;
  if (
    params.deployment_id !== undefined &&
    params.deployment_id !== null &&
    typeof params.deployment_id !== "string"
  ) {
    return null;
  }
  return {
    deploymentId: normalizeDeploymentId(params.deployment_id),
    qualifiedName: params.qualified_name,
  };
};

const submittedCallEvidence = (
  evidence: ReadonlyArray<EvidenceRecord>,
  submittedCall: SubmittedCall,
): EvidenceRecord | null => {
  if (submittedCall.target === null) return null;
  const matches = evidence.filter((record) => {
    if (
      submittedCall.baselineEvidenceIds.has(record.id) ||
      record.operation !== "workflow.capabilities.call" ||
      record.target !== submittedCall.target
    ) {
      return false;
    }
    const request = capabilityRequestProjection(record.request);
    return (
      request !== null &&
      request.qualifiedName === submittedCall.qualifiedName &&
      request.deploymentId === submittedCall.deploymentId
    );
  });
  // Sanitized payloads cannot provide identity. Any concurrent same-identity
  // call is therefore ambiguous and must fail closed.
  return matches.length === 1 ? matches[0] ?? null : null;
};

const schemaText = (value: Record<string, unknown>): string =>
  formatBoundedJson(value, 6_000);

const SchemaBlock = ({
  heading,
  value,
}: {
  readonly heading: string;
  readonly value: Record<string, unknown>;
}) => (
  <div className="capability-playground__schema-block">
    <h3>{heading}</h3>
    <details>
      <summary>View {heading.toLowerCase()}</summary>
      <pre aria-label={`${heading} JSON`}>{schemaText(value)}</pre>
    </details>
  </div>
);

const ContractView = ({
  capability,
  hidden,
  onAddToDraft,
}: {
  readonly capability: CapabilityDetail;
  readonly hidden: boolean;
  readonly onAddToDraft: (() => void) | undefined;
}) => (
  <section
    aria-labelledby={TAB_IDS.contract}
    className="capability-playground__panel"
    hidden={hidden}
    id={PANEL_IDS.contract}
    role="tabpanel"
    tabIndex={0}
  >
    <h3 id="capability-playground-contract-heading">Current contract</h3>
    <dl className="capability-playground__facts">
      <div>
        <dt>Kind</dt>
        <dd>{formatKind(capability.kind)}</dd>
      </div>
      <div>
        <dt>Source</dt>
        <dd>{capability.sourceId}</dd>
      </div>
      <div>
        <dt>Async</dt>
        <dd>{capability.isAsync ? "yes" : "no"}</dd>
      </div>
      <div>
        <dt>Outcomes</dt>
        <dd>{capability.outcomes.join(", ") || "none"}</dd>
      </div>
      {capability.kind === "wrapper_artifact" && (
        <>
          <div>
            <dt>Artifact</dt>
            <dd>{capability.artifactId}</dd>
          </div>
          <div>
            <dt>Version</dt>
            <dd>{capability.version}</dd>
          </div>
        </>
      )}
    </dl>
    {capability.description && <p className="capability-playground__description">{capability.description}</p>}
    <div className="capability-playground__schemas">
      <SchemaBlock heading="Input schema" value={capability.inputSchema} />
      <SchemaBlock heading="Output schema" value={capability.outputSchema} />
      <SchemaBlock heading="Wrapper hints" value={capability.wrapperHints} />
    </div>
    <button onClick={onAddToDraft} type="button">
      Add to draft
    </button>
  </section>
);

const formatSerializationIssues = (
  result: SchemaSerializationResult,
): string => result.issues.map((issue) => issue.message).join(" ");

const diagnosticKey = (diagnostic: CapabilityCallResult["diagnostics"][number]): string =>
  [diagnostic.code, diagnostic.logicalRef, diagnostic.severity, diagnostic.message].join("|");

const outcomeLabel = (outcome: string): string =>
  outcome === "runtime_error" ? "Completed with runtime error" : "Completed";

const ResultReceipt = ({
  result,
  evidence,
  submittedCall,
}: {
  readonly result: CapabilityCallResult;
  readonly evidence: EvidenceRecord | null;
  readonly submittedCall: SubmittedCall;
}) => (
  <section
    aria-labelledby="capability-playground-result-heading"
    className="capability-playground__receipt"
  >
    <div className="capability-playground__receipt-heading">
      <div>
        <p className="capability-playground__receipt-label">Result receipt</p>
        <h3 id="capability-playground-result-heading">
          {result.qualifiedName}
        </h3>
      </div>
      <p
        className="capability-playground__outcome"
        data-outcome={
          result.outcome === "runtime_error" ? "runtime-error" : "completed"
        }
      >
        {result.outcome === "runtime_error" ? (
          <AlertCircle aria-hidden="true" size={17} strokeWidth={2} />
        ) : (
          <CheckCircle2 aria-hidden="true" size={17} strokeWidth={2} />
        )}
        <span>{outcomeLabel(result.outcome)}</span>
      </p>
    </div>
    <div
      aria-labelledby="capability-playground-submitted-heading"
      className="capability-playground__submitted-request"
    >
      <h4 id="capability-playground-submitted-heading">Submitted request</h4>
      <dl className="capability-playground__receipt-facts">
        <div>
          <dt>Deployment</dt>
          <dd aria-label="Submitted deployment">
            {submittedCall.deploymentId ?? "default"}
          </dd>
        </div>
      </dl>
      <pre aria-label="Submitted payload">{submittedCall.payloadText}</pre>
    </div>
    <dl className="capability-playground__receipt-facts">
      <div>
        <dt>Outcome</dt>
        <dd>{result.outcome}</dd>
      </div>
      <div>
        <dt>Deployment</dt>
        <dd>{result.deploymentId ?? "default"}</dd>
      </div>
      {evidence && (
        <>
          <div>
            <dt>Evidence operation</dt>
            <dd>{evidence.operation}</dd>
          </div>
          <div>
            <dt>Duration</dt>
            <dd>
              <Clock3 aria-hidden="true" size={14} strokeWidth={1.8} />
              {evidence.durationMs} ms
            </dd>
          </div>
          <div>
            <dt>Target</dt>
            <dd>{evidence.target}</dd>
          </div>
        </>
      )}
    </dl>
    {!evidence && (
      <p className="capability-playground__muted">
        Call evidence was not retained for this connection.
      </p>
    )}
    <p className="capability-playground__runtime-note">
      A direct capability call creates no workflow run or trace.
    </p>
    <div className="capability-playground__receipt-section">
      <h4>Diagnostics</h4>
      {result.diagnostics.length > 0 ? (
        <ul className="capability-playground__diagnostics">
          {result.diagnostics.map((diagnostic) => (
            <li key={diagnosticKey(diagnostic)}>
              <span className="capability-playground__diagnostic-meta">
                {diagnostic.severity} / {diagnostic.code}
              </span>
              <span>{diagnostic.message}</span>
              {diagnostic.repairHint && (
                <small>Next: {diagnostic.repairHint}</small>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="capability-playground__muted">No diagnostics returned.</p>
      )}
    </div>
    <div className="capability-playground__receipt-section">
      <h4>Output</h4>
      {result.output === null ? (
        <p className="capability-playground__muted">No output returned.</p>
      ) : (
        <pre aria-label="Capability output">
          {formatBoundedJson(result.output)}
        </pre>
      )}
    </div>
  </section>
);

const TryView = ({
  capability,
  hidden,
  target,
  executor,
}: {
  readonly capability: CapabilityDetail;
  readonly hidden: boolean;
  readonly target: string | null;
  readonly executor: ConsoleWriteExecutor | null;
}) => {
  const controller = useCapabilityPlayground(capability.name);
  const { connection } = useConsoleWorkspace();
  const [localError, setLocalError] = useState<string | null>(null);
  const [submittedCall, setSubmittedCall] = useState<SubmittedCall | null>(null);

  const currentSubmittedCall =
    submittedCall !== null &&
    submittedCall.executor === executor &&
    submittedCall.qualifiedName === capability.name &&
    submittedCall.target === target &&
    controller.phase === "result" &&
    controller.result?.qualifiedName === submittedCall.qualifiedName
      ? submittedCall
      : null;
  const evidence = currentSubmittedCall
    ? submittedCallEvidence(connection.evidence, currentSubmittedCall)
    : null;
  const operationAvailable = executor !== null && target !== null && controller.phase !== "disconnected";

  const handleSubmit = (result: SchemaSerializationResult): void => {
    setLocalError(null);
    if (result.issues.length > 0) {
      setLocalError(formatSerializationIssues(result));
      return;
    }
    if (!isRecord(result.value)) {
      setLocalError("Capability inputs must serialize to an object.");
      return;
    }
    setSubmittedCall({
      baselineEvidenceIds: new Set(connection.evidence.map((record) => record.id)),
      deploymentId: normalizeDeploymentId(controller.deploymentId),
      executor,
      payload: result.value,
      payloadText: formatBoundedJson(result.value),
      qualifiedName: capability.name,
      target,
    });
    controller.call(result.value);
  };

  return (
    <>
      <section
        aria-labelledby={TAB_IDS.try}
        className="capability-playground__panel capability-playground__panel--try"
        hidden={hidden}
        id={PANEL_IDS.try}
        role="tabpanel"
        tabIndex={0}
      >
        <div className="capability-playground__try-heading">
          <div>
            <h3 id="capability-playground-try-heading">Try capability</h3>
            <p>
              Use literal values from this form. Nothing runs until you acknowledge the immediate call.
            </p>
          </div>
          <Play aria-hidden="true" size={20} strokeWidth={1.8} />
        </div>
        <div className="capability-playground__warning" role="note">
          <AlertCircle aria-hidden="true" size={18} strokeWidth={1.8} />
          <p>This calls the capability immediately against the connected workflow server.</p>
        </div>
        {!operationAvailable ? (
          <p className="capability-playground__disabled" role="status">
            Capability calls are unavailable until a workflow server is connected.
          </p>
        ) : (
          <>
            {capability.kind === "wrapper_artifact" && (
              <div className="capability-playground__deployment">
                <label htmlFor="capability-wrapper-deployment">Wrapper deployment ID</label>
                <input
                  id="capability-wrapper-deployment"
                  onChange={(event) => controller.setDeploymentId(event.target.value)}
                  type="text"
                  value={controller.deploymentId}
                />
                <small>Optional. Leave blank to use the server default.</small>
              </div>
            )}
            <label className="capability-playground__acknowledgement">
              <input
                checked={controller.acknowledged}
                onChange={(event) => controller.setAcknowledged(event.target.checked)}
                type="checkbox"
              />
              <span>I understand this executes the capability now.</span>
            </label>
            <fieldset
              className="capability-playground__form-fieldset"
              disabled={!controller.acknowledged || controller.phase === "calling"}
            >
              <legend className="visually-hidden">Literal capability inputs</legend>
              <SchemaForm
                schema={capability.inputSchema}
                onValueChange={() => setLocalError(null)}
                onSubmit={handleSubmit}
                showSourceControls={false}
                submitLabel={
                  controller.phase === "calling"
                    ? "Calling capability..."
                    : "Call capability now"
                }
              />
            </fieldset>
          </>
        )}
        {localError && (
          <p className="capability-playground__local-error" role="alert">
            {localError}
          </p>
        )}
        {controller.phase === "error" && controller.message && (
          <p className="capability-playground__local-error" role="alert">
            {controller.message}
          </p>
        )}
        {controller.phase === "result" && controller.result && (
          currentSubmittedCall ? (
            <ResultReceipt
              evidence={evidence}
              result={controller.result}
              submittedCall={currentSubmittedCall}
            />
          ) : (
            <p className="capability-playground__muted">
              Result receipt unavailable; call again to capture the submitted request.
            </p>
          )
        )}
      </section>
      {controller.phase === "result" && controller.result && (
        <p className="visually-hidden" role="status">
          Capability call completed. Outcome: {controller.result.outcome}.
        </p>
      )}
    </>
  );
};

export const CapabilityPlayground = ({
  capability,
  target,
  executor,
  onAddToDraft,
}: CapabilityPlaygroundProps) => {
  const [activeTab, setActiveTab] = useState<PlaygroundTab>("contract");

  const activateTab = (tab: PlaygroundTab): void => {
    setActiveTab(tab);
    document.getElementById(TAB_IDS[tab])?.focus();
  };

  const handleTabKeyDown = (
    event: KeyboardEvent<HTMLButtonElement>,
    tab: PlaygroundTab,
  ): void => {
    const currentIndex = PLAYGROUND_TABS.indexOf(tab);
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % PLAYGROUND_TABS.length;
    if (event.key === "ArrowLeft") {
      nextIndex = (currentIndex - 1 + PLAYGROUND_TABS.length) % PLAYGROUND_TABS.length;
    }
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = PLAYGROUND_TABS.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    const nextTab = PLAYGROUND_TABS[nextIndex];
    if (nextTab !== undefined) activateTab(nextTab);
  };

  return (
    <section
      aria-labelledby="capability-playground-heading"
      className="capability-playground"
      id="capability-detail"
    >
      <div className="capability-playground__header">
        <h2 id="capability-playground-heading">{capability.name}</h2>
        <span className="capability-playground__source">{capability.sourceId}</span>
      </div>
      <div
        aria-label="Capability detail views"
        className="capability-playground__tabs"
        role="tablist"
      >
        {PLAYGROUND_TABS.map((tab) => {
          const label = tab === "contract" ? "Contract" : "Try capability";
          return (
          <button
            aria-controls={PANEL_IDS[tab]}
            aria-selected={activeTab === tab}
            className="capability-playground__tab"
            id={TAB_IDS[tab]}
            key={tab}
            onClick={() => setActiveTab(tab)}
            onKeyDown={(event) => handleTabKeyDown(event, tab)}
            role="tab"
            tabIndex={activeTab === tab ? 0 : -1}
            type="button"
          >
            {label}
          </button>
          );
        })}
      </div>
      <ContractView
        capability={capability}
        hidden={activeTab !== "contract"}
        onAddToDraft={onAddToDraft}
      />
      <TryView
        capability={capability}
        executor={executor}
        hidden={activeTab !== "try"}
        target={target}
      />
    </section>
  );
};
