import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { CapabilityNodeForm } from "./CapabilityNodeForm.js";

afterEach(() => cleanup());

describe("CapabilityNodeForm", () => {
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
    expect(screen.getByRole("spinbutton", { name: "Timeout seconds" })).toHaveAttribute("inputmode", "decimal");
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
