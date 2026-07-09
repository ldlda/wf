export type DemoApprovalUiState = "ready" | "submitted" | "cancelled";

export type DemoApprovalActions = {
  readonly state: DemoApprovalUiState;
  readonly canSubmit: boolean;
  readonly canCancel: boolean;
  readonly submit: () => Promise<void>;
  readonly cancel: () => Promise<void>;
};
