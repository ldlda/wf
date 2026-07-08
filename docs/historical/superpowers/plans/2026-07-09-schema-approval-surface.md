# Schema Approval Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the raw `{ "type": "object" }` interrupt proof in the defense demo with a reusable schema-aware approval surface that can be used by Scene 10, prepared-agent approval messages, and future console interrupt/resume flows.

**Architecture:** Keep runtime validation owned by `wf_core` and persisted run inspection; the web layer only projects known JSON Schema and replay payload data into display fields. Add a small pure projection module, then render it through one approval component used by the typed interrupt panel and the chat approval event. The current replay has a loose resume schema, so the UI must show outcome buttons plus the actual recorded resume payload instead of pretending fields exist.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, Valibot for existing replay decoding, CSS modules by convention through existing presentation stylesheets.

## Global Constraints

- Do not implement JSON Schema validation in the web UI; runtime validation already lives in the workflow engine.
- Do not add a form library or component library in this slice.
- Do not replace the chat surface in this slice; make the approval component reusable by the later AI Elements/chat-library work.
- Keep Scene 10 readable at 720p and avoid adding a modal for the approval form.
- Use submitted/cancelled outcome language, not approved/denied, when describing workflow resume outcomes.
- Raw schema evidence may remain available, but it must not be the primary approval visual.
- Add comments around non-obvious fallback logic, especially when projecting fields from a loose schema plus replay payload.

---

## File Structure

- Create `web/apps/console/src/presentation/approval/schema-approval-model.ts`
  - Pure projection helpers from schema/payload/outcomes to display rows.
- Create `web/apps/console/src/presentation/approval/schema-approval-model.test.ts`
  - Unit tests for explicit schema fields, loose-object fallback, arrays, booleans, and unknown schemas.
- Create `web/apps/console/src/presentation/approval/SchemaApprovalSurface.tsx`
  - Reusable approval UI: heading, outcome buttons, projected fields, payload preview, status text.
- Create `web/apps/console/src/presentation/approval/SchemaApprovalSurface.test.tsx`
  - Component tests for buttons, field rendering, loose schema copy, cancelled/submitted states.
- Modify `web/apps/console/src/presentation/demo-workflow-model.ts`
  - Extend the interrupt projection with request schema, resume payload preview, and resume outcome.
- Modify `web/apps/console/src/presentation/InterruptContractPreview.tsx`
  - Use `SchemaApprovalSurface` for approval mode; keep raw schema compact for preview mode.
- Modify `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
  - Pass the `run_resume` event into the interrupt contract projection.
- Modify `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
  - Update assertions away from raw-schema-first approval and toward form/payload/outcome evidence.
- Modify `web/apps/console/src/demo/agent/events.ts`
  - Add optional approval contract data to `approval-request` parts without importing presentation code.
- Modify `web/apps/console/src/demo/agent/preparedRecipeDriver.ts`
  - Attach replay-derived approval contract data to the `resumeIssueReview` approval request.
- Modify `web/apps/console/src/presentation/OperatorChat.tsx`
  - Render `SchemaApprovalSurface` inside approval-request parts when approval data is present; fall back to current buttons otherwise.
- Modify `web/apps/console/src/presentation/OperatorChat.test.tsx`
  - Assert schema approval renders in chat and still calls approve/cancel handlers.
- Modify `web/apps/console/src/presentation/styles/demo-workflow.css`
  - Add approval surface styles and remove raw-schema dominance in approval mode.
- Modify `docs/current_roadmap.md`
  - Mark this schema approval slice completed when implementation is done and renumber later items.

---

### Task 1: Pure Schema Approval Projection

**Files:**
- Create: `web/apps/console/src/presentation/approval/schema-approval-model.ts`
- Create: `web/apps/console/src/presentation/approval/schema-approval-model.test.ts`

**Interfaces:**
- Produces:

```ts
export type SchemaApprovalFieldKind = "string" | "number" | "boolean" | "array" | "object" | "unknown";

export type SchemaApprovalField = {
  readonly name: string;
  readonly label: string;
  readonly kind: SchemaApprovalFieldKind;
  readonly required: boolean;
  readonly description: string | null;
  readonly valuePreview: string | null;
};

export type SchemaApprovalModel = {
  readonly hasExplicitFields: boolean;
  readonly fields: ReadonlyArray<SchemaApprovalField>;
  readonly payloadPreview: ReadonlyArray<{ readonly key: string; readonly value: string }>;
  readonly outcomes: ReadonlyArray<string>;
};

export type BuildSchemaApprovalModelInput = {
  readonly schema: unknown;
  readonly payload: unknown;
  readonly outcomes: ReadonlyArray<string>;
};

export const buildSchemaApprovalModel = (input: BuildSchemaApprovalModelInput): SchemaApprovalModel;
```

