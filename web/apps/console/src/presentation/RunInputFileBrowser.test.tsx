import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { RunInputFileBrowser } from "./RunInputFileBrowser.js";

afterEach(() => cleanup());

const renderBrowser = () => {
  const user = userEvent.setup();
  render(
    <RunInputFileBrowser
      selectedDocuments={["project-brief.md", "architecture-notes.md"]}
      boardPath="issue-board.json"
    />,
  );
  return { user };
};

describe("RunInputFileBrowser", () => {
  it("renders selected docs as an interactive file list", () => {
    render(
      <RunInputFileBrowser
        selectedDocuments={["docs/project-brief.md", "docs/architecture-notes.md"]}
        boardPath="artifacts/issue-board.json"
      />,
    );

    const browser = screen.getByRole("region", { name: /workflow input files/i });
    expect(within(browser).getByRole("heading", { name: "docs/" })).toBeInTheDocument();

    const files = within(browser).getByRole("list", { name: /included in prepared run/i });
    expect(within(files).getAllByRole("listitem")).toHaveLength(2);
    expect(within(files).getAllByText("selected")).toHaveLength(2);
    expect(within(files).getAllByRole("button")).toHaveLength(2);
    expect(within(files).queryAllByRole("link")).toHaveLength(0);
    for (const path of ["docs/project-brief.md", "docs/architecture-notes.md"]) {
      const row = within(files).getByText(path).closest("li");
      expect(row).not.toBeNull();
      expect(row).toHaveAttribute("data-file-path", path);
      expect(row).toHaveTextContent(/selected/i);
    }

    const destination = within(browser).getByRole("group", { name: /workflow output/i });
    expect(destination).toHaveTextContent("artifacts/issue-board.json");
  });

  it("previews the selected prepared fixture without calling it run evidence", async () => {
    const { user } = renderBrowser();

    expect(screen.getByRole("region", { name: /prepared fixture preview/i })).toHaveTextContent(
      /workflow substrate for ai-agent-facing workspace automation/i,
    );

    await user.click(screen.getByRole("button", { name: /architecture-notes\.md/i }));

    const preview = screen.getByRole("region", { name: /prepared fixture preview/i });
    expect(preview).toHaveTextContent(/architecture-notes\.md/i);
    expect(preview).toHaveTextContent(/fixture preview/i);
    expect(preview).toHaveTextContent(/not execution evidence/i);
  });

  it("shows an honest empty preview for files absent from the fixture catalog", () => {
    render(
      <RunInputFileBrowser
        selectedDocuments={["live-only.md"]}
        boardPath="issue-board.json"
      />,
    );

    expect(screen.getByRole("region", { name: /prepared fixture preview/i })).toHaveTextContent(
      /preview unavailable/i,
    );
  });
});
