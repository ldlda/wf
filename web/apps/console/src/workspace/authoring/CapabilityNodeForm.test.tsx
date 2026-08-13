import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { CapabilityNodeForm, type CapabilityNodeFormValue } from "./CapabilityNodeForm.js";

afterEach(() => cleanup());

describe("CapabilityNodeForm", () => {
  it("accepts expression bindings in its callback value without authoring them", () => {
    const value = {
      stepId: "concat",
      capabilityName: "wf.std.concat",
      inputBindings: [
        {
          target: "request",
          expression: {
            kind: "array",
            items: [
              { kind: "path", path: "state.foo" },
              { kind: "literal", value: "wowcool" },
            ],
          },
        },
      ],
    } satisfies CapabilityNodeFormValue;

    expect(value.inputBindings).toHaveLength(1);
    expect(value.inputBindings[0]).toHaveProperty("expression.kind", "array");
  });

  it("preserves rehydrated expression bindings when the legacy form is submitted", async () => {
    const user = userEvent.setup();
    const submissions: CapabilityNodeFormValue[] = [];
    const expressionBinding = {
      target: "request",
      expression: {
        kind: "array",
        items: [
          { kind: "path", path: "state.foo" },
          { kind: "literal", value: "wowcool" },
        ],
      },
    } as const;

    render(
      <CapabilityNodeForm
        capabilityName="wf.std.concat"
        initialValue={{ stepId: "concat", inputBindings: [expressionBinding] }}
        inputSchema={{ type: "object", properties: {} }}
        onSubmit={(value) => { submissions.push(value); }}
        submitLabel="Save node"
      />,
    );

    await user.click(screen.getByRole("button", { name: "Save node" }));

    expect(submissions).toHaveLength(1);
    expect(
      submissions[0]?.inputBindings?.filter((binding) => "expression" in binding),
    ).toEqual([expressionBinding]);
  });

  it("submits explicit node metadata and serialized schema bindings", async () => {
    const user = userEvent.setup();
    const submissions: unknown[] = [];
    render(
      <CapabilityNodeForm
        capabilityName="demo.enrich"
        inputSchema={{
          type: "object",
          properties: { title: { type: "string" } },
        }}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    await user.type(screen.getByRole("textbox", { name: "Step id" }), "enrich");
    await user.type(screen.getByRole("textbox", { name: "Description" }), "Enrich report");
    await user.type(screen.getByRole("textbox", { name: "Title" }), "Quarterly report");
    expect(screen.getByRole("spinbutton", { name: "Timeout seconds" })).toHaveAttribute("inputmode", "numeric");
    await user.click(screen.getByRole("button", { name: "Add node" }));

    expect(submissions[0]).toMatchObject({
      stepId: "enrich",
      capabilityName: "demo.enrich",
      description: "Enrich report",
      inputBindings: [{ target: "title", value: "Quarterly report" }],
    });
    expect(submissions[0]).not.toHaveProperty("retry");
    expect(submissions[0]).not.toHaveProperty("timeoutSeconds");
  });

  it("preserves an explicit zero retry while omitting untouched blank metadata", async () => {
    const user = userEvent.setup();
    const submissions: unknown[] = [];
    render(
      <CapabilityNodeForm
        capabilityName="demo.enrich"
        inputSchema={{ type: "object", properties: {} }}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    await user.type(screen.getByRole("textbox", { name: "Step id" }), "enrich");
    await user.type(screen.getByRole("spinbutton", { name: "Retry" }), "0");
    await user.click(screen.getByRole("button", { name: "Add node" }));

    expect(submissions[0]).toHaveProperty("retry", 0);
    expect(submissions[0]).not.toHaveProperty("timeoutSeconds");
    expect(submissions[0]).not.toHaveProperty("description");
  });

  it("requires timeout seconds to be a positive whole number", async () => {
    const user = userEvent.setup();
    const submissions: unknown[] = [];
    render(
      <CapabilityNodeForm
        capabilityName="demo.enrich"
        inputSchema={{ type: "object", properties: {} }}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    await user.type(screen.getByRole("textbox", { name: "Step id" }), "enrich");
    const timeout = screen.getByRole("spinbutton", { name: "Timeout seconds" });
    expect(timeout).toHaveAttribute("min", "1");
    expect(timeout).toHaveAttribute("step", "1");
    await user.type(timeout, "1.5");
    await user.click(screen.getByRole("button", { name: "Add node" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Timeout must be a whole number greater than 0.",
    );
    expect(submissions).toHaveLength(0);
  });

  it("reports local edits as dirty and keeps them when submission fails", async () => {
    const user = userEvent.setup();
    const dirtyStates: boolean[] = [];
    render(
      <CapabilityNodeForm
        capabilityName="demo.enrich"
        inputSchema={{ type: "object", properties: {} }}
        onDirtyChange={(dirty) => dirtyStates.push(dirty)}
        onSubmit={() => { throw new Error("not sent"); }}
      />,
    );

    const stepId = screen.getByRole("textbox", { name: "Step id" });
    await user.type(stepId, "enrich");
    expect(dirtyStates.at(-1)).toBe(true);
    expect(stepId).toHaveValue("enrich");
  });

  it("submits an explicit target for every declared capability outcome", async () => {
    const user = userEvent.setup();
    const submissions: unknown[] = [];
    render(
      <CapabilityNodeForm
        capabilityName="everything.default.echo"
        inputSchema={{ type: "object", properties: {} }}
        onSubmit={(value) => { submissions.push(value); }}
        routeOutcomes={["ok", "error"]}
      />,
    );

    await user.type(screen.getByRole("textbox", { name: "Step id" }), "echo");
    expect(screen.getByRole("textbox", { name: "Route target for ok" })).toHaveValue("__end__");
    await user.clear(screen.getByRole("textbox", { name: "Route target for error" }));
    await user.type(screen.getByRole("textbox", { name: "Route target for error" }), "recover");
    await user.click(screen.getByRole("button", { name: "Add node" }));

    expect(submissions[0]).toMatchObject({
      routes: { ok: "__end__", error: "recover" },
    });
  });
});