- Consumes: no project runtime APIs; this is a pure projection helper.

- [ ] **Step 1: Write the failing projection tests**

Create `web/apps/console/src/presentation/approval/schema-approval-model.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { buildSchemaApprovalModel } from "./schema-approval-model.js";

describe("buildSchemaApprovalModel", () => {
  it("projects explicit object schema properties into approval fields", () => {
    const model = buildSchemaApprovalModel({
      schema: {
        type: "object",
        required: ["selected_issue_ids"],
        properties: {
          selected_issue_ids: {
            type: "array",
            description: "Issue ids to create",
            items: { type: "string" },
          },
          comment: { type: "string" },
          approved: { type: "boolean" },
        },
      },
      payload: {
        selected_issue_ids: ["risk-1"],
        comment: "Create the selected issue.",
        approved: true,
      },
      outcomes: ["submitted", "cancelled"],
    });

    expect(model.hasExplicitFields).toBe(true);
    expect(model.outcomes).toEqual(["submitted", "cancelled"]);
    expect(model.fields).toEqual([
      {
        name: "selected_issue_ids",
        label: "selected issue ids",
        kind: "array",
        required: true,
        description: "Issue ids to create",
        valuePreview: "[\"risk-1\"]",
      },
      {
        name: "comment",
        label: "comment",
        kind: "string",
        required: false,
        description: null,
        valuePreview: "Create the selected issue.",
      },
      {
        name: "approved",
        label: "approved",
        kind: "boolean",
        required: false,
        description: null,
        valuePreview: "true",
      },
    ]);
  });

  it("uses payload preview when schema is a loose object without properties", () => {
    const model = buildSchemaApprovalModel({
      schema: { type: "object" },
      payload: {
        selected_issue_ids: ["risk-1"],
        comment: "Create the selected issue.",
      },
      outcomes: ["submitted", "cancelled"],
    });

    expect(model.hasExplicitFields).toBe(false);
    expect(model.fields).toEqual([]);
    expect(model.payloadPreview).toEqual([
      { key: "selected_issue_ids", value: "[\"risk-1\"]" },
      { key: "comment", value: "Create the selected issue." },
    ]);
  });

  it("handles non-object schema without throwing", () => {
    const model = buildSchemaApprovalModel({
      schema: true,
      payload: null,
      outcomes: [],
    });

    expect(model.hasExplicitFields).toBe(false);
    expect(model.fields).toEqual([]);
    expect(model.payloadPreview).toEqual([]);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pnpm --filter @lda/console test -- src/presentation/approval/schema-approval-model.test.ts
```

Expected: FAIL because `schema-approval-model.ts` does not exist.

- [ ] **Step 3: Implement the projection helper**

Create `web/apps/console/src/presentation/approval/schema-approval-model.ts`:

