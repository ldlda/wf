import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { InputBinding } from "../domain/draft-workspace-models.js";
import { StepInputBindingsForm } from "./StepInputBindingsForm.js";
import { displayGraphInputPath, displayLocalInputPath } from "./input-binding-paths.js";

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
  it("formats local and graph path objects at whole and nested paths", () => {
    expect(displayLocalInputPath({ root: "local", parts: [] })).toBe(".");
    expect(displayLocalInputPath({ root: "local", parts: ["payload", "item"] })).toBe("payload.item");
    expect(displayGraphInputPath({ root: "input", parts: ["payload", "item"] })).toBe("input.payload.item");
    expect(displayGraphInputPath({ root: "state", parts: [] })).toBe("state");
  });

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
    expect(screen.getByRole("combobox", { name: "Target for row 1" })).toHaveValue("title");
    expect(screen.getByRole("radio", { name: "Path for input row 1" })).toBeChecked();
    expect(screen.getByRole("combobox", { name: "Source path for input row 1" })).toHaveValue("input.title");
    expect(screen.getByRole("combobox", { name: "Nullable" })).toHaveValue("0:null");
    expect(screen.getByRole("combobox", { name: "Target for row 3" })).toHaveValue("nested.name");
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
    expect(screen.queryByRole("group", { name: "Input row 1" })).toBeNull();
  });

  it("keeps input rows when clearing fails", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockRejectedValue(new Error("clear failed"));
    render(
      <StepInputBindingsForm
        inputSchema={schema}
        initialRows={[
          { kind: "canonical", index: 0, value: { path: "input.title", target: "title" } },
        ]}
        onSubmit={onSubmit}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Clear inputs" }));

    expect(onSubmit).toHaveBeenCalledWith([]);
    expect(screen.getByRole("group", { name: "Input row 1" })).toBeInTheDocument();
  });

  it("blocks clear until every unsupported row is explicitly removed", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<InputBinding>[] = [];
    render(
      <StepInputBindingsForm
        inputSchema={schema}
        initialRows={[{
          kind: "unsupported",
          field: "input",
          index: 0,
          raw: { target: "broken" },
          reason: "Unsupported input binding.",
        }]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    const clear = screen.getByRole("button", { name: "Clear inputs" });
    await user.click(clear);

    expect(submissions).toEqual([]);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Remove or repair this unsupported input row before clearing inputs.",
    );
    expect(clear.getAttribute("aria-describedby")).toBe(screen.getByRole("alert").id);

    await user.click(screen.getByRole("button", { name: "Remove unsupported input row 1" }));
    await user.click(clear);
    expect(submissions).toEqual([[]]);
  });

  it("round-trips whole and nested local paths without adding the local root", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<InputBinding>[] = [];
    render(
      <StepInputBindingsForm
        inputSchema={schema}
        initialRows={[
          {
            kind: "canonical",
            index: 0,
            value: {
              target: { root: "local", parts: ["payload", "item"] },
              path: { root: "input", parts: ["source"] },
            },
          },
          {
            kind: "canonical",
            index: 1,
            value: {
              target: { root: "local", parts: [] },
              path: { root: "state", parts: ["audit", "latest"] },
            },
          },
        ]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    expect(screen.getByRole("combobox", { name: "Target for row 1" })).toHaveValue("payload.item");
    expect(screen.getByRole("combobox", { name: "Target for row 2" })).toHaveValue(".");
    expect(screen.getByRole("combobox", { name: "Source path for input row 1" })).toHaveValue("input.source");
    expect(screen.getByRole("combobox", { name: "Source path for input row 2" })).toHaveValue("state.audit.latest");

    await user.click(screen.getByRole("button", { name: "Save inputs" }));

    expect(submissions).toEqual([[
      { target: "payload.item", path: "input.source" },
      { target: ".", path: "state.audit.latest" },
    ]]);
  });

  it("uses explicit row modes and immutably edits a whole object literal", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<InputBinding>[] = [];
    render(
      <StepInputBindingsForm
        inputSchema={{
          type: "object",
          properties: {
            nested: {
              type: "object",
              properties: { name: { type: "string" }, count: { type: "integer" } },
            },
          },
        }}
        initialRows={[{
          kind: "canonical",
          index: 0,
          value: { target: "nested", value: { name: "before", count: 2 } },
        }]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    expect(screen.getByRole("radio", { name: "Literal value for input row 1" })).toBeChecked();
    await user.clear(screen.getByRole("textbox", { name: "Name" }));
    await user.type(screen.getByRole("textbox", { name: "Name" }), "after");
    await user.click(screen.getByRole("radio", { name: "Path for input row 1" }));
    await user.clear(screen.getByRole("combobox", { name: "Source path for input row 1" }));
    await user.type(screen.getByRole("combobox", { name: "Source path for input row 1" }), "input.nested");
    await user.click(screen.getByRole("radio", { name: "Literal value for input row 1" }));
    await user.click(screen.getByRole("button", { name: "Save inputs" }));

    expect(submissions).toEqual([[{ target: "nested", value: { name: "after", count: 2 } }]]);
  });

  it("preserves array shape while editing a whole array literal", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<InputBinding>[] = [];
    render(
      <StepInputBindingsForm
        inputSchema={{ type: "object", properties: { items: { type: "array", items: { type: "string" } } } }}
        initialRows={[{
          kind: "canonical",
          index: 0,
          value: { target: "items", value: ["first", "second"] },
        }]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    await user.clear(screen.getByRole("textbox", { name: "Item 1" }));
    await user.type(screen.getByRole("textbox", { name: "Item 1" }), "updated");
    await user.click(screen.getByRole("button", { name: "Save inputs" }));

    expect(submissions).toEqual([[{ target: "items", value: ["updated", "second"] }]]);
  });

  it("associates local row errors with the target control", async () => {
    const user = userEvent.setup();
    render(
      <StepInputBindingsForm
        inputSchema={schema}
        initialRows={[{ kind: "canonical", index: 0, value: { path: "input.title", target: "title" } }]}
        onSubmit={() => undefined}
      />,
    );

    await user.clear(screen.getByRole("combobox", { name: "Target for row 1" }));
    await user.click(screen.getByRole("button", { name: "Save inputs" }));

    const target = screen.getByRole("combobox", { name: "Target for row 1" });
    const describedBy = target.getAttribute("aria-describedby");
    expect(target).toHaveAttribute("aria-invalid", "true");
    expect(describedBy).toBeTruthy();
    expect(document.getElementById(describedBy ?? "")).toHaveTextContent("Target is required.");
  });

  it("offers workflow source and nested capability target choices while retaining text entry", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<InputBinding>[] = [];
    render(
      <StepInputBindingsForm
        inputSchema={{
          type: "object",
          properties: { profile: { type: "object", properties: { name: { type: "string" } } } },
        }}
        workflowInputSchema={{
          type: "object",
          properties: { request: { type: "object", properties: { id: { type: "string" } } } },
        }}
        workflowStateSchema={{
          type: "object",
          properties: { session: { type: "object", properties: { token: { type: "string" } } } },
        }}
        initialBindings={[{ path: "input.request.id", target: "profile.name" }]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    const target = screen.getByRole("combobox", { name: "Target for row 1" });
    const targetList = document.getElementById(target.getAttribute("list") ?? "");
    expect(target.getAttribute("list")).toBeTruthy();
    expect(targetList).not.toBeNull();
    expect(targetList?.querySelector('option[value="profile.name"]')).not.toBeNull();
    const source = screen.getByRole("combobox", { name: "Source path for input row 1" });
    const sourceList = document.getElementById(source.getAttribute("list") ?? "");
    expect(source.getAttribute("list")).toBeTruthy();
    expect(sourceList).not.toBeNull();
    expect(sourceList?.querySelector('option[value="input.request.id"]')).not.toBeNull();
    expect(sourceList?.querySelector('option[value="state.session.token"]')).not.toBeNull();

    await user.clear(target);
    await user.type(target, "profile.custom");
    await user.clear(source);
    await user.type(source, "context.custom");
    await user.click(screen.getByRole("button", { name: "Save inputs" }));

    expect(submissions).toEqual([[{ path: "context.custom", target: "profile.custom" }]]);
  });

  it("rejects exact duplicate targets across path and literal rows with errors on both rows", async () => {
    const user = userEvent.setup();
    const submissions: ReadonlyArray<InputBinding>[] = [];
    render(
      <StepInputBindingsForm
        inputSchema={schema}
        initialRows={[
          { kind: "canonical", index: 0, value: { path: "input.title", target: "title" } },
          { kind: "canonical", index: 1, value: { target: "other", value: "literal" } },
        ]}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    await user.clear(screen.getByRole("combobox", { name: "Target for row 2" }));
    await user.type(screen.getByRole("combobox", { name: "Target for row 2" }), "title");
    await user.click(screen.getByRole("button", { name: "Save inputs" }));

    expect(submissions).toEqual([]);
    expect(screen.getByRole("combobox", { name: "Target for row 1" })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("combobox", { name: "Target for row 2" })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getAllByRole("alert").filter((alert) =>
      alert.textContent?.includes("Target is duplicated") ?? false,
    )).toHaveLength(2);
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
