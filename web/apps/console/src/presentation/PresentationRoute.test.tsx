import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PresentationRoute } from "./PresentationRoute.js";

afterEach(() => cleanup());

describe("PresentationRoute", () => {
  it("renders the presentation stage entry point", () => {
    render(<PresentationRoute />);

    expect(screen.getByRole("main", { name: /lda.chat presentation/i })).toBeInTheDocument();
    expect(screen.getByText(/planner decisions/i)).toBeInTheDocument();
  });
});
