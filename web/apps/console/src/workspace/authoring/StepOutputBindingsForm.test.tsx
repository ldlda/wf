import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
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

describe("StepOutputBindingsForm", () => {
  it("offers capability output sources and existing state targets", () => {
    render(
      <StepOutputBindingsForm
        outputSchema={outputSchema}
        stateSchema={stateSchema}
        initialBindings={[{ source: "text", target: "state.existing" }]}
        onSubmit={() => undefined}
      />,
    );

    const source = screen.getByRole("combobox", { name: "Source choice for output row 1" });
    expect(within(source).getByRole("option", { name: "Whole output (.)" })).toBeInTheDocument();
    expect(within(source).getByRole("option", { name: "text" })).toBeInTheDocument();
    expect(within(source).getByRole("option", { name: "audit.latest" })).toBeInTheDocument();

    const target = screen.getByRole("combobox", { name: "Target for output row 1" });
    expect(target).toHaveValue("state.existing");
    const targetList = target.getAttribute("list");
    expect(targetList).toBeTruthy();
    const targetListElement = document.getElementById(targetList ?? "");
    expect(targetListElement).not.toBeNull();
    if (targetListElement !== null) {
      expect(targetListElement.querySelector('option[value="state.existing"]')).not.toBeNull();
    }
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

    expect(screen.getByRole("combobox", { name: "Target for output row 1" })).toHaveValue(
      "state.report.markdown",
    );
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

    expect(screen.getByRole("combobox", { name: "Source choice for output row 1" }))
      .toHaveValue("__custom__");
    expect(screen.getByRole("textbox", { name: "Local source path for output row 1" }))
      .toHaveValue("nested.whole");

    await user.click(screen.getByRole("button", { name: "Save outputs" }));

    expect(submissions).toEqual([[{ source: "nested.whole", target: "state.report" }]]);
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

    const target = screen.getByRole("combobox", { name: "Target for output row 1" });
    const describedBy = target.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    expect(document.getElementById(describedBy ?? "")).toHaveTextContent("Target field is not declared.");
  });
});
