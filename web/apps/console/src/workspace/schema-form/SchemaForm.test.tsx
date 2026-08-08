import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SchemaForm } from "./SchemaForm.js";
import type { SchemaSerializationResult } from "./schema-values.js";

const schema = {
  type: "object",
  properties: {
    summary: { type: "string", description: "A short report summary." },
    amount: { type: "number" },
    enabled: { type: "boolean" },
    color: { enum: ["red", "blue"] },
    profile: {
      type: "object",
      properties: { name: { type: "string" } },
      required: ["name"],
    },
    tags: { type: "array", items: { type: "string" } },
  },
  required: ["summary"],
};

describe("SchemaForm", () => {
  afterEach(() => cleanup());

  it("renders accessible native controls and a collapsed raw schema", () => {
    render(<SchemaForm schema={schema} />);

    expect(screen.getByRole("textbox", { name: "Summary" })).toHaveAttribute(
      "aria-required",
      "true",
    );
    expect(screen.getByText("A short report summary.")).toBeInTheDocument();
    expect(screen.getByRole("spinbutton", { name: "Amount" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Enabled" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Color" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Profile" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add tag" })).toBeInTheDocument();
    expect(screen.getByText("Raw schema").closest("details")).not.toHaveAttribute("open");
  });

  it("renders unsupported fields as JSON editors with their exact fallback reason", () => {
    render(
      <SchemaForm
        schema={{
          type: "object",
          properties: {
            choice: { oneOf: [{ type: "string" }, { type: "number" }] },
          },
        }}
      />,
    );

    expect(screen.getByRole("textbox", { name: "Choice" })).toHaveAttribute(
      "aria-label",
      "Choice",
    );
    expect(
      screen.getByText("The schema uses oneOf, which the native form cannot represent."),
    ).toBeInTheDocument();
  });

  it("exposes literal and bind modes and submits canonical values and bindings", async () => {
    const user = userEvent.setup();
    const submissions: SchemaSerializationResult[] = [];
    render(
      <SchemaForm
        schema={{ type: "object", properties: { summary: { type: "string" } } }}
        initialValue={{ summary: "Report" }}
        initialSources={{ summary: { mode: "bind", sourcePath: "input.summary" } }}
        onSubmit={(result) => submissions.push(result)}
      />,
    );

    const summarySource = screen.getAllByRole("group", { name: "Value source" })[0];
    expect(within(summarySource!).getByRole("radio", { name: "Bind" })).toBeChecked();
    expect(screen.getByRole("textbox", { name: "Source path for Summary" })).toHaveValue(
      "input.summary",
    );
    await user.click(screen.getByRole("button", { name: "Save form" }));

    expect(submissions[0]?.value).toEqual({ summary: undefined });
    expect(submissions[0]?.bindings).toEqual([
      { target: "summary", path: "input.summary" },
    ]);
  });

  it("shows field diagnostics and supports adding array items", async () => {
    const user = userEvent.setup();
    render(
      <SchemaForm
        schema={schema}
        diagnostics={[{ path: ["summary"], message: "Summary is already used." }]}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Summary is already used.");
    expect(screen.queryAllByRole("textbox", { name: "Tag" })).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Add tag" }));
    expect(screen.getByRole("textbox", { name: "Tag 1" })).toBeInTheDocument();
  });
});
