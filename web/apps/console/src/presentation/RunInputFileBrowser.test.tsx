import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { RunInputFileBrowser } from "./RunInputFileBrowser.js";

afterEach(() => cleanup());

describe("RunInputFileBrowser", () => {
  it("renders the selected docs paths as factual readable files", () => {
    render(
      <RunInputFileBrowser
        selectedDocuments={["docs/project-brief.md", "docs/architecture-notes.md"]}
        boardPath="artifacts/issue-board.json"
      />,
    );

    const browser = screen.getByRole("region", { name: /workflow input files/i });
    expect(within(browser).getByRole("heading", { name: "docs/" })).toBeInTheDocument();

    const files = within(browser).getByRole("list", { name: /selected for this run/i });
    expect(within(files).getAllByRole("listitem")).toHaveLength(2);
    for (const path of ["docs/project-brief.md", "docs/architecture-notes.md"]) {
      const row = within(files).getByText(path).closest("li");
      expect(row).not.toBeNull();
      expect(row).toHaveAttribute("data-file-path", path);
      expect(row).toHaveTextContent(/selected|read/i);
    }

    const destination = within(browser).getByRole("group", { name: /workflow output/i });
    expect(destination).toHaveTextContent("artifacts/issue-board.json");
  });

  it("does not invent file metadata or contents", () => {
    render(
      <RunInputFileBrowser
        selectedDocuments={["docs/project-brief.md"]}
        boardPath="issue-board.json"
      />,
    );

    const browser = screen.getByRole("region", { name: /workflow input files/i });
    expect(within(browser).queryByText(/\b\d+(?:\.\d+)?\s*(?:kb|mb|bytes)\b/i)).not.toBeInTheDocument();
    expect(within(browser).queryByText(/preview|modified|created|content/i)).not.toBeInTheDocument();
  });
});
