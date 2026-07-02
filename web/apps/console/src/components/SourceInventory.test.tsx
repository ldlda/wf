import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, within, cleanup } from "@testing-library/react";
import { SourceInventory } from "./SourceInventory.js";
import type { SourceRecord } from "../app/state.js";

beforeEach(() => {
  cleanup();
});

afterEach(() => {
  cleanup();
});

const makeSource = (overrides: Partial<SourceRecord> & { id: string }): SourceRecord => ({
  kind: "tool",
  enabled: true,
  description: null,
  toolCount: 1,
  nodeSpecCount: 0,
  reducerCount: 0,
  promptCount: 0,
  resourceCount: 0,
  ...overrides,
});

describe("SourceInventory", () => {
  it("shows loading state", () => {
    render(<SourceInventory sources={[]} loading={true} error={null} />);
    expect(screen.getByTestId("sources-loading")).toHaveTextContent(
      "Loading sources\u2026",
    );
  });

  it("shows empty state when no sources", () => {
    render(<SourceInventory sources={[]} loading={false} error={null} />);
    expect(screen.getByTestId("sources-empty")).toHaveTextContent(
      "No workflow sources reported.",
    );
  });

  it("renders source rows with id, kind, and enabled status", () => {
    const sources = [
      makeSource({ id: "tools-core", kind: "tool", enabled: true }),
      makeSource({ id: "reducers-main", kind: "reducer", enabled: false }),
    ];
    render(<SourceInventory sources={sources} loading={false} error={null} />);

    expect(screen.getByTestId("source-id-tools-core")).toHaveTextContent(
      "tools-core",
    );
    expect(screen.getByTestId("source-kind-tools-core")).toHaveTextContent(
      "tool",
    );
    expect(
      screen.getByTestId("source-status-tools-core"),
    ).toHaveTextContent("enabled");
    expect(
      screen.getByTestId("source-status-reducers-main"),
    ).toHaveTextContent("disabled");
  });

  it("shows description when present", () => {
    const sources = [
      makeSource({
        id: "tools-core",
        description: "Core workflow tools",
      }),
    ];
    render(<SourceInventory sources={sources} loading={false} error={null} />);
    expect(screen.getByText("Core workflow tools")).toBeDefined();
  });

  it("renders total counts across categories", () => {
    const sources = [
      makeSource({
        id: "tools-core",
        toolCount: 5,
        nodeSpecCount: 3,
        reducerCount: 2,
        promptCount: 1,
        resourceCount: 4,
      }),
    ];
    render(<SourceInventory sources={sources} loading={false} error={null} />);

    expect(screen.getByTestId("source-tools-tools-core")).toHaveTextContent("5");
    expect(
      screen.getByTestId("source-nodes-tools-core"),
    ).toHaveTextContent("3");
    expect(
      screen.getByTestId("source-reducers-tools-core"),
    ).toHaveTextContent("2");
    expect(
      screen.getByTestId("source-prompts-tools-core"),
    ).toHaveTextContent("1");
    expect(
      screen.getByTestId("source-resources-tools-core"),
    ).toHaveTextContent("4");
  });

  it("renders error without replacing connection status", () => {
    render(
      <SourceInventory
        sources={[]}
        loading={false}
        error="Failed to load sources"
      />,
    );
    expect(screen.getByTestId("sources-error")).toHaveTextContent(
      "Failed to load sources",
    );
    expect(screen.getByTestId("sources-error")).toHaveAttribute(
      "role",
      "alert",
    );
  });
});
