import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { AppRoutes } from "./AppRoutes.js";

afterEach(() => cleanup());

describe("AppRoutes", () => {
  it.each([
    ["/", "Discover"],
    ["/console", "Discover"],
  ])("redirects %s to the discover workspace leaf", async (entry, label) => {
    render(
      <MemoryRouter initialEntries={[entry]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: label })).toBeInTheDocument();
  });

  it("keeps presentation routes outside console navigation", async () => {
    render(
      <MemoryRouter initialEntries={["/present"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(screen.getByRole("main", { name: /lda.chat presentation/i })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Workflow lifecycle" })).toBeNull();

    cleanup();
    window.location.hash = "#scene/thesis/title";
    render(
      <MemoryRouter initialEntries={["/presenter"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("main", { name: /lda.chat presenter notes/i }, { timeout: 5_000 }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Workflow lifecycle" })).toBeNull();
  });

  it("shows the connection prompt and pending route message while disconnected", () => {
    render(
      <MemoryRouter initialEntries={["/console/discover"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText("Workflow JSON-RPC URL")).toBeInTheDocument();
    expect(
      screen.getByText("Discover is unavailable until a workflow server is connected."),
    ).toBeInTheDocument();
    expect(screen.getByText("Connect a workflow server to view Discover.")).toBeInTheDocument();
  });

  it("navigates between lifecycle links without leaving the workspace shell", async () => {
    render(
      <MemoryRouter initialEntries={["/console/discover"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    await userEvent.click(screen.getByRole("link", { name: "Runs" }));

    expect(await screen.findByRole("heading", { name: "Runs" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Workflow lifecycle" })).toBeInTheDocument();
  });
});
