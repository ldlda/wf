import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DiscussionPanel } from "./DiscussionPanel.js";

afterEach(() => cleanup());

describe("DiscussionPanel", () => {
  const onClose = vi.fn();

  it("renders the branch title and claim class", () => {
    render(<DiscussionPanel branchId="hosted-automation" onClose={onClose} />);
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-label", "Hosted automation");
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

  it("shows hosted-automation detail paragraph", () => {
    render(<DiscussionPanel branchId="hosted-automation" onClose={onClose} />);
    expect(screen.getByText(/future scheduler/)).toBeDefined();
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