```ts
export type SchemaApprovalFieldKind = "string" | "number" | "boolean" | "array" | "object" | "unknown";

export type SchemaApprovalField = {
  readonly name: string;
  readonly label: string;
  readonly kind: SchemaApprovalFieldKind;
  readonly required: boolean;
  readonly description: string | null;
  readonly valuePreview: string | null;
};

export type SchemaApprovalModel = {
  readonly hasExplicitFields: boolean;
  readonly fields: ReadonlyArray<SchemaApprovalField>;
  readonly payloadPreview: ReadonlyArray<{ readonly key: string; readonly value: string }>;
  readonly outcomes: ReadonlyArray<string>;
};

export type BuildSchemaApprovalModelInput = {
  readonly schema: unknown;
  readonly payload: unknown;
  readonly outcomes: ReadonlyArray<string>;
};

type JsonObject = Record<string, unknown>;

const isObject = (value: unknown): value is JsonObject =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const stringArray = (value: unknown): ReadonlyArray<string> =>
  Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === "string") : [];

const formatValue = (value: unknown): string | null => {
  if (value === undefined) return null;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean" || value === null) return String(value);
  return JSON.stringify(value);
};

const fieldKind = (propertySchema: unknown): SchemaApprovalFieldKind => {
  if (!isObject(propertySchema)) return "unknown";
  const type = propertySchema.type;
  if (type === "integer") return "number";
  if (type === "string" || type === "number" || type === "boolean" || type === "array" || type === "object") {
    return type;
  }
  return "unknown";
};

const labelFor = (name: string): string => name.replaceAll("_", " ");

const payloadEntries = (payload: unknown): ReadonlyArray<{ readonly key: string; readonly value: string }> => {
  if (!isObject(payload)) return [];
  return Object.entries(payload).map(([key, value]) => ({
    key,
    value: formatValue(value) ?? "undefined",
  }));
};

export const buildSchemaApprovalModel = ({
  schema,
  payload,
  outcomes,
}: BuildSchemaApprovalModelInput): SchemaApprovalModel => {
  const required = isObject(schema) ? new Set(stringArray(schema.required)) : new Set<string>();
  const properties = isObject(schema) && isObject(schema.properties) ? schema.properties : null;
  const payloadObject = isObject(payload) ? payload : {};

  // This is projection, not validation. For loose schemas the product should
  // still show the recorded resume payload instead of inventing absent fields.
  const fields = properties
    ? Object.entries(properties).map(([name, propertySchema]): SchemaApprovalField => ({
      name,
      label: labelFor(name),
      kind: fieldKind(propertySchema),
      required: required.has(name),
      description: isObject(propertySchema) && typeof propertySchema.description === "string"
        ? propertySchema.description
        : null,
      valuePreview: formatValue(payloadObject[name]),
    }))
    : [];

  return {
    hasExplicitFields: fields.length > 0,
    fields,
    payloadPreview: payloadEntries(payload),
    outcomes,
  };
};
```

- [ ] **Step 4: Run the projection tests**

Run:

```bash
pnpm --filter @lda/console test -- src/presentation/approval/schema-approval-model.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/apps/console/src/presentation/approval/schema-approval-model.ts web/apps/console/src/presentation/approval/schema-approval-model.test.ts
git commit -m "feat: project schema approval fields"
```

---

### Task 2: Reusable Schema Approval Surface

**Files:**
- Create: `web/apps/console/src/presentation/approval/SchemaApprovalSurface.tsx`
- Create: `web/apps/console/src/presentation/approval/SchemaApprovalSurface.test.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`

**Interfaces:**
- Consumes: `buildSchemaApprovalModel(input: BuildSchemaApprovalModelInput): SchemaApprovalModel`
- Produces:

```ts
export type SchemaApprovalSurfaceProps = {
  readonly title: string;
  readonly schema: unknown;
  readonly payload: unknown;
  readonly outcomes: ReadonlyArray<string>;
  readonly runId: string | null;
  readonly state?: "ready" | "submitted" | "cancelled";
  readonly onSubmit?: (() => void) | undefined;
  readonly onCancel?: (() => void) | undefined;
};

export const SchemaApprovalSurface: (props: SchemaApprovalSurfaceProps) => JSX.Element;
```

- [ ] **Step 1: Write the failing component tests**

Create `web/apps/console/src/presentation/approval/SchemaApprovalSurface.test.tsx`:

