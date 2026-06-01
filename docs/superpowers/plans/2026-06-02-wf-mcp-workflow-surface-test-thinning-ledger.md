# wf_mcp Workflow Surface Test Thinning Ledger

This ledger records every `wf_mcp.workflow_surface` test removed or kept during
the thinning pass. Do not delete a test unless the `replacement` column points
to equal-or-stronger coverage.

| Test | Decision | Replacement / Reason |
| --- | --- | --- |
| test_artifacts::test_workflow_surface_lists_artifact_catalog_entries | keep | Handler adapter smoke test for compact artifact listing; reduced to minimal assertions. |
| test_artifacts::test_workflow_surface_pages_and_filters_artifact_catalog_entries | remove | Covered by WorkflowArtifactApi list tests plus wf_api.listing pagination tests; handler keeps one list_artifacts smoke test. |
| test_capabilities::test_workflow_surface_lists_planner_visible_capabilities | keep | Handler list smoke test; reduced to minimal adapter-path assertions. |
| test_capabilities::test_workflow_surface_filters_stdlib_capabilities_by_source | remove | Covered by WorkflowCapabilityApi source/query filtering; handler list smoke remains. |
| test_capabilities::test_workflow_surface_call_capability_returns_structured_error | keep | Protected: MCP/service behavior — structured error on capability call failure. |
| test_capabilities::test_workflow_surface_lists_saved_wrapper_capabilities | remove | Covered by WorkflowCapabilityApi saved wrapper list tests. |
| test_capabilities::test_workflow_surface_inspects_one_capability | keep | Handler inspect smoke test; ensures adapter path works for single capability inspection. |
| test_capabilities::test_workflow_surface_inspect_capability_includes_wrapper_hints | keep | Protected: MCP/service behavior — wrapper hints detail through handler. |
| test_capabilities::test_workflow_surface_inspects_saved_wrapper_capability | remove | Covered by WorkflowCapabilityApi saved wrapper inspect tests. |
| test_capabilities::test_workflow_surface_does_not_auto_map_raw_mcp_content_blocks | keep | Protected: MCP content-block mapping behavior. |
| test_deployments::test_workflow_surface_validates_deployment_dependencies | keep | Handler-level dependency validation has stronger next-action assertions than wf_api. |
| test_deployments::test_workflow_surface_validate_deployment_live_check_is_opt_in | keep | Protected: MCP service adapter — live check is opt-in. |
| test_deployments::test_workflow_surface_validate_deployment_live_check_reports_unreachable_source | keep | Protected: MCP service adapter — unreachable source reporting. |
| test_deployments::test_workflow_surface_validate_deployment_live_check_reports_missing_connection | keep | Protected: MCP service adapter — missing connection reporting. |
| test_deployments::test_workflow_surface_records_artifact_and_deployment_save_events | keep | Protected: service event recording. |
| test_deployments::test_workflow_surface_save_deployment_accepts_deployment_id_alias | keep | Protected: request alias normalization. |
| test_deployments::test_workflow_surface_deletes_deployment | keep | Protected: delete event recording. |
| test_deployments::test_workflow_surface_save_deployment_rejects_id_and_deployment_id | keep | Protected: XOR validation on id/deployment_id. |
| test_deployments::test_workflow_surface_lists_compact_deployment_summaries_and_inspects_detail | keep | Protected: compact-vs-detail response shape. |
| test_drafts::test_workflow_surface_validates_draft_without_saving | remove | Covered by WorkflowDraftApi.validate_draft via test_delegation_smoke_validate_draft_equivalence. |
| test_drafts::test_workflow_surface_rejects_unknown_draft_route_outcome_when_spec_is_known | keep | Live outcome lookup through handler; not duplicated in wf_api. |
| test_drafts::test_workflow_surface_creates_artifact_from_draft_with_binding_suggestions | keep | Binding suggestions and artifact persistence through handler. |
| test_drafts::test_workflow_surface_draft_artifact_requires_std_self_binding | keep | binding_missing diagnostic through handler/deployment integration. |
| test_drafts::test_workflow_surface_patches_draft_without_saving | remove | Covered by WorkflowDraftApi.patch_draft. |
| test_drafts::test_workflow_surface_creates_and_gets_draft_workspace | remove | Covered by WorkflowDraftApi.create_draft_workspace and get_draft_workspace assertions in tests/wf_api/test_drafts_service.py. |
| test_drafts::test_workflow_surface_lists_draft_workspaces | remove | Covered by tests/wf_api/test_drafts_service.py::test_list_draft_workspaces_returns_sorted_summaries_without_drafts. |
| test_drafts::test_workflow_surface_deletes_draft_workspace | remove | Covered by tests/wf_api/test_drafts_service.py::test_delete_draft_workspace_is_idempotent. |
| test_drafts::test_workflow_surface_patch_helpers_update_draft_workspace | remove | Covered by tests/wf_api/test_drafts_service.py::test_draft_workspace_patch_helpers_update_revision_and_bindings. |
| test_drafts::test_workflow_surface_validates_draft_workspace_with_live_outcomes | keep | Live outcome lookup through handler/service stack. |
| test_drafts::test_workflow_surface_patches_draft_workspace_by_revision | remove | Covered by WorkflowDraftApi.patch_draft_workspace. |
| test_drafts::test_workflow_surface_creates_minimal_draft_workspace_with_error_route | keep | MCP request model parsing and error route generation. |
| test_drafts::test_workflow_surface_minimal_draft_honors_explicit_error_message_source | keep | Explicit error_message_source handling. |
| test_drafts::test_minimal_draft_request_accepts_structural_error_message_source | keep | MCP Pydantic model validation (CreateMinimalDraftWorkspaceRequest). |
| test_drafts::test_workflow_surface_accepts_canonical_bindings_for_minimal_workspace | keep | Canonical InputPathBinding/OutputBinding through handler. |
| test_drafts::test_workflow_surface_creates_draft_workspace_from_capability_hints | keep | Wrapper hints and next-actions through handler. |
| test_drafts::test_workflow_surface_creates_artifact_from_workspace | keep | Artifact persistence with schema snapshots through handler. |
| test_drafts::test_workflow_surface_workspace_artifact_infers_raw_concrete_dependency | keep | Source dependency inference through handler. |
| test_drafts::test_workflow_surface_creates_wrapper_from_workspace | keep | Wrapper creation through handler. |
| test_drafts::test_workflow_surface_low_confidence_draft_returns_patch_guidance | keep | Next-action guidance with patch examples through handler. |
| test_runs::test_raw_workflow_plan_uses_core_step_and_edge_models | keep | DEVIATION: Plan said wf_api covers this, but test_raw_workflow_plan_extraction.py only tests imports (canonical, compat, identity). The surface test is the only one exercising actual RawWorkflowPlan step/edge model parsing. Kept to avoid coverage gap. |
| test_runs::test_workflow_surface_runs_non_interrupting_deployment | keep | Persisted run records, trace slicing, response model, next-actions. |
| test_runs::test_workflow_surface_failed_deployment_exposes_error_on_run_and_inspect | keep | Failed run error exposure and inspect_run. |
| test_runs::test_workflow_surface_run_deployment_can_include_trace_detail | keep | Protected: MCP TraceRange, RunDeploymentResult model validation. |
| test_runs::test_workflow_surface_run_deployment_can_read_empty_trace_range | keep | Protected: empty trace range behavior. |
| test_runs::test_workflow_surface_runs_deployment_with_bound_node_spec_dependency | keep | Protected: logical source binding. |
| test_runs::test_workflow_surface_runs_artifact_created_from_concrete_node_ref | keep | Protected: concrete node ref artifact creation and run. |
| test_runs::test_workflow_surface_detects_drift_from_saved_node_spec_snapshot | keep | Protected: schema drift detection. |
| test_runs::test_workflow_surface_runs_deployment_with_bound_reducer_dependency | keep | Protected: reducer dependency integration. |
| test_wrappers::test_workflow_surface_creates_wrapper_artifact_from_plan | keep | Handler integration: wrapper artifact creation from plan. |
| test_wrappers::test_workflow_surface_creates_artifact_with_logical_node_refs | keep | Handler integration: logical node ref resolution. |
| test_wrappers::test_workflow_surface_calls_saved_wrapper_artifact | keep | Handler integration: saved wrapper direct call. |
| test_wrappers::test_workflow_surface_calls_live_node_spec_with_self_describing_response | keep | Handler integration: live node spec call. |
| test_wrappers::test_workflow_surface_calls_saved_wrapper_artifact_with_deployment_bindings | keep | Protected: saved wrapper call with deployment bindings. |
| test_next_actions::test_next_actions_from_high_confidence_wrapper_hints_can_validate | keep | NextActions model unit test. |
| test_next_actions::test_next_actions_from_low_confidence_wrapper_hints_can_patch | keep | NextActions model unit test. |
| test_next_actions::test_next_actions_from_runnable_deployment_recommends_run | keep | NextActions model unit test. |
| test_next_actions::test_next_actions_from_unrunnable_deployment_recommends_validation_retry | keep | NextActions model unit test. |
| test_next_actions::test_next_actions_from_completed_run_has_no_required_next_tool | keep | NextActions model unit test. |
| test_next_actions::test_next_actions_from_failed_run_recommends_bounded_trace | keep | NextActions model unit test. |
| test_next_actions::test_next_actions_from_interrupted_run_recommends_resume | keep | NextActions model unit test. |
| test_next_actions::test_workflow_surface_next_actions_shim_reexports_canonical_model | keep | Shim re-export verification. |
