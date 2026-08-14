import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { normalizeSchema } from "../schema-form/schema-field.js";
import type { ExpressionEditorState } from "./input-expression-editor.js";
import { InputExpressionControl } from "./InputExpressionControl.js";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("InputExpressionControl", () => {
  it("offers construct mode for an unconstrained target", async () => {
    const user = userEvent.setup();
    const Harness = () => {
      const [state, setState] = useState<ExpressionEditorState>({
        kind: "literal",
        value: null,
        touched: false,
      });
      return (
        <InputExpressionControl
          field={null}
          label="payload"
          onChange={setState}
          state={state}
        />
      );
    };

    render(<Harness />);
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Value source for payload" }),
      "construct",
    );

    expect(screen.getByRole("group", { name: "payload" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add item to payload" })).toBeInTheDocument();
  });

  it("removes and restores an optional declared property", async () => {
    const user = userEvent.setup();
    const Harness = () => {
      const [state, setState] = useState<ExpressionEditorState>({
        kind: "object",
        fields: [{ name: "note", value: { kind: "literal", value: "", touched: false } }],
      });
      return (
        <InputExpressionControl
          field={normalizeSchema({
            type: "object",
            properties: { note: { type: "string" } },
          })}
          label="payload"
          onChange={setState}
          state={state}
        />
      );
    };

    render(<Harness />);
    await user.click(screen.getByRole("button", { name: "Remove payload.note" }));
    expect(screen.queryByRole("group", { name: "payload.note" })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Add optional property note to payload" }));
    expect(screen.getByRole("group", { name: "payload.note" })).toBeInTheDocument();
  });

  it("repairs one duplicate object field without changing the other", async () => {
    const user = userEvent.setup();
    const Harness = () => {
      const [state, setState] = useState<ExpressionEditorState>({
        kind: "object",
        fields: [
          { name: "duplicate", value: { kind: "literal", value: "first", touched: false } },
          { name: "duplicate", value: { kind: "literal", value: "second", touched: false } },
        ],
      });
      return (
        <InputExpressionControl
          field={normalizeSchema({ type: "object", additionalProperties: true })}
          label="payload"
          onChange={setState}
          state={state}
        />
      );
    };

    render(<Harness />);
    const removeButtons = screen.getAllByRole("button", { name: "Remove payload field duplicate" });
    await user.click(removeButtons[0]!);

    expect(screen.getAllByRole("group", { name: "payload field duplicate" })).toHaveLength(1);
  });

  it("adds, removes, and reorders array expressions with accessible controls", async () => {
    const user = userEvent.setup();
    let state: ExpressionEditorState = { kind: "array", items: [] };
    const renderControl = (): void => {
      render(
        <InputExpressionControl
          field={normalizeSchema({ type: "array", items: { type: "string" } })}
          label="items"
          onChange={(next) => {
            state = next;
            cleanup();
            renderControl();
          }}
          state={state}
        />,
      );
    };

    renderControl();
    await user.click(screen.getByRole("button", { name: "Add item to items" }));
    await user.click(screen.getByRole("button", { name: "Add item to items" }));
    expect(screen.getByRole("group", { name: "items item 1" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "items item 2" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Move items item 2 up" }));
    expect(state).toMatchObject({ kind: "array", items: [{ kind: "literal" }, { kind: "literal" }] });
    await user.click(screen.getByRole("button", { name: "Remove items item 1" }));
    expect(screen.getByRole("group", { name: "items item 1" })).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "items item 2" })).toBeNull();
  });

  it("supports nested object fields and named additional properties", async () => {
    const user = userEvent.setup();
    let state: ExpressionEditorState = {
      kind: "object",
      fields: [{ name: "known", value: { kind: "literal", value: "before", touched: false } }],
    };
    const renderControl = (): void => {
      render(
        <InputExpressionControl
          field={normalizeSchema({
            type: "object",
            properties: { known: { type: "string" } },
            additionalProperties: { type: "number" },
          })}
          label="payload"
          onChange={(next) => {
            state = next;
            cleanup();
            renderControl();
          }}
          state={state}
        />,
      );
    };

    renderControl();
    const name = screen.getByRole("textbox", { name: "Additional property name for payload" });
    await user.type(name, "count");
    await user.click(screen.getByRole("button", { name: "Add property to payload" }));

    expect(screen.getByRole("group", { name: "payload.count" })).toBeInTheDocument();
    expect(state).toMatchObject({ kind: "object", fields: [{ name: "known" }, { name: "count" }] });
    await user.type(screen.getByRole("textbox", { name: "Additional property name for payload" }), "count");
    expect(screen.getByRole("button", { name: "Add property to payload" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Remove payload.count" }));
    expect(screen.queryByRole("group", { name: "payload.count" })).toBeNull();
  });

  it("restores a missing required declared property without removing declared fields", async () => {
    const user = userEvent.setup();
    let state: ExpressionEditorState = { kind: "object", fields: [] };
    const renderControl = (): void => {
      render(
        <InputExpressionControl
          field={normalizeSchema({
            type: "object",
            properties: { name: { type: "string" } },
            required: ["name"],
          })}
          label="payload"
          onChange={(next) => {
            state = next;
            cleanup();
            renderControl();
          }}
          state={state}
        />,
      );
    };

    renderControl();
    expect(screen.getByRole("button", { name: "Add required property name to payload" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Add required property name to payload" }));

    expect(state).toMatchObject({ kind: "object", fields: [{ name: "name" }] });
    expect(screen.getByRole("group", { name: "payload.name" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove payload.name" })).toBeNull();
  });

  it("keeps nested additional-name state with its logical array item after reorder", async () => {
    const user = userEvent.setup();
    const Harness = () => {
      const [state, setState] = useState<ExpressionEditorState>({
        kind: "array",
        items: [
          { kind: "object", fields: [] },
          { kind: "object", fields: [] },
        ],
      });
      return (
        <InputExpressionControl
          field={normalizeSchema({
            type: "array",
            items: { type: "object", additionalProperties: true },
          })}
          label="items"
          onChange={setState}
          state={state}
        />
      );
    };

    render(<Harness />);
    const firstName = screen.getByRole("textbox", { name: "Additional property name for items item 1" });
    await user.type(firstName, "kept");
    await user.click(screen.getByRole("button", { name: "Move items item 2 up" }));

    expect(screen.getByRole("textbox", { name: "Additional property name for items item 1" })).toHaveValue("");
    expect(screen.getByRole("textbox", { name: "Additional property name for items item 2" })).toHaveValue("kept");
  });

  it("follows logical item identity across an external remove", async () => {
    const user = userEvent.setup();
    const first = { kind: "object", fields: [] } satisfies ExpressionEditorState;
    const second = { kind: "object", fields: [] } satisfies ExpressionEditorState;
    const Harness = () => {
      const [state, setState] = useState<ExpressionEditorState>({ kind: "array", items: [first, second] });
      return (
        <>
          <button onClick={() => setState({ kind: "array", items: state.kind === "array" ? state.items.slice(1) : [] })} type="button">
            External remove first
          </button>
          <InputExpressionControl
            field={normalizeSchema({ type: "array", items: { type: "object", additionalProperties: true } })}
            label="items"
            onChange={setState}
            state={state}
          />
        </>
      );
    };

    render(<Harness />);
    await user.type(screen.getByRole("textbox", { name: "Additional property name for items item 2" }), "second-local");
    await user.click(screen.getByRole("button", { name: "External remove first" }));

    expect(screen.getByRole("textbox", { name: "Additional property name for items item 1" })).toHaveValue("second-local");
  });

  it("follows logical item identity across an external reorder", async () => {
    const user = userEvent.setup();
    const first = { kind: "object", fields: [] } satisfies ExpressionEditorState;
    const second = { kind: "object", fields: [] } satisfies ExpressionEditorState;
    const Harness = () => {
      const [state, setState] = useState<ExpressionEditorState>({ kind: "array", items: [first, second] });
      return (
        <>
          <button
            onClick={() => setState({ kind: "array", items: state.kind === "array" ? [...state.items].reverse() : [] })}
            type="button"
          >
            External reorder
          </button>
          <InputExpressionControl
            field={normalizeSchema({ type: "array", items: { type: "object", additionalProperties: true } })}
            label="items"
            onChange={setState}
            state={state}
          />
        </>
      );
    };

    render(<Harness />);
    await user.type(screen.getByRole("textbox", { name: "Additional property name for items item 1" }), "first-local");
    await user.type(screen.getByRole("textbox", { name: "Additional property name for items item 2" }), "second-local");
    await user.click(screen.getByRole("button", { name: "External reorder" }));

    expect(screen.getByRole("textbox", { name: "Additional property name for items item 1" })).toHaveValue("second-local");
    expect(screen.getByRole("textbox", { name: "Additional property name for items item 2" })).toHaveValue("first-local");
  });

  it("allocates an identity for an externally added item without a missing key", async () => {
    const user = userEvent.setup();
    const first = { kind: "object", fields: [] } satisfies ExpressionEditorState;
    const Harness = () => {
      const [state, setState] = useState<ExpressionEditorState>({ kind: "array", items: [first] });
      return (
        <>
          <button
            onClick={() => setState({
              kind: "array",
              items: state.kind === "array" ? [...state.items, { kind: "object", fields: [] }] : [],
            })}
            type="button"
          >
            External add
          </button>
          <InputExpressionControl
            field={normalizeSchema({ type: "array", items: { type: "object", additionalProperties: true } })}
            label="items"
            onChange={setState}
            state={state}
          />
        </>
      );
    };

    render(<Harness />);
    await user.click(screen.getByRole("button", { name: "External add" }));

    expect(screen.getAllByRole("group", { name: "items item 2" })).not.toHaveLength(0);
    expect(screen.getAllByRole("textbox", { name: /Additional property name for items item/ })).toHaveLength(2);
  });

  it("does not carry local state into a reconstructed semantically equal item", async () => {
    const user = userEvent.setup();
    const Harness = () => {
      const [state, setState] = useState<ExpressionEditorState>({ kind: "array", items: [{ kind: "object", fields: [] }] });
      return (
        <>
          <button
            onClick={() => setState({ kind: "array", items: [{ kind: "object", fields: [] }] })}
            type="button"
          >
            External replace with equal value
          </button>
          <InputExpressionControl
            field={normalizeSchema({ type: "array", items: { type: "object", additionalProperties: true } })}
            label="items"
            onChange={setState}
            state={state}
          />
        </>
      );
    };

    render(<Harness />);
    const name = screen.getByRole("textbox", { name: "Additional property name for items item 1" });
    await user.type(name, "stale-local");
    await user.click(screen.getByRole("button", { name: "External replace with equal value" }));

    expect(screen.getByRole("textbox", { name: "Additional property name for items item 1" })).toHaveValue("");
  });

  it("gives repeated object references distinct keys across external array changes", async () => {
    const shared = { kind: "object", fields: [] } satisfies ExpressionEditorState;
    const user = userEvent.setup();
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const Harness = () => {
      const [state, setState] = useState<ExpressionEditorState>({ kind: "array", items: [shared, shared] });
      return (
        <>
          <button
            onClick={() => setState({ kind: "array", items: state.kind === "array" ? [...state.items].reverse() : [] })}
            type="button"
          >
            External reorder aliases
          </button>
          <button
            onClick={() => setState({ kind: "array", items: state.kind === "array" ? state.items.slice(1) : [] })}
            type="button"
          >
            External remove alias
          </button>
          <button
            onClick={() => setState({ kind: "array", items: state.kind === "array" ? [...state.items, shared] : [] })}
            type="button"
          >
            External add alias
          </button>
          <button
            onClick={() => setState({ kind: "array", items: [{ kind: "object", fields: [] }, shared] })}
            type="button"
          >
            External replace alias
          </button>
          <InputExpressionControl
            field={normalizeSchema({ type: "array", items: { type: "object", additionalProperties: true } })}
            label="items"
            onChange={setState}
            state={state}
          />
        </>
      );
    };

    render(<Harness />);
    await user.click(screen.getByRole("button", { name: "External reorder aliases" }));
    await user.click(screen.getByRole("button", { name: "External remove alias" }));
    await user.click(screen.getByRole("button", { name: "External add alias" }));
    await user.click(screen.getByRole("button", { name: "External replace alias" }));

    expect(consoleError.mock.calls.flat().join(" ")).not.toContain("same key");
  });

  it("transfers the edited occurrence identity when aliased children diverge", async () => {
    const shared = {
      kind: "object",
      fields: [{ name: "value", value: { kind: "literal", value: "", touched: false } }],
    } satisfies ExpressionEditorState;
    const user = userEvent.setup();
    const Harness = () => {
      const [state, setState] = useState<ExpressionEditorState>({ kind: "array", items: [shared, shared] });
      return (
        <>
          <button
            onClick={() => setState({ kind: "array", items: state.kind === "array" ? [...state.items].reverse() : [] })}
            type="button"
          >
            External reorder after child edit
          </button>
          <InputExpressionControl
            field={normalizeSchema({
              type: "array",
              items: { type: "object", properties: { value: { type: "string" } }, additionalProperties: true },
            })}
            label="items"
            onChange={setState}
            state={state}
          />
        </>
      );
    };

    render(<Harness />);
    await user.type(screen.getByRole("textbox", { name: "Additional property name for items item 2" }), "second-local");
    await user.type(screen.getAllByRole("textbox", { name: "Value" })[1]!, "changed");
    await user.click(screen.getByRole("button", { name: "External reorder after child edit" }));

    expect(screen.getByRole("textbox", { name: "Additional property name for items item 1" })).toHaveValue("second-local");
  });

  it("gives repeated labels unique datalist and typed-leaf control ids", () => {
    const field = normalizeSchema({ type: "string" });
    render(
      <>
        <InputExpressionControl
          field={field}
          label="value"
          onChange={() => undefined}
          state={{ kind: "path", path: "state.first", touched: false }}
        />
        <InputExpressionControl
          field={field}
          label="value"
          onChange={() => undefined}
          state={{ kind: "path", path: "state.second", touched: false }}
        />
        <InputExpressionControl
          field={field}
          label="value"
          onChange={() => undefined}
          state={{ kind: "literal", value: "first", touched: false }}
        />
        <InputExpressionControl
          field={field}
          label="value"
          onChange={() => undefined}
          state={{ kind: "literal", value: "second", touched: false }}
        />
      </>,
    );

    const datalistIds = [...document.querySelectorAll("datalist")].map((element) => element.id);
    const controlIds = [...document.querySelectorAll("textarea")].map((element) => element.id);
    expect(datalistIds).toHaveLength(2);
    expect(new Set(datalistIds).size).toBe(datalistIds.length);
    expect(controlIds).toHaveLength(2);
    expect(new Set(controlIds).size).toBe(controlIds.length);
  });

  it("exposes deferred path guidance and keeps construct unavailable for scalar schemas", async () => {
    const user = userEvent.setup();
    let state: ExpressionEditorState = { kind: "path", path: "context.profile", touched: false };
    const control = () => (
      <InputExpressionControl
        field={normalizeSchema({ type: "string" })}
        label="name"
        onChange={(next) => {
          state = next;
          view.rerender(control());
        }}
        state={state}
      />
    );
    const view = render(control());

    expect(screen.getByText("Validated when the workflow runs")).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Construct" })).toBeNull();
    await user.clear(screen.getByRole("combobox", { name: "Path for name" }));
    await user.type(screen.getByRole("combobox", { name: "Path for name" }), "state.name");
    expect(state).toMatchObject({ kind: "path", path: "state.name" });
  });
});