```tsx
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SchemaApprovalSurface } from "./SchemaApprovalSurface.js";

describe("SchemaApprovalSurface", () => {
  it("renders explicit schema fields and outcome actions", () => {
    const onSubmit = vi.fn();
    const onCancel = vi.fn();

    render(
      <SchemaApprovalSurface
        title="Issue review resume"
        schema={{
          type: "object",
          required: ["selected_issue_ids"],
          properties: {
            selected_issue_ids: { type: "array", description: "Issue ids to create" },
            comment: { type: "string" },
          },
        }}
        payload={{ selected_issue_ids: ["risk-1"], comment: "Create the selected issue." }}
        outcomes={["submitted", "cancelled"]}
        runId="run_recorded_lda_report"
        onSubmit={onSubmit}
        onCancel={onCancel}
      />,
    );

    const surface = screen.getByRole("group", { name: /issue review resume/i });
    expect(within(surface).getByText("selected issue ids")).toBeInTheDocument();
    expect(within(surface).getByText("required")).toBeInTheDocument();
    expect(within(surface).getByText("[\"risk-1\"]")).toBeInTheDocument();
    expect(within(surface).getByText("run_recorded_lda_report")).toBeInTheDocument();

    fireEvent.click(within(surface).getByRole("button", { name: /submit/i }));
    fireEvent.click(within(surface).getByRole("button", { name: /cancel/i }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("renders payload preview for loose object schemas", () => {
    render(
      <SchemaApprovalSurface
        title="Issue review resume"
        schema={{ type: "object" }}
        payload={{ selected_issue_ids: ["risk-1"], comment: "Create the selected issue." }}
        outcomes={["submitted", "cancelled"]}
        runId="run_recorded_lda_report"
      />,
    );

    expect(screen.getByText("No additional resume fields are declared by this schema.")).toBeInTheDocument();
    expect(screen.getByText("selected_issue_ids")).toBeInTheDocument();
    expect(screen.getByText("[\"risk-1\"]")).toBeInTheDocument();
  });

  it("shows submitted and cancelled states without active actions", () => {
    const { rerender } = render(
      <SchemaApprovalSurface
        title="Issue review resume"
        schema={{ type: "object" }}
        payload={{}}
        outcomes={["submitted", "cancelled"]}
        runId={null}
        state="submitted"
      />,
    );

    expect(screen.getByText("Outcome: submitted")).toBeInTheDocument();

    rerender(
      <SchemaApprovalSurface
        title="Issue review resume"
        schema={{ type: "object" }}
        payload={{}}
        outcomes={["submitted", "cancelled"]}
        runId={null}
        state="cancelled"
      />,
    );

    expect(screen.getByText("Outcome: cancelled")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pnpm --filter @lda/console test -- src/presentation/approval/SchemaApprovalSurface.test.tsx
```

Expected: FAIL because `SchemaApprovalSurface.tsx` does not exist.

- [ ] **Step 3: Implement the component**

Create `web/apps/console/src/presentation/approval/SchemaApprovalSurface.tsx`:

```tsx
import { buildSchemaApprovalModel } from "./schema-approval-model.js";

export type SchemaApprovalSurfaceProps = {
  readonly title: string;
  readonly schema: unknown;
  readonly payload: unknown;
  readonly outcomes: ReadonlyArray<string>;
  readonly runId: string | null;
  readonly state?: "ready" | "submitted" | "cancelled";
  readonly onSubmit?: (() => void) | undefined;
  readonly onCancel?: (() => void) | undefined;
};

export const SchemaApprovalSurface = ({
  title,
  schema,
  payload,
  outcomes,
  runId,
  state = "ready",
  onSubmit,
  onCancel,
}: SchemaApprovalSurfaceProps) => {
  const model = buildSchemaApprovalModel({ schema, payload, outcomes });
  const isResolved = state !== "ready";

  return (
    <section className="schema-approval-surface" role="group" aria-label={title} data-state={state}>
      <header className="schema-approval-surface__header">
        <span>Schema-backed decision</span>
        <strong>{title}</strong>
        <code>{runId ?? "run unavailable"}</code>
      </header>

      <div className="schema-approval-surface__body">
        {model.hasExplicitFields ? (
          <dl className="schema-approval-surface__fields">
            {model.fields.map((field) => (
              <div key={field.name} className="schema-approval-surface__field" data-kind={field.kind}>
                <dt>
                  <span>{field.label}</span>
                  {field.required ? <small>required</small> : <small>optional</small>}
                </dt>
                <dd>
                  <code>{field.valuePreview ?? "not provided"}</code>
                  {field.description ? <p>{field.description}</p> : null}
                </dd>
              </div>
            ))}
          </dl>
        ) : (
          <div className="schema-approval-surface__loose">
            <p>No additional resume fields are declared by this schema.</p>
            <dl>
              {model.payloadPreview.map((entry) => (
                <div key={entry.key}>
                  <dt>{entry.key}</dt>
                  <dd><code>{entry.value}</code></dd>
                </div>
              ))}
            </dl>
          </div>
        )}
      </div>

      <footer className="schema-approval-surface__actions">
        {isResolved ? (
          <strong>Outcome: {state}</strong>
        ) : (
          <>
            <button type="button" onClick={onSubmit} disabled={!onSubmit}>
              Submit
            </button>
            <button type="button" onClick={onCancel} disabled={!onCancel}>
              Cancel
            </button>
          </>
        )}
        <span>{model.outcomes.join(" / ")}</span>
      </footer>
    </section>
  );
};
```

- [ ] **Step 4: Add minimal presentation CSS**

Append to `web/apps/console/src/presentation/styles/demo-workflow.css`:

