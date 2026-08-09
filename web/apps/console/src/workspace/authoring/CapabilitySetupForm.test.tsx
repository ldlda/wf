import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { CapabilitySetupForm } from "./CapabilitySetupForm.js";

afterEach(() => cleanup());

describe("CapabilitySetupForm", () => {
  it("omits untouched blank optional metadata", async () => {
    const user = userEvent.setup();
    const submissions: unknown[] = [];
    render(<CapabilitySetupForm onSubmit={(value) => { submissions.push(value); }} />);

    await user.click(screen.getByRole("button", { name: "Save setup" }));

    expect(submissions).toEqual([{}]);
  });

  it("submits null only when clearing an existing value", async () => {
    const user = userEvent.setup();
    const submissions: unknown[] = [];
    render(
      <CapabilitySetupForm
        initialValue={{ retry: 3, timeoutSeconds: 12 }}
        onSubmit={(value) => { submissions.push(value); }}
      />,
    );

    await user.clear(screen.getByRole("spinbutton", { name: "Retry" }));
    await user.click(screen.getByRole("button", { name: "Save setup" }));

    expect(submissions[0]).toEqual({ retry: null });
    expect(submissions[0]).not.toHaveProperty("timeoutSeconds");
  });

  it("accepts retry zero", async () => {
    const user = userEvent.setup();
    const submissions: unknown[] = [];
    render(<CapabilitySetupForm onSubmit={(value) => { submissions.push(value); }} />);

    await user.type(screen.getByRole("spinbutton", { name: "Retry" }), "0");
    await user.click(screen.getByRole("button", { name: "Save setup" }));

    expect(submissions).toEqual([{ retry: 0 }]);
  });

  it.each([
    ["-1", "Retry must be at least 0."],
    ["1.5", "Retry must be a whole number."],
  ])("rejects retry %s", async (value, message) => {
    const user = userEvent.setup();
    const submissions: unknown[] = [];
    render(<CapabilitySetupForm onSubmit={(input) => { submissions.push(input); }} />);

    await user.type(screen.getByRole("spinbutton", { name: "Retry" }), value);
    await user.click(screen.getByRole("button", { name: "Save setup" }));

    expect(screen.getByRole("alert")).toHaveTextContent(message);
    expect(submissions).toEqual([]);
  });

  it("rejects timeout zero and accepts a positive timeout", async () => {
    const user = userEvent.setup();
    const submissions: unknown[] = [];
    render(<CapabilitySetupForm onSubmit={(value) => { submissions.push(value); }} />);

    await user.type(screen.getByRole("spinbutton", { name: "Timeout seconds" }), "0");
    await user.click(screen.getByRole("button", { name: "Save setup" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Timeout must be greater than 0.");
    expect(submissions).toEqual([]);

    await user.clear(screen.getByRole("spinbutton", { name: "Timeout seconds" }));
    await user.type(screen.getByRole("spinbutton", { name: "Timeout seconds" }), "2.5");
    await user.click(screen.getByRole("button", { name: "Save setup" }));

    expect(submissions).toEqual([{ timeoutSeconds: 2.5 }]);
  });

  it("associates local retry errors with the retry control and avoids duplicate ids", async () => {
    const user = userEvent.setup();
    render(
      <>
        <CapabilitySetupForm onSubmit={() => undefined} />
        <CapabilitySetupForm onSubmit={() => undefined} />
      </>,
    );

    const retryInputs = screen.getAllByRole("spinbutton", { name: "Retry" });
    expect(new Set(retryInputs.map((input) => input.id)).size).toBe(2);
    expect(new Set(retryInputs.map((input) => input.getAttribute("aria-describedby"))).size).toBe(1);

    await user.type(retryInputs[0]!, "-1");
    await user.click(screen.getAllByRole("button", { name: "Save setup" })[0]!);

    const describedBy = retryInputs[0]!.getAttribute("aria-describedby");
    expect(retryInputs[0]).toHaveAttribute("aria-invalid", "true");
    expect(describedBy).toBeTruthy();
    expect(document.getElementById(describedBy ?? "")).toHaveTextContent("Retry must be at least 0.");
  });
});
