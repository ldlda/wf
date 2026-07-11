export type DemoApprovalUiState = "ready" | "submitted" | "revision_requested";

export type DemoApprovalActions = {
  readonly state: DemoApprovalUiState;
  readonly canSubmit: boolean;
  readonly canRequestRevision: boolean;
  readonly submit: (
    selectedIssueIds?: ReadonlyArray<string>,
    comment?: string,
  ) => Promise<void>;
  readonly requestRevision: () => Promise<void>;
};