```css
.schema-approval-surface {
  display: grid;
  gap: 0.75rem;
  min-width: 0;
  padding: 0.85rem;
  border: 1px solid color-mix(in oklch, var(--accent-amber) 48%, var(--stage-line));
  border-radius: 0.85rem;
  background:
    linear-gradient(135deg, color-mix(in oklch, var(--accent-amber) 16%, transparent), transparent 48%),
    var(--stage-surface);
  color: var(--text-primary);
}

.schema-approval-surface__header,
.schema-approval-surface__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.schema-approval-surface__header span,
.schema-approval-surface__actions span,
.schema-approval-surface__field small {
  color: var(--text-muted);
  font: 700 0.68rem/1 var(--font-mono);
}

.schema-approval-surface__header strong {
  font: 700 1rem/1.1 var(--font-display);
}

.schema-approval-surface__header code,
.schema-approval-surface__field code,
.schema-approval-surface__loose code {
  font: 600 0.72rem/1.35 var(--font-mono);
  color: var(--accent-cyan);
}

.schema-approval-surface__fields,
.schema-approval-surface__loose dl {
  display: grid;
  gap: 0.5rem;
  margin: 0;
}

.schema-approval-surface__field,
.schema-approval-surface__loose dl > div {
  display: grid;
  grid-template-columns: minmax(8rem, 0.55fr) minmax(0, 1fr);
  gap: 0.75rem;
  align-items: start;
  padding: 0.55rem;
  border: 1px solid color-mix(in oklch, var(--stage-line) 70%, transparent);
  border-radius: 0.6rem;
  background: color-mix(in oklch, var(--stage-inset) 82%, transparent);
}

.schema-approval-surface__field dt {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  margin: 0;
}

.schema-approval-surface__field dd,
.schema-approval-surface__loose dd {
  display: grid;
  gap: 0.3rem;
  margin: 0;
}

.schema-approval-surface__field p,
.schema-approval-surface__loose p {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.82rem;
}

.schema-approval-surface__actions button {
  border: 1px solid var(--stage-line);
  border-radius: 0.55rem;
  padding: 0.48rem 0.7rem;
  background: color-mix(in oklch, var(--stage-surface) 78%, var(--accent-cyan));
  color: var(--text-primary);
  font: 700 0.78rem/1 var(--font-mono);
}

.schema-approval-surface__actions button:disabled {
  opacity: 0.55;
}
```

- [ ] **Step 5: Run the component tests**

Run:

```bash
pnpm --filter @lda/console test -- src/presentation/approval
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/apps/console/src/presentation/approval web/apps/console/src/presentation/styles/demo-workflow.css
git commit -m "feat: add schema approval surface"
```

---

### Task 3: Wire Scene 10 Approval To Replay Payload

**Files:**
- Modify: `web/apps/console/src/presentation/demo-workflow-model.ts`
- Modify: `web/apps/console/src/presentation/InterruptContractPreview.tsx`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`

**Interfaces:**
- Consumes: `SchemaApprovalSurface`
- Produces: `InterruptContractPresentation` with request schema and resume payload.

- [ ] **Step 1: Write failing scene assertions**

Modify `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`:

```tsx
it("shows a schema approval surface for the approval beat instead of raw schema as the primary visual", () => {
  render(<DemoWorkflowScene beatId="approval" recording={recording} />);

  const approval = screen.getByRole("group", { name: /issue review resume/i });
  expect(within(approval).getByText("Schema-backed decision")).toBeInTheDocument();
  expect(within(approval).getByText("selected_issue_ids")).toBeInTheDocument();
  expect(within(approval).getByText("[\"risk-1\"]")).toBeInTheDocument();
  expect(within(approval).getByRole("button", { name: /submit/i })).toBeDisabled();
  expect(within(approval).getByRole("button", { name: /cancel/i })).toBeDisabled();
});

it("keeps raw resume schema visible only in interrupt preview mode", () => {
  const { rerender } = render(<DemoWorkflowScene beatId="interrupt" recording={recording} />);
  expect(screen.getByText("Resume schema")).toBeInTheDocument();

  rerender(<DemoWorkflowScene beatId="approval" recording={recording} />);
  expect(screen.queryByText("Resume schema")).not.toBeInTheDocument();
});
```

Make sure this test imports `within` from `@testing-library/react`.

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pnpm --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx
```

Expected: FAIL because approval mode still renders `InterruptContractPreview` with raw schema only.

- [ ] **Step 3: Extend the presentation contract**

Modify `web/apps/console/src/presentation/demo-workflow-model.ts`:

