import { useRef, useState, type FormEvent } from "react";
import type { AuthoringContractInventory } from "../domain/authoring-contract-models.js";
import type { DraftWorkspace, InputBinding, JsonObject } from "../domain/draft-workspace-models.js";
import { AuthoringPathPicker } from "./AuthoringPathPicker.js";
import { WorkflowSchemaFieldsForm } from "./WorkflowSchemaFieldsForm.js";
import { normalizeOutcomes, type WorkflowContractKind } from "./workflow-contract-editor.js";
import type { DraftAuthoringController } from "./useDraftAuthoring.js";

type WorkflowContractInspectorProps = {
  readonly contract: WorkflowContractKind;
  readonly controller: DraftAuthoringController;
  readonly draft: DraftWorkspace;
  readonly inventory: AuthoringContractInventory | null;
};

type OutputRow = {
  readonly id: string;
  readonly kind: "path" | "value";
  readonly source: string;
  readonly value: string;
  readonly target: string;
};

const isObject = (value: unknown): value is JsonObject =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const draftObject = (draft: DraftWorkspace): JsonObject => isObject(draft.draft) ? draft.draft : {};

const pathText = (value: unknown): string => {
  if (typeof value === "string") return value;
  if (!isObject(value) || !Array.isArray(value.parts) || typeof value.root !== "string") return "";
  return [value.root, ...value.parts.map(String)].join(".");
};

const outputRows = (draft: DraftWorkspace): ReadonlyArray<OutputRow> => {
  const raw = draftObject(draft).output;
  if (!Array.isArray(raw)) return [];
  const rows: OutputRow[] = [];
  raw.forEach((item, index) => {
    if (!isObject(item)) return;
    const target = pathText(item.target);
    if ("path" in item) {
      rows.push({ id: `output-${index}`, kind: "path", source: pathText(item.path), value: "", target });
      return;
    }
    if ("value" in item) {
      rows.push({ id: `output-${index}`, kind: "value", source: "", value: JSON.stringify(item.value) ?? "null", target });
    }
  });
  return rows;
};

const parseLiteral = (value: string): unknown => {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
};

const schemaFor = (draft: DraftWorkspace, contract: "input" | "state" | "output"): unknown =>
  draftObject(draft)[`${contract}_schema`];

const contractPatch = (
  contract: "input" | "state" | "output",
  schema: JsonObject,
) => contract === "input"
  ? { inputSchema: schema }
  : contract === "state"
    ? { stateSchema: schema }
    : { outputSchema: schema };

const StatusTruth = ({ controller, draft }: Pick<WorkflowContractInspectorProps, "controller" | "draft">) => (
  <div className="workflow-contract-inspector__status" aria-live="polite">
    {controller.dirty && controller.phase === "idle" && <span>Unsaved changes</span>}
    {controller.phase === "saving" && <span>Saving canonical draft...</span>}
    {draft.status === "invalid" && controller.phase === "idle" && <span>Saved with validation diagnostics</span>}
  </div>
);

const EntryStepForm = ({ controller, draft, inventory }: WorkflowContractInspectorProps) => {
  const [stepId, setStepId] = useState(() => pathText(draft.summary.start));
  return (
    <form className="workflow-contract-entry" onSubmit={(event) => {
      event.preventDefault();
      if (stepId !== "") void controller.setStart(stepId);
    }}>
      <label>
        Entry step
        <select onChange={(event) => { setStepId(event.target.value); controller.markDirty(); }} value={stepId}>
          <option value="">Choose a step</option>
          {(inventory?.entrySteps ?? []).map((step) => <option key={step.stepId} value={step.stepId}>{step.label} ({step.stepId})</option>)}
        </select>
      </label>
      <button disabled={stepId === ""} type="submit">Save entry step</button>
    </form>
  );
};

