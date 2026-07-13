import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { PresenterRoute } from "./PresenterRoute.js";

afterEach(() => {
  cleanup();
  window.location.hash = "";
});

describe("PresenterRoute", () => {
  it("renders the first presenter note without audience runtime surfaces", () => {
    window.location.hash = "#scene/thesis/title";
    render(<PresenterRoute />);
    expect(screen.getByRole("main", { name: /lda.chat presenter notes/i })).toBeInTheDocument();
    expect(screen.getByText(/This project began with the goal/i)).toBeInTheDocument();
    expect(screen.getByText("the system underneath the chat").tagName).toBe("STRONG");
    expect(screen.getByRole("navigation", { name: /presenter note navigation/i })).toHaveTextContent("1 / 39");
    expect(screen.getByRole("link", { name: "Next →" })).toHaveAttribute("href", "#scene/thesis/substrate");
    expect(screen.getByRole("link", { name: /open audience slide/i })).toHaveAttribute("href", "/present#scene/thesis/title");
    expect(screen.queryByText(/live target/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /run prepared workflow/i })).not.toBeInTheDocument();
  });

  it("keeps covered state local to the route", async () => {
    window.location.hash = "#scene/thesis/title";
    render(<PresenterRoute />);
    const checkbox = screen.getByRole("checkbox", { name: /mark covered/i });
    await userEvent.click(checkbox);
    expect(checkbox).toBeChecked();
  });

  it("navigates notes with arrow keys", () => {
    window.location.hash = "#scene/thesis/title";
    render(<PresenterRoute />);
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(window.location.hash).toBe("#scene/thesis/substrate");
  });

  it("renders Q&A speaker guidance only in presenter mode", () => {
    window.location.hash = "#discuss/where-is-ai-agent";
    render(<PresenterRoute />);
    expect(screen.getByRole("heading", { name: /Where is the AI agent/i })).toBeInTheDocument();
    expect(screen.getByText(/Answer directly first/i)).toBeInTheDocument();
    expect(screen.getByText(/Abstract; Chapter 1 framing/i)).toBeInTheDocument();
    expect(screen.getByText(/Defense Q&A/i).closest("details")).toHaveAttribute("open");
    expect(screen.getByRole("link", { name: /Where is the AI agent in this thesis/i })).toHaveAttribute("aria-current", "page");
  });
});
