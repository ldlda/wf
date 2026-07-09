export type DemoApprovalUiState = "ready" | "submitted" | "cancelled";

export type DemoApprovalActions = {
  readonly state: DemoApprovalUiState;
  readonly canSubmit: boolean;
  readonly canCancel: boolean;
  readonly submit: (
    selectedIssueIds?: ReadonlyArray<string>,
    comment?: string,
  ) => Promise<void>;
  readonly cancel: () => Promise<void>;
};