```ts
const InterruptProjectionSchema = v.looseObject({
  kind: v.string(),
  outcomes: v.optional(v.array(v.string())),
  request_schema: v.optional(v.unknown()),
  resume_schema: v.optional(v.unknown()),
});

const ResumeParamsSchema = v.looseObject({
  resume_payload: v.optional(v.unknown()),
  resume_outcome: v.optional(v.string()),
});
```

Update `InterruptContractPresentation`:

```ts
export type InterruptContractPresentation = {
  readonly kind: string;
  readonly outcomes: ReadonlyArray<string>;
  readonly requestSchema: unknown;
  readonly resumeSchema: unknown;
  readonly resumePayloadPreview: unknown;
  readonly resumeOutcome: string | null;
  readonly runId: string | null;
};
```

Update `projectInterruptContract`:

```ts
export const projectInterruptContract = (
  event: DemoEvent,
  resumeEvent?: DemoEvent | null,
): InterruptContractPresentation | null => {
  const interrupt = decodeInterpretation(event)?.interrupt;
  if (!interrupt || !interrupt.outcomes || interrupt.resume_schema === undefined) return null;
  const decodedResumeParams = v.safeParse(ResumeParamsSchema, resumeEvent?.params);
  const resumeParams = decodedResumeParams.success ? decodedResumeParams.output : null;
  return {
    kind: interrupt.kind,
    outcomes: interrupt.outcomes,
    requestSchema: interrupt.request_schema ?? null,
    resumeSchema: interrupt.resume_schema,
    resumePayloadPreview: resumeParams?.resume_payload ?? null,
    resumeOutcome: resumeParams?.resume_outcome ?? null,
    runId: event.resultingIds.runId,
  };
};
```

- [ ] **Step 4: Pass the resume event from the demo scene**

Modify `web/apps/console/src/presentation/DemoWorkflowScene.tsx`:

```ts
const runStart = recording.events.find((event) => event.stage === "run_start") ?? null;
const runResume = recording.events.find((event) => event.stage === "run_resume") ?? null;
const contract = runStart ? projectInterruptContract(runStart, runResume) : null;
```

- [ ] **Step 5: Render approval surface in approval mode**

Modify `web/apps/console/src/presentation/InterruptContractPreview.tsx`:

```tsx
import { SchemaApprovalSurface } from "./approval/SchemaApprovalSurface.js";
```

Inside the component body, before the raw schema block:

```tsx
{mode === "approval" ? (
  <SchemaApprovalSurface
    title={`${contract.kind} resume`}
    schema={contract.resumeSchema}
    payload={contract.resumePayloadPreview}
    outcomes={contract.outcomes}
    runId={contract.runId}
  />
) : (
  <div className="interrupt-contract-preview__schema">
    <span>Resume schema</span>
    <pre><code>{formatJson(contract.resumeSchema)}</code></pre>
  </div>
)}
```

Keep the header and persisted-run summary. The approval mode can show both the surrounding interrupt metadata and the approval surface, but not the raw schema block as the main visual.

- [ ] **Step 6: Run scene tests**

Run:

```bash
pnpm --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx src/presentation/InterruptContractPreview.test.tsx
```

If `InterruptContractPreview.test.tsx` does not exist, run only `DemoWorkflowScene.test.tsx`.

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add web/apps/console/src/presentation/demo-workflow-model.ts web/apps/console/src/presentation/InterruptContractPreview.tsx web/apps/console/src/presentation/DemoWorkflowScene.tsx web/apps/console/src/presentation/DemoWorkflowScene.test.tsx
git commit -m "feat: show schema approval in demo interrupt"
```

---

### Task 4: Attach Approval Data To Chat Approval Requests

**Files:**
- Modify: `web/apps/console/src/demo/agent/events.ts`
- Modify: `web/apps/console/src/demo/agent/events.test.ts`
- Modify: `web/apps/console/src/demo/agent/preparedRecipeDriver.ts`
- Modify: `web/apps/console/src/demo/agent/preparedRecipeDriver.test.ts`
- Modify: `web/apps/console/src/presentation/OperatorChat.tsx`
- Modify: `web/apps/console/src/presentation/OperatorChat.test.tsx`

**Interfaces:**
- Produces:

```ts
export type AgentApprovalContract = {
  readonly kind: string;
  readonly outcomes: ReadonlyArray<string>;
  readonly resumeSchema: unknown;
  readonly resumePayloadPreview: unknown;
  readonly runId: string | null;
};
```

Then:

```ts
| {
    readonly type: "approval-request";
    readonly callId: string;
    readonly name: AgentToolName;
    readonly prompt: string;
    readonly contract?: AgentApprovalContract | undefined;
  }
