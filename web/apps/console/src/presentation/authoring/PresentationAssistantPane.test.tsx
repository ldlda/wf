import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PresentationAssistantPane } from "./PresentationAssistantPane.js";
import {
  PREPARED_LIFECYCLE_PHASE_PLACEHOLDERS,
  PREPARED_LIFECYCLE_PHASE_PROMPTS,
  initialPreparedLifecycleMessageState,
  projectPreparedLifecycleMessage,
} from "./prepared-lifecycle-message-state.js";

afterEach(cleanup);

const renderPane = (
  phase: Parameters<typeof projectPreparedLifecycleMessage>[1],
  options: Partial<ComponentProps<typeof PresentationAssistantPane>> = {},
) => {
  const onDraftChange = options.onDraftChange ?? (() => undefined);
  const onSubmit = options.onSubmit ?? (() => undefined);

  return render(
    <PresentationAssistantPane
      phase={phase}
      message={projectPreparedLifecycleMessage(initialPreparedLifecycleMessageState, phase)}
      submittedOverrides={{}}
      runRequested={null}
      onDraftChange={onDraftChange}
      onSubmit={onSubmit}
      {...options}
    />,
  );
};

describe("PresentationAssistantPane", () => {
  it("renders a persistent prepared replay surface for the current phase", () => {
    renderPane("validate");

    expect(screen.getByRole("complementary", { name: /prepared authoring assistant/i })).not.toHaveAttribute(
      "data-visual-role",
    );
    expect(screen.getByRole("heading", { name: /authoring assistant/i })).toBeInTheDocument();
    expect(screen.getByText(/current phase: validate/i)).toBeInTheDocument();
    expect(screen.getByText(/prepared replay only/i)).toBeInTheDocument();
  });

  it("exposes an explicit support role when composed in the lifecycle scene", () => {
    renderPane("validate", { visualRole: "support" });

    expect(screen.getByRole("complementary", { name: /prepared authoring assistant/i })).toHaveAttribute(
      "data-visual-role",
      "support",
    );
  });

  it("keeps the active tool group synchronized with the phase", () => {
    renderPane("artifact");

    expect(screen.getByRole("button", { name: /artifact.*3 tool calls/i }))
      .toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /validate.*3 tool calls/i }))
      .toHaveAttribute("aria-expanded", "false");
  });

  it("renders an empty, accessible message surface for empty phases", () => {
    for (const phase of ["discover", "validate"] as const) {
      cleanup();
      renderPane(phase);

      const input = screen.getByRole("textbox", { name: /message to authoring assistant/i });
      expect(input).toHaveValue("");
      expect(input).toHaveAttribute("placeholder", PREPARED_LIFECYCLE_PHASE_PLACEHOLDERS[phase]);
      expect(screen.getByRole("button", { name: /send message/i })).toBeDisabled();
    }
  });

  it("prefills every staged request with its exact prompt", () => {
    for (const phase of ["draft", "artifact", "deployment"] as const) {
      cleanup();
      renderPane(phase);

      expect(screen.getByRole("textbox", { name: /message to authoring assistant/i }))
        .toHaveValue(PREPARED_LIFECYCLE_PHASE_PROMPTS[phase]);
    }
  });

  it("preserves edits until submit and submits the edited value", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderPane("draft", { onSubmit });

    const input = screen.getByRole("textbox", { name: /message to authoring assistant/i });
    await user.clear(input);
    await user.type(input, "Check only the report binding.");
    expect(input).toHaveValue("Check only the report binding.");

    await user.click(screen.getByRole("button", { name: /send message/i }));
    expect(onSubmit).toHaveBeenCalledWith("Check only the report binding.");
  });

  it("uses Shift+Enter for newlines and Enter to submit", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderPane("artifact", { onSubmit });
    const input = screen.getByRole("textbox", { name: /message to authoring assistant/i });

    await user.clear(input);
    await user.type(input, "first");
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    await user.type(input, "second");
    expect(input).toHaveValue("first\nsecond");
    expect(onSubmit).not.toHaveBeenCalled();

    await user.keyboard("{Enter}");
    expect(onSubmit).toHaveBeenCalledWith("first\nsecond");
  });

  it("ignores blank submissions and disables the terminal request after submission", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderPane("deployment", { onSubmit });
    const input = screen.getByRole("textbox", { name: /message to authoring assistant/i });

    await user.clear(input);
    expect(screen.getByRole("button", { name: /send message/i })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: /send message/i }));
    expect(onSubmit).not.toHaveBeenCalled();

    cleanup();
    renderPane("deployment", { runRequested: "Run this deployment" });
    expect(screen.getByRole("button", { name: /send message/i })).toBeDisabled();
  });

  it("renders submitted overrides while keeping the replay tools canonical", () => {
    renderPane("validate", { submittedOverrides: { validate: "Edited validation request" } });

    expect(screen.getByText("Edited validation request")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /workflow\.draft_workspaces\.validate/i }))
      .toBeInTheDocument();
  });

  it("does not expose a live or run action", () => {
    renderPane("deployment");

    expect(screen.queryByRole("button", { name: /run|execute/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/workflow\.runs\.start/i)).not.toBeInTheDocument();
  });
});
