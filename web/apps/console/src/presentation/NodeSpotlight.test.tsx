import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NodeSpotlight } from "./NodeSpotlight.js";

afterEach(() => cleanup());

describe("NodeSpotlight", () => {
  it("uses a readable fallback for raw interrupt nodes without labels", () => {
    render(<NodeSpotlight nodeId="review_issues" close={vi.fn()} />);

    expect(screen.getByRole("dialog", { name: "Review issues" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Review issues" })).toBeInTheDocument();
  });
});