```

- Consumes: `SchemaApprovalSurface`.

- [ ] **Step 1: Add event tests for optional approval contract**

Modify `web/apps/console/src/demo/agent/events.test.ts`:

```ts
it("creates approval request parts with optional contract data", () => {
  const part = approvalRequestPart(
    "call-1",
    "resumeIssueReview",
    "Approve?",
    {
      kind: "issue_review",
      outcomes: ["submitted", "cancelled"],
      resumeSchema: { type: "object" },
      resumePayloadPreview: { selected_issue_ids: ["risk-1"] },
      runId: "run_recorded_lda_report",
    },
  );

  expect(part).toMatchObject({
    type: "approval-request",
    contract: {
      kind: "issue_review",
      runId: "run_recorded_lda_report",
    },
  });
});
```

- [ ] **Step 2: Update event types and constructor**

Modify `web/apps/console/src/demo/agent/events.ts`:

```ts
export type AgentApprovalContract = {
  readonly kind: string;
  readonly outcomes: ReadonlyArray<string>;
  readonly resumeSchema: unknown;
  readonly resumePayloadPreview: unknown;
  readonly runId: string | null;
};
```

Update the union member and constructor:

```ts
| {
    readonly type: "approval-request";
    readonly callId: string;
    readonly name: AgentToolName;
    readonly prompt: string;
    readonly contract?: AgentApprovalContract | undefined;
  }
```

```ts
export const approvalRequestPart = (
  callId: string,
  name: AgentToolName,
  prompt: string,
  contract?: AgentApprovalContract,
): AgentMessagePart => ({
  type: "approval-request",
  callId,
  name,
  prompt,
  contract,
});
```

- [ ] **Step 3: Attach replay-derived contract in prepared driver**

Modify `web/apps/console/src/demo/agent/preparedRecipeDriver.ts` near the `runStart` / `resume` lookup:

```ts
const interrupt = runStart?.interpreted && typeof runStart.interpreted === "object"
  && "interrupt" in runStart.interpreted
  ? runStart.interpreted.interrupt
  : null;
const resumePayload = resume?.params && typeof resume.params === "object" && "resume_payload" in resume.params
  ? resume.params.resume_payload
  : null;
```

Add a local helper if type-checking needs narrowing:

```ts
const approvalContract = isObject(interrupt) && Array.isArray(interrupt.outcomes)
  ? {
      kind: typeof interrupt.kind === "string" ? interrupt.kind : "issue_review",
      outcomes: interrupt.outcomes.filter((entry): entry is string => typeof entry === "string"),
      resumeSchema: "resume_schema" in interrupt ? interrupt.resume_schema : { type: "object" },
      resumePayloadPreview: resumePayload,
      runId,
    }
  : undefined;
```

Then update the approval request:

```ts
approvalRequestPart(
  callId,
  step.toolName,
  "Approve resuming the workflow run with the selected issues?",
  approvalContract,
),
```

Add a small `isObject` helper in this file if needed:

```ts
const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
```

- [ ] **Step 4: Add driver test assertion**

Modify `web/apps/console/src/demo/agent/preparedRecipeDriver.test.ts` in the approval-request test:

```ts
const approvalPart = messages
  .flatMap((message) => message.parts)
  .find((part) => part.type === "approval-request");
expect(approvalPart).toMatchObject({
  type: "approval-request",
  contract: {
    kind: "issue_review",
    runId: "run_recorded_lda_report",
  },
});
```

- [ ] **Step 5: Render schema approval inside chat**

Modify `web/apps/console/src/presentation/OperatorChat.tsx`:

```tsx
import { SchemaApprovalSurface } from "./approval/SchemaApprovalSurface.js";
```

Replace the approval-request branch with:

```tsx
case "approval-request":
  return (
    <div key={key} className="chat-tool-part chat-tool-part--approval">
      <span>Approval required</span>
      <code>{part.name}</code>
      <p>{part.prompt}</p>
      {part.contract ? (
        <SchemaApprovalSurface
          title={`${part.contract.kind} resume`}
          schema={part.contract.resumeSchema}
          payload={part.contract.resumePayloadPreview}
          outcomes={part.contract.outcomes}
          runId={part.contract.runId}
          onSubmit={onApprove}
          onCancel={onDeny}
        />
      ) : (
        <div className="chat-approval-actions">
          <button type="button" onClick={onApprove} disabled={!onApprove}>Approve</button>
          <button type="button" onClick={onDeny} disabled={!onDeny}>Deny</button>
        </div>
      )}
    </div>
  );
