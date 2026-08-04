import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { initialState } from "../app/state.js";
import { ConsoleShell } from "./ConsoleShell.js";

afterEach(() => cleanup());

describe("ConsoleShell", () => {
  it("renders the connection header, lifecycle rail, main content, and evidence surface", () => {
    render(
      <MemoryRouter initialEntries={["/console/discover"]}>
        <ConsoleShell
          connection={initialState()}
          onConnect={() => undefined}
          onDraftChange={() => undefined}
        >
          <p>Discover content</p>
        </ConsoleShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Workflow lifecycle" })).toBeInTheDocument();
    expect(screen.getByRole("main", { name: "Console workspace" })).toHaveTextContent(
      "Discover content",
    );
    expect(screen.getByRole("complementary", { name: "Operation evidence" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Discover" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("renders all lifecycle links with route destinations", () => {
    render(
      <MemoryRouter>
        <ConsoleShell
          connection={initialState()}
          onConnect={() => undefined}
          onDraftChange={() => undefined}
        >
          <p>Content</p>
        </ConsoleShell>
      </MemoryRouter>,
    );

    for (const { label, href } of [
      { label: "Discover", href: "/console/discover" },
      { label: "Drafts", href: "/console/drafts" },
      { label: "Artifacts", href: "/console/artifacts" },
      { label: "Deployments", href: "/console/deployments" },
      { label: "Runs", href: "/console/runs" },
      { label: "Results", href: "/console/results" },
    ]) {
      expect(screen.getByRole("link", { name: label })).toHaveAttribute("href", href);
    }
  });

  it("provides a keyboard skip link to the workspace main region", async () => {
    render(
      <MemoryRouter>
        <ConsoleShell
          connection={initialState()}
          onConnect={() => undefined}
          onDraftChange={() => undefined}
        >
          <p>Content</p>
        </ConsoleShell>
      </MemoryRouter>,
    );

    const skipLink = screen.getByRole("link", { name: "Skip to main content" });
    expect(skipLink).toHaveAttribute("href", "#console-workspace-main");

    await userEvent.tab();

    expect(skipLink).toHaveFocus();
  });
});
