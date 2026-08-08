import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup } from "@testing-library/react";
import { RecordColumns } from "./RecordColumns.js";

afterEach(() => cleanup());

describe("RecordColumns", () => {
  it("uses presentation wrappers for listbox options", () => {
    render(
      <RecordColumns
        artifacts={[{
          key: "report@1",
          artifactId: "report",
          version: 1,
          kind: "workflow",
          displayName: "Report",
          description: null,
          outcomes: [],
          requiredSources: [],
          diagnosticCount: 0,
        }]}
        deployments={[{
          id: "report.default",
          artifactId: "report",
          artifactVersion: 1,
          bindingCount: 0,
          driftPolicy: "strict",
        }]}
        runs={[{
          runId: "run_123",
          deploymentId: "report.default",
          artifactId: "report",
          artifactVersion: 1,
          status: "succeeded",
          resumeReadiness: "not_applicable",
          diagnosticCount: 0,
        }]}
        selectedArtifactId={null}
        selectedDeploymentId={null}
        selectedRunId={null}
        primaryKind="artifact"
        onSelectArtifact={() => undefined}
        onSelectDeployment={() => undefined}
        onSelectRun={() => undefined}
      />,
    );

    for (const listbox of screen.getAllByRole("listbox")) {
      expect(Array.from(listbox.children)).toHaveLength(1);
      expect(listbox.children[0]).toHaveAttribute("role", "presentation");
    }
    expect(screen.getAllByRole("option")).toHaveLength(3);
  });
});
