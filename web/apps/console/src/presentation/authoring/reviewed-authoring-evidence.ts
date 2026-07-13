import type { PreparedLifecycleStepId } from "./authoring-projection.js";

export type ReviewedAuthoringEvidence =
  | {
      readonly kind: "inventory";
      readonly sourceCount: 6;
      readonly sources: readonly string[];
      readonly capability: {
        readonly name: string;
        readonly inputs: readonly string[];
        readonly outputs: readonly string[];
        readonly outcomes: readonly string[];
      };
    }
  | {
      readonly kind: "draft";
      readonly workspaceId: "lda_report_workflow";
      readonly revision: 2;
      readonly status: "valid";
      readonly stepCount: 2;
      readonly routeCount: 2;
      readonly steps: readonly string[];
      readonly routes: readonly string[];
    }
  | {
      readonly kind: "diagnostic";
      readonly workspaceId: "lda_report_workflow";
      readonly revision: 3;
      readonly status: "invalid";
      readonly diagnostic: {
        readonly code: "missing_outcome_edge";
        readonly path: "nodes[analyze]";
        readonly message: string;
        readonly explanation: string;
      };
      readonly faultInjection: {
        readonly command: string;
        readonly fromRevision: 2;
        readonly toRevision: 3;
        readonly label: "prepared fault injection";
      };
    }
  | {
      readonly kind: "repair";
      readonly fromRevision: 3;
      readonly toRevision: 4;
      readonly command: string;
      readonly status: "valid";
      readonly diagnosticCount: 0;
    }
  | {
      readonly kind: "artifact";
      readonly artifactId: "lda_report_case_study";
      readonly version: 1;
      readonly immutable: true;
      readonly requiredSources: readonly string[];
    }
  | {
      readonly kind: "deployment";
      readonly deploymentId: "lda_report_case_study.default";
      readonly status: "runnable";
      readonly bindings: readonly {
        readonly requirement: string;
        readonly source: string;
      }[];
    };

export type ReviewedAuthoringStep = {
  readonly step: PreparedLifecycleStepId;
  readonly evidence: ReviewedAuthoringEvidence;
};

const localSourceIds = [
  "local.lda_docs",
  "local.lda_report",
  "local.issue_board",
] as const;

// This catalog is static by design: presentation playback uses reviewed CLI facts,
// rather than invoking authoring or exposing disposable probe workspace IDs.
const reviewedAuthoringEvidence: Readonly<
  Record<PreparedLifecycleStepId, ReviewedAuthoringEvidence>
> = {
  discover: {
    kind: "inventory",
    sourceCount: 6,
    sources: localSourceIds,
    capability: {
      name: "local.lda_report.analyze_documents",
      inputs: ["documents"],
      outputs: ["analysis"],
      outcomes: ["ok"],
    },
  },
  draft: {
    kind: "draft",
    workspaceId: "lda_report_workflow",
    revision: 2,
    status: "valid",
    stepCount: 2,
    routeCount: 2,
    steps: ["read_documents", "analyze"],
    routes: ["read_documents.ok -> analyze", "analyze.ok -> __end__"],
  },
  diagnose: {
    kind: "diagnostic",
    workspaceId: "lda_report_workflow",
    revision: 3,
    status: "invalid",
    diagnostic: {
      code: "missing_outcome_edge",
      path: "nodes[analyze]",
      message: "reachable node is missing edges for outcomes ['ok']",
      explanation: "The workflow cannot prove where execution goes next.",
    },
    faultInjection: {
      command:
        "wf draft remove-route lda_report_workflow --revision 2 --step analyze --outcome ok",
      fromRevision: 2,
      toRevision: 3,
      label: "prepared fault injection",
    },
  },
  repair: {
    kind: "repair",
    fromRevision: 3,
    toRevision: 4,
    command:
      "wf draft set-route lda_report_workflow --revision 3 --step analyze --outcome ok --to __end__",
    status: "valid",
    diagnosticCount: 0,
  },
  artifact: {
    kind: "artifact",
    artifactId: "lda_report_case_study",
    version: 1,
    immutable: true,
    requiredSources: localSourceIds,
  },
  deployment: {
    kind: "deployment",
    deploymentId: "lda_report_case_study.default",
    status: "runnable",
    bindings: localSourceIds.map((source) => ({
      requirement: source,
      source,
    })),
  },
};

export const reviewedAuthoringEvidenceFor = (
  step: PreparedLifecycleStepId,
): ReviewedAuthoringEvidence => reviewedAuthoringEvidence[step];
