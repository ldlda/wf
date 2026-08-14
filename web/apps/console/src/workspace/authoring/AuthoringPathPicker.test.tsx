import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  AuthoringPathOption,
  AuthoringPathUse,
} from "../domain/authoring-contract-models.js";
import { AuthoringPathPicker } from "./AuthoringPathPicker.js";

afterEach(() => {
  cleanup();
});

const option = (
  path: string,
  label: string,
  origin: AuthoringPathOption["origin"],
  uses: ReadonlyArray<AuthoringPathUse>,
  extras: Partial<AuthoringPathOption> = {},
): AuthoringPathOption => ({
  path,
  label,
  origin,
  schema: { type: "string" },
  required: false,
  availability: "available",
  uses,
  ...extras,
});

const options: ReadonlyArray<AuthoringPathOption> = [
  option("input.title", "Title", "workflow_input", ["step_input"], {
    description: "The report title.",
    required: true,
  }),
  option("state.report", "Report state", "workflow_state", ["step_input"]),
  option("step_output.markdown", "Markdown", "step_output", ["step_output_source"], {
    description: "Rendered markdown content.",
  }),
  option("context.viewer_id", "Viewer ID", "runtime_context", ["step_input"], {
    availability: "conditional",
    reason: "Available when the selected step runs in a viewer frame.",
  }),
  option("context.viewer_email", "Viewer email", "runtime_context", ["workflow_output"], {
    availability: "conditional",
    reason: "Available only in viewer frames.",
  }),
  option("output.report", "Final report", "workflow_output", ["workflow_output"]),
  option("input.customer.name", "Customer name", "workflow_input", ["step_input"]),
];

describe("AuthoringPathPicker", () => {
  it("groups options by semantic origin and shows canonical paths secondarily", () => {
    render(
      <AuthoringPathPicker
        label="Source path"
        onChange={vi.fn()}
        options={options}
        uses="step_input"
        value=""
      />,
    );

    expect(screen.getByRole("group", { name: "Workflow input" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "State" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Step output" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Runtime context" })).toBeInTheDocument();
    expect(screen.getByText("input.title")).toBeInTheDocument();
    expect(screen.getByText("Title")).toBeInTheDocument();
  });

  it("searches labels, canonical paths, and descriptions", async () => {
    const user = userEvent.setup();
    render(
      <AuthoringPathPicker
        label="Source path"
        onChange={vi.fn()}
        options={options}
        uses="step_input"
        value=""
      />,
    );

    await user.type(screen.getByRole("searchbox", { name: "Search Source path" }), "rendered");

    expect(screen.getByRole("button", { name: /Markdown/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Title/ })).not.toBeInTheDocument();
  });

  it("explains conditional options and hides an empty runtime context group", () => {
    const { rerender } = render(
      <AuthoringPathPicker
        label="Source path"
        onChange={vi.fn()}
        options={options}
        uses="step_input"
        value=""
      />,
    );

    expect(
      screen.getByText("Available when the selected step runs in a viewer frame."),
    ).toBeInTheDocument();

    rerender(
      <AuthoringPathPicker
        label="Source path"
        onChange={vi.fn()}
        options={options.filter((entry) => entry.origin !== "runtime_context")}
        uses="step_input"
        value=""
      />,
    );

    expect(screen.queryByRole("group", { name: "Runtime context" })).not.toBeInTheDocument();
  });

  it("disables incompatible entries and emits only a canonical path", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <AuthoringPathPicker
        label="Source path"
        onChange={onChange}
        options={options}
        uses="step_input"
        value=""
      />,
    );

    const incompatible = screen.getByRole("button", { name: /Final report/ });
    expect(incompatible).toBeDisabled();
    await user.click(incompatible);
    await user.click(screen.getByRole("button", { name: /Title/ }));

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("input.title", "catalog");
  });

  it("gives a conditional incompatible option one composed description node", () => {
    render(
      <AuthoringPathPicker
        label="Source path"
        onChange={vi.fn()}
        options={options}
        uses="step_input"
        value=""
      />,
    );

    const optionButton = screen.getByRole("button", { name: /Viewer email/ });
    const describedBy = optionButton.getAttribute("aria-describedby");

    expect(optionButton).toBeDisabled();
    expect(describedBy).not.toBeNull();
    expect(describedBy?.trim().split(/\s+/)).toHaveLength(1);
    expect(document.querySelectorAll(`#${describedBy}`).length).toBe(1);
    expect(document.getElementById(describedBy ?? "")?.textContent).toContain(
      "Available only in viewer frames.",
    );
    expect(document.getElementById(describedBy ?? "")?.textContent).toContain(
      "Not available for this field.",
    );
  });

  it("renders a supplied non-conditional reason before describing the option", () => {
    render(
      <AuthoringPathPicker
        label="Source path"
        onChange={vi.fn()}
        options={[
          option("input.reasoned", "Reasoned", "workflow_input", ["step_input"], {
            reason: "Retained for repair context.",
          }),
        ]}
        uses="step_input"
        value=""
      />,
    );

    const optionButton = screen.getByRole("button", { name: /Reasoned/ });
    const describedBy = optionButton.getAttribute("aria-describedby");
    expect(describedBy).not.toBeNull();
    expect(document.getElementById(describedBy ?? "")?.textContent).toBe(
      "Retained for repair context.",
    );
  });

  it("keeps nested choices keyboard reachable and preserves normal choices in Advanced mode", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <AuthoringPathPicker
        allowCustom
        label="Source path"
        onChange={onChange}
        options={options}
        uses="step_input"
        value=""
      />,
    );

    const nested = screen.getByRole("button", { name: /Customer name/ });
    nested.focus();
    await user.keyboard("{Enter}");
    expect(onChange).toHaveBeenCalledWith("input.customer.name", "catalog");

    await user.click(screen.getByText("Advanced"));
    expect(screen.getByRole("textbox", { name: "Custom Source path" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Title/ })).toBeInTheDocument();

    await user.clear(screen.getByRole("textbox", { name: "Custom Source path" }));
    await user.type(screen.getByRole("textbox", { name: "Custom Source path" }), "context.future");
    expect(onChange).toHaveBeenLastCalledWith("context.future", "custom");
  });
});
