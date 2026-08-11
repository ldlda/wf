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

  it("suppresses source selectors when source controls are disabled", () => {
    render(
      <SchemaForm
        initialSources={{ summary: { mode: "bind", sourcePath: "input.summary" } }}
        initialValue={{ summary: "literal summary" }}
        schema={{ type: "object", properties: { summary: { type: "string" } } }}
        showSourceControls={false}
        submitLabel="Call capability"
      />,
    );

    expect(screen.getByRole("textbox", { name: "Summary" })).toHaveValue("literal summary");
    expect(screen.queryByRole("group", { name: "Value source" })).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Source path for Summary" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Call capability" })).toBeInTheDocument();
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

  it("reindexes bindings when removing the first array item", async () => {
    const user = userEvent.setup();
    const submissions: SchemaSerializationResult[] = [];
    render(
      <SchemaForm
        initialSources={{
          "items.0.name": { mode: "bind", sourcePath: "input.first" },
          "items.1.name": { mode: "bind", sourcePath: "input.second" },
        }}
        initialValue={{ items: [{ name: "first" }, { name: "second" }] }}
        onSubmit={(result) => submissions.push(result)}
        schema={{
          type: "object",
          properties: {
            items: {
              type: "array",
              items: {
                type: "object",
                properties: { name: { type: "string" } },
              },
            },
          },
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Remove item 1" }));
    await user.click(screen.getByRole("button", { name: "Save form" }));

    expect(submissions[0]?.bindings).toEqual([
      { target: "items.0.name", path: "input.second" },
    ]);
  });

  it("omits an untouched optional boolean but preserves explicit false", async () => {
    const user = userEvent.setup();
    const untouched: SchemaSerializationResult[] = [];
    const { unmount } = render(
      <SchemaForm
        onSubmit={(result) => untouched.push(result)}
        schema={{ type: "object", properties: { enabled: { type: "boolean" } } }}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Save form" }));
    expect(untouched[0]?.value).toEqual({});
    unmount();

    const explicit: SchemaSerializationResult[] = [];
    render(
      <SchemaForm
        initialValue={{ enabled: false }}
        onSubmit={(result) => explicit.push(result)}
        schema={{ type: "object", properties: { enabled: { type: "boolean" } } }}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Save form" }));
    expect(explicit[0]?.value).toEqual({ enabled: false });
  });

  it("offers an unset, true, and false choice for a required boolean without a default", async () => {
    const user = userEvent.setup();
    const submissions: SchemaSerializationResult[] = [];
    render(
      <SchemaForm
        onSubmit={(result) => submissions.push(result)}
        schema={{
          type: "object",
          properties: { enabled: { type: "boolean" } },
          required: ["enabled"],
        }}
      />,
    );

    const enabled = screen.getByRole("combobox", { name: "Enabled" });
    expect(enabled).toHaveValue("");
    expect(screen.getByRole("option", { name: "Choose true or false" })).toBeInTheDocument();
    await user.selectOptions(enabled, "false");
    await user.click(screen.getByRole("button", { name: "Save form" }));
    expect(submissions[0]?.value).toEqual({ enabled: false });
    expect(submissions[0]?.issues).toEqual([]);
  });

  it("serializes the true choice for a required boolean without a default", async () => {
    const user = userEvent.setup();
    const submissions: SchemaSerializationResult[] = [];
    render(
      <SchemaForm
        onSubmit={(result) => submissions.push(result)}
        schema={{
          type: "object",
          properties: { enabled: { type: "boolean" } },
          required: ["enabled"],
        }}
      />,
    );

    await user.selectOptions(screen.getByRole("combobox", { name: "Enabled" }), "true");
    await user.click(screen.getByRole("button", { name: "Save form" }));
    expect(submissions[0]?.value).toEqual({ enabled: true });
    expect(submissions[0]?.issues).toEqual([]);
  });

  it("routes nested diagnostics only to their owning field", () => {
    render(
      <SchemaForm
        diagnostics={[{ path: ["profile", "name2"], message: "Second name is invalid." }]}
        schema={{
          type: "object",
          properties: {
            profile: {
              type: "object",
              properties: { name: { type: "string" }, name2: { type: "string" } },
            },
          },
        }}
      />,
    );

    const name = screen.getByRole("textbox", { name: "Name" });
    const name2 = screen.getByRole("textbox", { name: "Name2" });
    expect(name).not.toHaveAttribute("aria-describedby", expect.stringContaining("diagnostics"));
    expect(name2).toHaveAttribute("aria-describedby", expect.stringContaining("diagnostics"));
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });

  it("routes diagnostics into nested array object items", () => {
    render(
      <SchemaForm
        diagnostics={[{ path: ["items", 1, "name"], message: "Second item is invalid." }]}
        initialValue={{ items: [{ name: "first" }, { name: "second" }] }}
        schema={{
          type: "object",
          properties: {
            items: {
              type: "array",
              items: {
                type: "object",
                properties: { name: { type: "string" } },
              },
            },
          },
        }}
      />,
    );

    const names = screen.getAllByRole("textbox", { name: "Name" });
    expect(names[0]).not.toHaveAttribute("aria-describedby", expect.stringContaining("diagnostics"));
    expect(names[1]).toHaveAttribute("aria-describedby", expect.stringContaining("diagnostics"));
  });

  it("preserves the literal value when toggling from Bind back to Literal", async () => {
    const user = userEvent.setup();
    const submissions: SchemaSerializationResult[] = [];
    render(
      <SchemaForm
        initialSources={{ summary: { mode: "bind", sourcePath: "input.summary" } }}
        initialValue={{ summary: "keep this literal" }}
        onSubmit={(result) => submissions.push(result)}
        schema={{ type: "object", properties: { summary: { type: "string" } } }}
      />,
    );

    await user.click(screen.getByRole("radio", { name: "Literal" }));
    await user.click(screen.getByRole("button", { name: "Save form" }));

    expect(submissions[0]?.value).toEqual({ summary: "keep this literal" });
    expect(submissions[0]?.bindings).toEqual([]);
  });

  it("round-trips colliding enum display values through distinct option identities", async () => {
    const user = userEvent.setup();
    const submissions: SchemaSerializationResult[] = [];
    render(
      <SchemaForm
        onSubmit={(result) => submissions.push(result)}
        schema={{
          type: "object",
          properties: { choice: { enum: ["1", 1, "true", true] } },
        }}
      />,
    );
    const select = screen.getByRole("combobox", { name: "Choice" });
    const options = screen.getAllByRole("option");
    const numberOption = options[2];
    expect(numberOption).toBeDefined();
    if (!numberOption) return;
    await user.selectOptions(select, numberOption);
    await user.click(screen.getByRole("button", { name: "Save form" }));

    expect(submissions[0]?.value).toEqual({ choice: 1 });
  });

  it("associates required group help and fallback reasons with controls", () => {
    render(
      <SchemaForm
        schema={{
          type: "object",
          properties: {
            settings: { type: "object", properties: {} },
            choice: { oneOf: [{ type: "string" }, { type: "number" }] },
          },
          required: ["settings", "choice"],
        }}
      />,
    );

    expect(screen.getByRole("group", { name: /Settings.*required/ })).toBeInTheDocument();
    const choice = screen.getByRole("textbox", { name: "Choice" });
    expect(choice).toHaveAttribute("aria-describedby", expect.stringContaining("fallback"));
    expect(screen.getByText("The schema uses oneOf, which the native form cannot represent.")).toHaveAttribute(
      "id",
      expect.stringContaining("fallback"),
    );
  });

  it("generates distinct ids for dotted and hyphenated property names", () => {
    render(
      <SchemaForm
        schema={{
          type: "object",
          properties: { "a.b": { type: "string" }, "a-b": { type: "string" } },
        }}
      />,
    );

    const dotted = screen.getByRole("textbox", { name: "A.b" });
    const hyphenated = screen.getByRole("textbox", { name: "A-b" });
    expect(dotted.id).not.toBe(hyphenated.id);
  });

  it("edits a canonical literal source without aliasing a nested path", async () => {
    const user = userEvent.setup();
    const submissions: SchemaSerializationResult[] = [];
    render(
      <SchemaForm
        initialSources={{
          "a.b": { mode: "literal", value: "canonical nested" },
        }}
        initialValue={{ "a.b": "initial dotted", a: { b: "initial nested" } }}
        onSubmit={(result) => submissions.push(result)}
        schema={{
          type: "object",
          properties: {
            "a.b": { type: "string" },
            a: { type: "object", properties: { b: { type: "string" } } },
          },
        }}
      />,
    );

    const dotted = screen.getByRole("textbox", { name: "A.b" });
    await user.clear(dotted);
    await user.type(dotted, "edited dotted");
    await user.click(screen.getByRole("button", { name: "Save form" }));

    expect(submissions[0]?.value).toEqual({ "a.b": "edited dotted", a: { b: "canonical nested" } });
  });

  it("updates the canonical literal source when its field is edited", async () => {
    const user = userEvent.setup();
    const submissions: SchemaSerializationResult[] = [];
    render(
      <SchemaForm
        initialSources={{ '"a.b"': { mode: "literal", value: "canonical dotted" } }}
        initialValue={{ "a.b": "initial dotted" }}
        onSubmit={(result) => submissions.push(result)}
        schema={{ type: "object", properties: { "a.b": { type: "string" } } }}
      />,
    );

    const dotted = screen.getByRole("textbox", { name: "A.b" });
    await user.clear(dotted);
    await user.type(dotted, "edited canonical");
    await user.click(screen.getByRole("button", { name: "Save form" }));

    expect(submissions[0]?.value).toEqual({ "a.b": "edited canonical" });
  });
});
