import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { RouteForm } from "./RouteForm.js";

afterEach(() => cleanup());

describe("RouteForm", () => {
  it("replaces a selected route through explicit source, outcome, and target fields", async () => {
    const user = userEvent.setup();
    const submissions: unknown[] = [];
    render(
      <RouteForm
        initialValue={{ stepId: "read", outcome: "ok", target: "publish" }}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    await user.clear(screen.getByRole("textbox", { name: "Target step" }));
    await user.type(screen.getByRole("textbox", { name: "Target step" }), "archive");
    await user.click(screen.getByRole("button", { name: "Set route" }));

    expect(submissions).toEqual([
      { stepId: "read", outcome: "ok", target: "archive" },
    ]);
  });

  it("does not discard dirty values when the form is hidden and shown again", async () => {
    const user = userEvent.setup();
    let hidden = false;
    const { rerender } = render(
      <RouteForm
        hidden={hidden}
        initialValue={{ stepId: "read", outcome: "ok", target: "publish" }}
        onSubmit={() => undefined}
      />,
    );
    await user.clear(screen.getByRole("textbox", { name: "Target step" }));
    await user.type(screen.getByRole("textbox", { name: "Target step" }), "archive");
    hidden = true;
    rerender(
      <RouteForm
        hidden={hidden}
        initialValue={{ stepId: "read", outcome: "ok", target: "publish" }}
        onSubmit={() => undefined}
      />,
    );
    hidden = false;
    rerender(
      <RouteForm
        hidden={hidden}
        initialValue={{ stepId: "read", outcome: "ok", target: "publish" }}
        onSubmit={() => undefined}
      />,
    );

    expect(screen.getByRole("textbox", { name: "Target step" })).toHaveValue("archive");
  });
});
