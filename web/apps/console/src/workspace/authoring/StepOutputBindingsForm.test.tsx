import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import type { AuthoringPathOption } from "../domain/authoring-contract-models.js";
import type { DraftDiagnostic, OutputBinding } from "../domain/draft-workspace-models.js";
import { StepOutputBindingsForm } from "./StepOutputBindingsForm.js";

afterEach(() => cleanup());

const outputSchema = {
  type: "object",
  properties: {
    text: { type: "string" },
    audit: {
      type: "object",
      properties: { latest: { type: "integer" } },
    },
  },
};

const stateSchema = {
  type: "object",
  properties: {
    existing: { type: "string" },
  },
};

const authoringOption = (
  path: string,
  label: string,
  origin: AuthoringPathOption["origin"],
  uses: AuthoringPathOption["uses"],
): AuthoringPathOption => ({
  path,
  label,
  origin,
  schema: { type: "string" },
  required: false,
  availability: "available",
  uses,
});

type FormUser = ReturnType<typeof userEvent.setup>;
type ClearMutationCase = {
  readonly name: string;
  readonly mutate: (user: FormUser) => Promise<void>;
  readonly expected: ReadonlyArray<OutputBinding>;
};

const customInput = (label: string) =>
  within(screen.getByRole("region", { name: label }))
    .getByRole("textbox", { name: `Custom ${label}` });

const editableCustomInput = async (user: FormUser, label: string) => {
  const picker = screen.getByRole("region", { name: label });
  const details = picker.querySelector("details");
  if (!(details instanceof HTMLDetailsElement) || !details.open) {
    await user.click(within(picker).getByText("Advanced"));
  }
  return within(picker).getByRole("textbox", { name: `Custom ${label}` });
};

const clearMutationCases: ReadonlyArray<ClearMutationCase> = [
  {
    name: "add",
    mutate: async (user) => {
      await user.click(screen.getByRole("button", { name: "Add output row" }));
      await user.type(
        await editableCustomInput(user, "Target for output row 3"),
        "state.third",
      );
    },
    expected: [
      { source: "text", target: "state.first" },
      { source: "audit.latest", target: "state.second" },
      { source: ".", target: "state.third" },
    ],
  },
  {
    name: "edit",
    mutate: async (user) => {
      const target = await editableCustomInput(user, "Target for output row 1");
      await user.clear(target);
      await user.type(target, "state.edited");
    },
    expected: [
      { source: "text", target: "state.edited" },
      { source: "audit.latest", target: "state.second" },
    ],
  },
  {
    name: "remove",
    mutate: async (user) => {
      await user.click(screen.getByRole("button", { name: "Remove output row 2" }));
    },
    expected: [{ source: "text", target: "state.first" }],
  },
];

