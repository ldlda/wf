import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkflowSchemaFieldsForm } from "./WorkflowSchemaFieldsForm.js";

afterEach(cleanup);

describe("WorkflowSchemaFieldsForm", () => {
  it("edits nested fields without exposing state metadata on input", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(
      <WorkflowSchemaFieldsForm
        contract="input"
        onSubmit={onSubmit}
        schema={{
          type: "object",
          properties: {
            request: {
              type: "object",
              properties: { title: { type: "string" } },
            },
          },
        }}
      />,
    );

    expect(screen.queryByRole("textbox", { name: "Reducer" })).toBeNull();
    const descriptions = screen.getAllByRole("textbox", { name: "Description" });
    await user.type(descriptions[1]!, "Report title");
    await user.click(screen.getByRole("button", { name: "Save input schema" }));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        properties: expect.objectContaining({
          request: expect.objectContaining({
            properties: { title: { type: "string", description: "Report title" } },
          }),
        }),
      }),
    );
  });

  it("shows state default and reducer controls", () => {
    render(
      <WorkflowSchemaFieldsForm
        contract="state"
        onSubmit={vi.fn()}
        schema={{
          type: "object",
          properties: { count: { type: "integer", default: 0, reducer: "wf.std.add" } },
        }}
      />,
    );

    expect(screen.getByRole("textbox", { name: "Reducer" })).toHaveValue("wf.std.add");
    expect(screen.getByRole("textbox", { name: "Default JSON" })).toHaveValue("0");
  });

  it("keeps unsupported fields visible until explicitly removed", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(
      <WorkflowSchemaFieldsForm
        contract="output"
        onSubmit={onSubmit}
        schema={{
          type: "object",
          properties: { choice: { oneOf: [{ type: "string" }, { type: "number" }] } },
        }}
      />,
    );

    expect(screen.getByRole("group", { name: "Unsupported field choice" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save output schema" }));
    expect(onSubmit).toHaveBeenLastCalledWith(
      expect.objectContaining({ properties: { choice: expect.objectContaining({ oneOf: expect.any(Array) }) } }),
    );
    await user.click(screen.getByRole("button", { name: "Remove unsupported field" }));
    await user.click(screen.getByRole("button", { name: "Save output schema" }));
    expect(onSubmit).toHaveBeenLastCalledWith(expect.objectContaining({ properties: {} }));
  });
});
