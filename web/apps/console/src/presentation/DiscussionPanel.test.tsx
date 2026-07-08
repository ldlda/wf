import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DiscussionPanel } from "./DiscussionPanel.js";

afterEach(() => cleanup());

describe("DiscussionPanel", () => {
  const onClose = vi.fn();

  beforeEach(() => {
    onClose.mockClear();
  });

  it("renders the branch title and claim class", () => {
    render(<DiscussionPanel branchId="hosted-automation" onClose={onClose} />);
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-label", "Hosted automation");
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
    expect(screen.getByText("Hosted automation")).toBeDefined();
    expect(screen.getByText("future-work")).toBeDefined();
  });

  it("returns null for an unknown branch", () => {
    const { container } = render(
      <DiscussionPanel branchId="nonexistent" onClose={onClose} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("calls onClose when the return button is clicked", async () => {
    render(<DiscussionPanel branchId="hosted-automation" onClose={onClose} />);
    await userEvent.click(screen.getByRole("button", { name: /return/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("focuses the return button and closes on Escape", async () => {
    render(<DiscussionPanel branchId="hosted-automation" onClose={onClose} />);

    const returnButton = screen.getByRole("button", { name: /return/i });
    expect(document.activeElement).toBe(returnButton);

    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("traps tab focus inside the dialog", async () => {
    render(<DiscussionPanel branchId="mcp-agent-scale" onClose={onClose} />);

    const firstLink = screen.getByRole("link", { name: "Anthropic MCP" });
    const returnButton = screen.getByRole("button", { name: /return/i });
    returnButton.focus();

    await userEvent.tab();
    expect(document.activeElement).toBe(firstLink);

    await userEvent.tab({ shift: true });
    expect(document.activeElement).toBe(returnButton);
  });

  it("shows hosted-automation detail paragraph", () => {
    render(<DiscussionPanel branchId="hosted-automation" onClose={onClose} />);
    expect(screen.getByText(/future scheduler/)).toBeDefined();
  });

  it("renders defense Q&A fields when present", () => {
    render(<DiscussionPanel branchId="where-is-ai-agent" onClose={onClose} />);

    expect(screen.getByText("Where is the AI agent in this thesis?")).toBeDefined();
    expect(screen.getByText(/workflow substrate that external agents operate/i)).toBeDefined();
    expect(screen.getByText(/not a new planning algorithm/i)).toBeDefined();
    expect(screen.getByText(/Answer directly first/i)).toBeDefined();
  });

  it("renders speaker hints as presenter notes instead of answer content", () => {
    render(<DiscussionPanel branchId="where-is-ai-agent" onClose={onClose} />);

    const note = screen.getByLabelText("presenter note");
    expect(note).toHaveTextContent(/Answer directly first/i);
    expect(note).toHaveTextContent(/Presenter note/i);
  });

  it("shows mcp-agent-scale links to Anthropic and Cloudflare", () => {
    render(<DiscussionPanel branchId="mcp-agent-scale" onClose={onClose} />);
    const anthropic = screen.getByText("Anthropic MCP");
    const cloudflare = screen.getByText("Cloudflare Code Mode");
    expect(anthropic).toBeDefined();
    expect(cloudflare).toBeDefined();
    expect((anthropic as HTMLAnchorElement).href).toBe(
      "https://www.anthropic.com/engineering/code-execution-with-mcp",
    );
    expect((cloudflare as HTMLAnchorElement).href).toBe(
      "https://blog.cloudflare.com/code-mode-mcp/",
    );
  });
});
