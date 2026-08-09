import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import type { InputBinding } from "../domain/draft-workspace-models.js";
import { StepInputBindingsForm } from "./StepInputBindingsForm.js";

afterEach(() => cleanup());

const schema = {
  type: "object",
  properties: {
    title: { type: "string" },
    nullable: { enum: [null, "ready"] },
    nested: {
      type: "object",
      properties: { name: { type: "string" } },
    },
  },
};

describe("StepInputBindingsForm", () => {
  it("renders ordered path, null literal, nested, and unsupported rows with repair controls", () => {
    render(
      <StepInputBindingsForm
        inputSchema={schema}
        initialRows={[
          { kind: "canonical", index: 0, value: { path: "input.title", target: "title" } },
          { kind: "canonical", index: 1, value: { target: "nullable", value: null } },
          { kind: "canonical", index: 2, value: { path: "context.profile.name", target: "nested.name" } },
          { kind: "unsupported", field: "input", index: 3, raw: { target: "broken" }, reason: "Unsupported input binding." },
        ]}
        onSubmit={() => undefined}
      />,
    );

    expect(screen.getByRole("group", { name: "Input row 1" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Target for row 1" })).toHaveValue("title");
    expect(screen.getAllByRole("radio", { name: "Bind" })[0]).toBeChecked();
    expect(screen.getByRole("textbox", { name: "Source path for Title" })).toHaveValue("input.title");
    expect(screen.getByRole("combobox", { name: "Nullable" })).toHaveValue("0:null");
    expect(screen.getByRole("textbox", { name: "Target for row 3" })).toHaveValue("nested.name");
    expect(screen.getByText("Unsupported input binding.")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Raw unsupported input row 4" })).toHaveTextContent('"target"');
    expect(screen.getByRole("button", { name: "Remove unsupported input row 4" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Move input row 1 down" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Move input row 2 up" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove input row 3" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add input row" })).toBeInTheDocument();
  });

  it("submits canonical rows in exact reordered order and preserves fan-out", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<InputBinding>[] = [];
    render(
      <StepInputBindingsForm
        inputSchema={schema}
        initialRows={[
          { kind: "canonical", index: 0, value: { path: "input.title", target: "first" } },
          { kind: "canonical", index: 1, value: { path: "input.title", target: "second" } },
        ]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Move input row 1 down" }));
    await user.click(screen.getByRole("button", { name: "Save inputs" }));

    expect(submissions[0]).toEqual([
      { path: "input.title", target: "second" },
      { path: "input.title", target: "first" },
    ]);
  });

  it("supports explicit clear and removes unsupported rows before saving", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<InputBinding>[] = [];
    render(
      <StepInputBindingsForm
        inputSchema={schema}
        initialRows={[
          { kind: "canonical", index: 0, value: { path: "input.title", target: "title" } },
          { kind: "unsupported", field: "input", index: 1, raw: { target: "broken" }, reason: "Unsupported input binding." },
        ]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Remove unsupported input row 2" }));
    await user.click(screen.getByRole("button", { name: "Clear inputs" }));

    expect(submissions).toEqual([[]]);
  });

  it("shows row diagnostics at the row that owns them", () => {
    render(
      <StepInputBindingsForm
        inputSchema={schema}
        initialRows={[{ kind: "canonical", index: 4, value: { path: "input.title", target: "title" } }]}
        onSubmit={() => undefined}
        rowDiagnostics={{
          4: [{ code: "invalid", path: "bindings[4].target", message: "Target does not exist.", stepId: "step", repairHint: null, details: {} }],
        }}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Target does not exist.");
  });
});