describe("StepOutputBindingsForm", () => {
  it("uses inventory step-output and state-target pickers while preserving local output bindings", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<OutputBinding>[] = [];
    render(
      <StepOutputBindingsForm
        outputSchema={{ type: "object", properties: { text: { type: "string" } } }}
        stateSchema={stateSchema}
        sourceOptions={[authoringOption("step_output.text", "Text output", "step_output", ["step_output_source"])]}
        targetOptions={[authoringOption("state.existing", "Existing state", "workflow_state", ["state_target"])]}
        initialBindings={[{ source: "text", target: "state.existing" }]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    expect(screen.getByRole("group", { name: "Step output" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "State" })).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Source choice for output row 1" })).toBeNull();

    await user.click(screen.getByRole("button", { name: /Text output/ }));
    await user.click(screen.getByRole("button", { name: /Existing state/ }));
    await user.click(screen.getByRole("button", { name: "Save outputs" }));

    expect(submissions).toEqual([[{ source: "text", target: "state.existing" }]]);
  });

  it("preserves a custom source that collides with the canonical step-output namespace", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<OutputBinding>[] = [];
    render(
      <StepOutputBindingsForm
        outputSchema={outputSchema}
        stateSchema={stateSchema}
        sourceOptions={[authoringOption("step_output.text", "Text output", "step_output", ["step_output_source"])]}
        targetOptions={[authoringOption("state.existing", "Existing state", "workflow_state", ["state_target"])]}
        initialBindings={[{ source: "step_output.text", target: "state.existing" }]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    const source = await editableCustomInput(user, "Source path for output row 1");
    await user.clear(source);
    await user.type(source, "step_output.text");
    await user.click(screen.getByRole("button", { name: "Save outputs" }));

    expect(submissions).toEqual([[{ source: "step_output.text", target: "state.existing" }]]);
  });

  it("offers capability output sources and existing state targets", () => {
    render(
      <StepOutputBindingsForm
        outputSchema={outputSchema}
        stateSchema={stateSchema}
        sourceOptions={[
          authoringOption("step_output.text", "Text", "step_output", ["step_output_source"]),
          authoringOption("step_output.audit.latest", "Latest audit", "step_output", ["step_output_source"]),
        ]}
        targetOptions={[authoringOption("state.existing", "Existing state", "workflow_state", ["state_target"])]}
        initialBindings={[{ source: "text", target: "state.existing" }]}
        onSubmit={() => undefined}
      />,
    );

    expect(screen.getByRole("button", { name: /Text/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Latest audit/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Existing state/ })).toBeInTheDocument();
  });

  it("submits a nested state target and shows the selected source schema preview", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<OutputBinding>[] = [];
    render(
      <StepOutputBindingsForm
        outputSchema={outputSchema}
        stateSchema={stateSchema}
        initialBindings={[{ source: "audit.latest", target: "state.report.markdown" }]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    expect(customInput("Target for output row 1")).toHaveValue("state.report.markdown");
    expect(screen.getByRole("region", { name: "Inferred schema for output row 1" }))
      .toHaveTextContent('"type": "integer"');

    await user.click(screen.getByRole("button", { name: "Save outputs" }));

    expect(submissions).toEqual([[{ source: "audit.latest", target: "state.report.markdown" }]]);
  });

  it("keeps a repeated source fan-out in exact moved order and removes rows explicitly", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<OutputBinding>[] = [];
    render(
      <StepOutputBindingsForm
        outputSchema={outputSchema}
        stateSchema={stateSchema}
        initialBindings={[
          { source: "text", target: "state.first" },
          { source: "text", target: "state.second" },
        ]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Move output row 1 down" }));
    await user.click(screen.getByRole("button", { name: "Remove output row 2" }));
    await user.click(screen.getByRole("button", { name: "Save outputs" }));

    expect(submissions).toEqual([[{ source: "text", target: "state.second" }]]);
  });

  it("preserves a valid custom local source path outside the suggestions", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<OutputBinding>[] = [];
    render(
      <StepOutputBindingsForm
        outputSchema={{ type: "object", properties: {} }}
        stateSchema={stateSchema}
        initialBindings={[{ source: "nested.whole", target: "state.report" }]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    expect(customInput("Source path for output row 1")).toHaveValue("nested.whole");

    await user.click(screen.getByRole("button", { name: "Save outputs" }));

    expect(submissions).toEqual([[{ source: "nested.whole", target: "state.report" }]]);
  });

  it("round-trips structural and whole local sources in ordered submissions", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<OutputBinding>[] = [];
    render(
      <StepOutputBindingsForm
        outputSchema={outputSchema}
        stateSchema={stateSchema}
        initialBindings={[
          {
            source: { root: "local", parts: ["payload", "item"] },
            target: { root: "state", parts: ["report", "markdown"] },
          },
          {
            source: { root: "local", parts: [] },
            target: "state.existing",
          },
        ]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    expect(customInput("Source path for output row 1")).toHaveValue("payload.item");
    expect(customInput("Source path for output row 2")).toHaveValue(".");

    await user.click(screen.getByRole("button", { name: "Save outputs" }));

    expect(submissions).toEqual([[
      { source: "payload.item", target: "state.report.markdown" },
      { source: ".", target: "state.existing" },
    ]]);
  });

  it("adds a whole-output row that can be completed and submitted", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<OutputBinding>[] = [];
    render(
      <StepOutputBindingsForm
        outputSchema={outputSchema}
        stateSchema={stateSchema}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Add output row" }));
    expect(customInput("Source path for output row 1")).toHaveValue(".");
    await user.type(await editableCustomInput(user, "Target for output row 1"), "state.new");
    await user.click(screen.getByRole("button", { name: "Save outputs" }));

    expect(submissions).toEqual([[{ source: ".", target: "state.new" }]]);
  });

  it("allows a real __custom__ schema source instead of treating it as the custom escape hatch", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<OutputBinding>[] = [];
    render(
      <StepOutputBindingsForm
        outputSchema={{
          type: "object",
          properties: { __custom__: { type: "string" }, text: { type: "string" } },
        }}
        stateSchema={stateSchema}
        sourceOptions={[
          authoringOption("step_output.__custom__", "__custom__", "step_output", ["step_output_source"]),
          authoringOption("step_output.text", "Text", "step_output", ["step_output_source"]),
        ]}
        targetOptions={[authoringOption("state.existing", "Existing state", "workflow_state", ["state_target"])]}
        initialBindings={[{ source: "text", target: "state.existing" }]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    await user.click(screen.getByRole("button", { name: /__custom__/ }));
    await user.click(screen.getByRole("button", { name: "Save outputs" }));

    expect(submissions).toEqual([[{ source: "__custom__", target: "state.existing" }]]);
  });

  it("requires explicit confirmation before clearing the ordered binding list", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<OutputBinding>[] = [];
    render(
      <StepOutputBindingsForm
        outputSchema={outputSchema}
        stateSchema={stateSchema}
        initialBindings={[{ source: "text", target: "state.existing" }]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    expect(screen.getByText(
      "Saving a new target asks the workflow API to project this output schema into state. Clearing bindings does not delete existing state fields.",
    )).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear outputs" }));
    expect(submissions).toEqual([]);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Saving a new target asks the workflow API to project this output schema into state. Clearing bindings does not delete existing state fields.",
    );
    expect(screen.getByRole("button", { name: "Confirm clear outputs" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Confirm clear outputs" }));
    expect(submissions).toEqual([[]]);
  });

  it("cancels pending clear confirmation before saving reordered bindings", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<OutputBinding>[] = [];
    render(
      <StepOutputBindingsForm
        outputSchema={outputSchema}
        stateSchema={stateSchema}
        initialBindings={[
          { source: "text", target: "state.first" },
          { source: "audit.latest", target: "state.second" },
        ]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Clear outputs" }));
    await user.click(screen.getByRole("button", { name: "Move output row 1 down" }));
    await user.click(screen.getByRole("button", { name: "Save outputs" }));

    expect(submissions).toEqual([[
      { source: "audit.latest", target: "state.second" },
      { source: "text", target: "state.first" },
    ]]);
    expect(screen.queryByRole("button", { name: "Confirm clear outputs" })).not.toBeInTheDocument();
  });

  it("requires fresh confirmation when saving after removing the last stored row", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<OutputBinding>[] = [];
    render(
      <StepOutputBindingsForm
        outputSchema={outputSchema}
        stateSchema={stateSchema}
        initialBindings={[{ source: "text", target: "state.existing" }]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Remove output row 1" }));
    await user.click(screen.getByRole("button", { name: "Save outputs" }));

    expect(submissions).toEqual([]);
    expect(screen.getByRole("button", { name: "Confirm clear outputs" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirm clear outputs" }));
    expect(submissions).toEqual([[]]);
  });

  it.each(clearMutationCases)(
    "cancels pending clear confirmation after $name and preserves the mutated rows",
    async ({ mutate, expected }) => {
      const user = userEvent.setup();
      const submissions: ReadonlyArray<OutputBinding>[] = [];
      render(
        <StepOutputBindingsForm
          outputSchema={outputSchema}
          stateSchema={stateSchema}
          initialBindings={[
            { source: "text", target: "state.first" },
            { source: "audit.latest", target: "state.second" },
          ]}
          onSubmit={(value) => { submissions.push(value); }}
        />,
      );

      await user.click(screen.getByRole("button", { name: "Clear outputs" }));
      await mutate(user);
      expect(screen.queryByRole("button", { name: "Confirm clear outputs" })).not.toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "Save outputs" }));

      expect(submissions).toEqual([expected]);
      await user.click(screen.getByRole("button", { name: "Clear outputs" }));
      expect(screen.getByRole("button", { name: "Confirm clear outputs" })).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Confirm clear outputs" }));

      expect(submissions).toEqual([expected, []]);
      expect(screen.getByText("No output bindings configured.")).toBeInTheDocument();
    },
  );

  it("blocks saving while a malformed stored row remains visible for repair", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<OutputBinding>[] = [];
    render(
      <StepOutputBindingsForm
        outputSchema={outputSchema}
        stateSchema={stateSchema}
        initialRows={[
          { kind: "canonical", index: 0, value: { source: "text", target: "state.existing" } },
          {
            kind: "unsupported",
            field: "output",
            index: 1,
            raw: { source: "broken", target: "state" },
            reason: "Unsupported output binding.",
          },
        ]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Save outputs" }));

    expect(submissions).toEqual([]);
    expect(screen.getAllByRole("alert").some((alert) =>
      alert.textContent?.includes("Remove or repair every unsupported output row before saving.") ?? false,
    )).toBe(true);
    expect(screen.getByRole("region", { name: "Raw unsupported output row 2" }))
      .toHaveTextContent('"source"');
  });

  it("blocks clear until every unsupported output row is explicitly removed", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<OutputBinding>[] = [];
    render(
      <StepOutputBindingsForm
        outputSchema={outputSchema}
        stateSchema={stateSchema}
        initialRows={[{
          kind: "unsupported",
          field: "output",
          index: 0,
          raw: { source: "broken", target: "state" },
          reason: "Unsupported output binding.",
        }]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Clear outputs" }));

    expect(submissions).toEqual([]);
    expect(screen.queryByRole("button", { name: "Confirm clear outputs" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("alert").some((alert) =>
      alert.textContent?.includes("Remove or repair this unsupported output row before clearing outputs.") ?? false,
    )).toBe(true);
  });

  it("keeps backend diagnostics attached to their output row", () => {
    const diagnostic: DraftDiagnostic = {
      code: "invalid_target",
      path: "bindings[4].target",
      message: "Target field is not declared.",
      stepId: "render",
      repairHint: null,
      details: {},
    };
    render(
      <StepOutputBindingsForm
        outputSchema={outputSchema}
        stateSchema={stateSchema}
        initialRows={[{ kind: "canonical", index: 4, value: { source: "text", target: "state.existing" } }]}
        rowDiagnostics={{ 4: [diagnostic] }}
        onSubmit={() => undefined}
      />,
    );

    const target = customInput("Target for output row 1");
    const describedBy = target.getAttribute("aria-describedby");
    expect(describedBy).not.toBeNull();
    expect(target).toHaveAttribute("aria-invalid", "true");
    expect(document.getElementById(describedBy ?? "")).toHaveTextContent("Target field is not declared.");
  });
});