```

- [ ] **Step 6: Update chat tests**

Modify `web/apps/console/src/presentation/OperatorChat.test.tsx` approval test to include `contract` and expect submit/cancel:

```tsx
expect(screen.getByRole("group", { name: /issue review resume/i })).toBeInTheDocument();
fireEvent.click(screen.getByRole("button", { name: /submit/i }));
fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
expect(onApprove).toHaveBeenCalledTimes(1);
expect(onDeny).toHaveBeenCalledTimes(1);
```

Keep a fallback test for approval requests without `contract`, because live AI SDK drivers may not provide this immediately.

- [ ] **Step 7: Run focused agent/chat tests**

Run:

```bash
pnpm --filter @lda/console test -- src/demo/agent src/presentation/OperatorChat.test.tsx src/presentation/approval
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add web/apps/console/src/demo/agent web/apps/console/src/presentation/OperatorChat.tsx web/apps/console/src/presentation/OperatorChat.test.tsx web/apps/console/src/presentation/approval
git commit -m "feat: render schema approval in chat"
```

---

### Task 5: Verification, Roadmap, And Visual Smoke

**Files:**
- Modify: `docs/current_roadmap.md`
- Move after completion: `docs/superpowers/plans/2026-07-09-schema-approval-surface.md` -> `docs/historical/superpowers/plans/2026-07-09-schema-approval-surface.md`

**Interfaces:**
- Consumes all previous task outputs.
- Produces final documented slice status.

- [ ] **Step 1: Run presentation-focused tests**

Run:

```bash
pnpm --filter @lda/console test -- src/presentation src/demo/agent
```

Expected: PASS.

- [ ] **Step 2: Run broad web verification**

Run:

```bash
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
```

Expected:
- Tests pass.
- Typecheck clean.
- Build passes with only the known Vite chunk-size warning if it appears.

- [ ] **Step 3: Capture visual smoke screenshots**

With `pnpm dev` running, capture these routes at `1280x720`:

```text
http://127.0.0.1:5173/present#scene/interrupt-evidence/approval
http://127.0.0.1:5173/present#scene/interrupt-evidence/resume
http://127.0.0.1:5173/present#scene/workflow-demo/interrupt
```

Expected:
- Approval beat shows the schema approval surface and recorded resume payload.
- Interrupt beat still shows raw resume schema proof.
- Buttons are visible but disabled in Scene 10 unless the chat approval event owns handlers.

- [ ] **Step 4: Update roadmap**

In `docs/current_roadmap.md`:
- Change implementation order item 15 from future to completed.
- Add implementation link to `historical/superpowers/plans/2026-07-09-schema-approval-surface.md`.
- Keep chat surface replacement as a later item unless it was fully replaced; this slice only improves approval rendering inside existing chat.

Use wording like:

```md
15. Completed: schema approval surface for typed interrupt/resume decisions.
    Scene 10 and prepared-agent approval requests now render schema/payload
    approval UI instead of raw `{ "type": "object" }` as the primary product
    proof. Implementation:
    [`schema approval surface`](historical/superpowers/plans/2026-07-09-schema-approval-surface.md).
```

- [ ] **Step 5: Archive the plan**

Run:

```bash
git mv docs/superpowers/plans/2026-07-09-schema-approval-surface.md docs/historical/superpowers/plans/2026-07-09-schema-approval-surface.md
```

- [ ] **Step 6: Commit**

```bash
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-09-schema-approval-surface.md
git commit -m "docs: complete schema approval surface"
```

---

## Self-Review Checklist

- [ ] No task asks the worker to implement JSON Schema validation in React.
- [ ] Scene 10 approval no longer makes raw `{ "type": "object" }` the primary visual.
- [ ] Loose-schema fallback uses actual recorded resume payload and has a code comment explaining why.
- [ ] Chat approval request still works without contract data.
- [ ] The component has explicit submit/cancel labels, but workflow outcome copy remains submitted/cancelled.
- [ ] Tests cover projection, component rendering, Scene 10 integration, and chat integration.
- [ ] Roadmap points to `historical/**` after completion.
