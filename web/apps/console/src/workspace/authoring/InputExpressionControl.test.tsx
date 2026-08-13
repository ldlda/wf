import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { normalizeSchema } from "../schema-form/schema-field.js";
import type { ExpressionEditorState } from "./input-expression-editor.js";
import { InputExpressionControl } from "./InputExpressionControl.js";

afterEach(() => cleanup());

describe("InputExpressionControl", () => {
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
