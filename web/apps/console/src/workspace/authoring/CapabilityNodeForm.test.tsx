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
    await user.click(screen.getByRole("button", { name: "Add node" }));

    expect(submissions[0]).toMatchObject({
      stepId: "enrich",
      capabilityName: "demo.enrich",
      description: "Enrich report",
        inputBindings: [{ target: "title", value: "Quarterly report" }],
      });
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
});
