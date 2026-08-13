import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
