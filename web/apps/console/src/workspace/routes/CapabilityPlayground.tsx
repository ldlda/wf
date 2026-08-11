import { useState } from "react";
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

const formatKind = (kind: CapabilityDetail["kind"]): string =>
  kind === "node_spec" ? "Node spec" : "Wrapper artifact";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const latestCallEvidence = (
  evidence: ReadonlyArray<EvidenceRecord>,
  target: string | null,
): EvidenceRecord | null => {
  for (let index = evidence.length - 1; index >= 0; index -= 1) {
    const record = evidence[index];
    if (record === undefined) continue;
    if (
      record.operation === "workflow.capabilities.call" &&
      (target === null || record.target === target)
    ) {
      return record;
    }
  }
  return null;
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
  onAddToDraft,
}: {
  readonly capability: CapabilityDetail;
  readonly onAddToDraft: (() => void) | undefined;
}) => (
  <section
    aria-labelledby="capability-playground-contract-heading"
    className="capability-playground__panel"
    id="capability-playground-contract-panel"
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

const outcomeLabel = (outcome: string): string =>
  outcome === "runtime_error" ? "Completed with runtime error" : "Completed";

const ResultReceipt = ({
  result,
  evidence,
}: {
  readonly result: CapabilityCallResult;
  readonly evidence: EvidenceRecord | null;
}) => (
  <section
    aria-labelledby="capability-playground-result-heading"
    className="capability-playground__receipt"
  >
    <div className="capability-playground__receipt-heading">
      <div>
        <p className="capability-playground__receipt-label">Result receipt</p>
        <h3 id="capability-playground-result-heading">{result.qualifiedName}</h3>
      </div>
      <p
        className="capability-playground__outcome"
        data-outcome={result.outcome === "runtime_error" ? "runtime-error" : "completed"}
      >
        <CheckCircle2 aria-hidden="true" size={17} strokeWidth={2} />
        <span>{outcomeLabel(result.outcome)}</span>
      </p>
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
    {result.outcome === "runtime_error" && (
      <p className="capability-playground__runtime-note">
        No workflow run or trace was created.
      </p>
    )}
    <div className="capability-playground__receipt-section">
      <h4>Diagnostics</h4>
      {result.diagnostics.length > 0 ? (
        <ul className="capability-playground__diagnostics">
          {result.diagnostics.map((diagnostic, index) => (
            <li key={`${diagnostic.code}-${index}`}>
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
  target,
  executor,
}: {
  readonly capability: CapabilityDetail;
  readonly target: string | null;
  readonly executor: ConsoleWriteExecutor | null;
}) => {
  const controller = useCapabilityPlayground(capability.name);
  const { connection } = useConsoleWorkspace();
  const [localError, setLocalError] = useState<string | null>(null);
  const evidence =
    controller.phase === "result"
      ? latestCallEvidence(connection.evidence, target)
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
    controller.call(result.value);
  };

  return (
    <section
      aria-labelledby="capability-playground-try-heading"
      className="capability-playground__panel capability-playground__panel--try"
      id="capability-playground-try-panel"
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
              submitLabel={controller.phase === "calling" ? "Calling capability..." : "Call capability"}
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
        <ResultReceipt result={controller.result} evidence={evidence} />
      )}
    </section>
  );
};

export const CapabilityPlayground = ({
  capability,
  target,
  executor,
  onAddToDraft,
}: CapabilityPlaygroundProps) => {
  const [activeTab, setActiveTab] = useState<PlaygroundTab>("contract");
  const tabId = (tab: PlaygroundTab): string => `capability-playground-tab-${tab}`;

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
        {([
          ["contract", "Contract"],
          ["try", "Try capability"],
        ] as const).map(([tab, label]) => (
          <button
            aria-controls={`capability-playground-${tab}-panel`}
            aria-selected={activeTab === tab}
            className="capability-playground__tab"
            id={tabId(tab)}
            key={tab}
            onClick={() => setActiveTab(tab)}
            role="tab"
            type="button"
          >
            {label}
          </button>
        ))}
      </div>
      {activeTab === "contract" ? (
        <ContractView capability={capability} onAddToDraft={onAddToDraft} />
      ) : (
        <TryView capability={capability} executor={executor} target={target} />
      )}
    </section>
  );
};