const WorkflowOutputBindingsForm = ({ controller, draft, inventory }: WorkflowContractInspectorProps) => {
  const [rows, setRows] = useState(() => outputRows(draft));
  const nextId = useRef(rows.length);
  const sources = (inventory?.readableSources ?? []).filter(
    (option) => option.origin !== "runtime_context" && option.uses.includes("workflow_output"),
  );
  const targets = inventory?.workflowOutputTargets ?? [];
  const update = (id: string, patch: Partial<OutputRow>): void => {
    setRows((current) => current.map((row) => row.id === id ? { ...row, ...patch } : row));
    controller.markDirty();
  };
  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const bindings: InputBinding[] = rows.filter((row) => row.target.trim() !== "").map((row) => row.kind === "path"
      ? { path: row.source, target: row.target }
      : { value: parseLiteral(row.value), target: row.target });
    void controller.setWorkflowOutputBindings(bindings);
  };
  return (
    <form className="workflow-output-bindings" onSubmit={submit}>
      <h3>Final output bindings</h3>
      {rows.map((row, index) => (
        <fieldset key={row.id}>
          <legend>Output binding {index + 1}</legend>
          <label>Source kind<select value={row.kind} onChange={(event) => update(row.id, { kind: event.target.value as OutputRow["kind"] })}><option value="path">Path</option><option value="value">Literal</option></select></label>
          {row.kind === "path" ? (
            <AuthoringPathPicker allowCustom label={`Source for output binding ${index + 1}`} onChange={(source) => update(row.id, { source })} options={sources} uses="workflow_output" value={row.source} />
          ) : <label>Literal JSON<textarea value={row.value} onChange={(event) => update(row.id, { value: event.target.value })} /></label>}
          <label>Output target<select value={row.target} onChange={(event) => update(row.id, { target: event.target.value })}><option value="">Choose output field</option>{targets.map((target) => <option key={target.path} value={target.path.replace(/^output\./, "")}>{target.label}</option>)}</select></label>
          <div className="workflow-output-bindings__actions">
            <button
              disabled={index === 0}
              onClick={() => {
                setRows((current) => {
                  const copy = [...current];
                  [copy[index - 1], copy[index]] = [copy[index]!, copy[index - 1]!];
                  return copy;
                });
                controller.markDirty();
              }}
              type="button"
            >
              Move up
            </button>
            <button onClick={() => { setRows((current) => current.filter((item) => item.id !== row.id)); controller.markDirty(); }} type="button">Remove binding</button>
          </div>
        </fieldset>
      ))}
      <button onClick={() => { setRows((current) => [...current, { id: `output-new-${nextId.current++}`, kind: "path", source: "", value: "", target: "" }]); controller.markDirty(); }} type="button">Add output binding</button>
      <button type="submit">Save output bindings</button>
    </form>
  );
};

const OutcomesForm = ({ controller, draft }: WorkflowContractInspectorProps) => {
  const raw = draftObject(draft).outcomes;
  const [rows, setRows] = useState<ReadonlyArray<string>>(() => Array.isArray(raw) ? raw.map(String) : []);
  return (
    <form className="workflow-outcomes-form" onSubmit={(event) => { event.preventDefault(); void controller.setContract({ outcomes: normalizeOutcomes(rows) }); }}>
      {rows.map((outcome, index) => <div key={index}><label>Outcome {index + 1}<input value={outcome} onChange={(event) => { setRows((current) => current.map((item, itemIndex) => itemIndex === index ? event.target.value : item)); controller.markDirty(); }} /></label><button onClick={() => { setRows((current) => current.filter((_, itemIndex) => itemIndex !== index)); controller.markDirty(); }} type="button">Remove</button></div>)}
      <button onClick={() => { setRows((current) => [...current, ""]); controller.markDirty(); }} type="button">Add outcome</button>
      <button type="submit">Save outcomes</button>
    </form>
  );
};

export const WorkflowContractInspector = (props: WorkflowContractInspectorProps) => {
  const { contract, controller, draft } = props;
  const title = contract.charAt(0).toUpperCase() + contract.slice(1);
  return (
    <section aria-labelledby="workflow-contract-heading" className="workflow-contract-inspector">
      <p className="workspace-route-pending__eyebrow">Workflow projection</p>
      <h2 id="workflow-contract-heading">{title} contract</h2>
      <StatusTruth controller={controller} draft={draft} />
      {contract === "outcomes" ? <OutcomesForm {...props} /> : (
        <>
          <WorkflowSchemaFieldsForm
            contract={contract}
            key={`${contract}:${controller.resetGeneration}`}
            onDirtyChange={controller.markDirty}
            onSubmit={(schema) => controller.setContract(contractPatch(contract, schema))}
            schema={schemaFor(draft, contract)}
          />
          {contract === "input" && <EntryStepForm {...props} />}
          {contract === "state" && <p className="workflow-contract-inspector__impact">Removing state fields can invalidate existing bindings. Review diagnostics after saving.</p>}
          {contract === "output" && <WorkflowOutputBindingsForm {...props} />}
        </>
      )}
    </section>
  );
};
