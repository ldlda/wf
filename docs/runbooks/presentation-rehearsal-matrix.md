# Presentation Rehearsal Matrix

This is the route checklist for rehearsing the defense presentation, not a new
story or product contract. The route column is the captureable portion of the
hash: open it as `http://127.0.0.1:5173/present#scene/<route>`.

The evidence column points to the existing storyboard evidence pointer or the
runbook fallback. Do not claim output that is not present in that pointer. A
`replay-only` beat needs no live service; `live-capable` may use the live target
when available; `explicit run` requires the prepared workflow start operation
before its live evidence exists. Every fallback is a route in this matrix and
can be shown after selecting replay with the runbook's session-storage switch.

| Route | Say | Dominant visual | Supporting visual | Chat | Evidence mode | Fallback route |
|---|---|---|---|---|---|---|
| `thesis/title` | The project began as a pursuit of an AI agent for workspace automation. | Thesis title card | Substrate framing | hidden | replay-only; Thesis Abstract and Introduction | `thesis/title` |
| `thesis/substrate` | The implemented contribution is the typed workflow substrate an agent needs. | Substrate lifecycle card | Thesis framing | hidden | replay-only; Thesis Abstract and Introduction | `thesis/substrate` |
| `problem/direct-actions` | Direct tool actions can act without becoming reusable automation. | Problem contrast | Lifecycle vocabulary | hidden | replay-only; Thesis Problem Statement and Requirements | `problem/direct-actions` |
| `problem/missing-contracts` | Reusable automation needs schemas, persistence, traces, and recovery boundaries. | Contract checklist | Problem contrast | hidden | replay-only; Thesis Problem Statement and Requirements | `problem/missing-contracts` |
| `positioning/landscape` | Related systems solve different parts of the tool, script, workflow, and agent problem. | Related-systems landscape | Problem contracts | hidden | replay-only; Thesis Positioning and Related Systems | `positioning/landscape` |
| `positioning/lda-position` | lda.chat occupies the typed, provider-neutral workflow substrate niche for external agents. | lda.chat position map | Related-systems landscape | hidden | replay-only; Thesis Positioning and Related Systems | `positioning/lda-position` |
| `planner-runtime/planner` | An external planner proposes and revises workflow structure. | Planner side of boundary | Typed operations | hidden | replay-only; Thesis Architecture Overview | `planner-runtime/planner` |
| `planner-runtime/runtime` | The runtime validates, executes, records, and resumes the proposal deterministically. | Runtime side of boundary | Lifecycle records | hidden | replay-only; Thesis Architecture Overview | `planner-runtime/runtime` |
| `planner-runtime/boundary` | Typed CLI and JSON-RPC operations make the planner/runtime boundary explicit. | Boundary diagram | CLI and RPC surface | hidden | replay-only; Thesis Architecture Overview | `planner-runtime/boundary` |
| `lifecycle/draft` | Draft is mutable iterative authoring state. | Lifecycle stage: Draft | State transition strip | hidden | replay-only; Thesis Workflow Lifecycle | `lifecycle/draft` |
| `lifecycle/artifact` | Artifact is the immutable saved workflow definition. | Lifecycle stage: Artifact | State transition strip | hidden | replay-only; Thesis Workflow Lifecycle | `lifecycle/artifact` |
| `lifecycle/deployment` | Deployment binds logical requirements to concrete sources. | Lifecycle stage: Deployment | Binding relationship | hidden | replay-only; Thesis Workflow Lifecycle | `lifecycle/deployment` |
| `lifecycle/run` | Run is persisted execution with output, status, and trace. | Lifecycle stage: Run | Evidence record chain | hidden | replay-only; Thesis Workflow Lifecycle | `lifecycle/run` |
| `architecture/client` | Human and agent clients use the same public lifecycle surface. | Architecture client node | System architecture figure | hidden | replay-only; Thesis System Architecture; `docs/project_map.md`; `docs/source_architecture.md` | `architecture/client` |
| `architecture/api` | JSON-RPC reaches WorkflowApi without owning domain behavior. | Architecture API node | Client operations | hidden | replay-only; Thesis System Architecture; `docs/project_map.md`; `docs/source_architecture.md` | `architecture/api` |
| `architecture/runtime` | Runtime resolves provider-neutral capabilities and stores lifecycle records. | Runtime/providers focus | Architecture overview | hidden | replay-only; Thesis System Architecture; `docs/project_map.md`; `docs/source_architecture.md` | `architecture/runtime` |
| `architecture/node-use` | A NodeUse validates input, invokes a capability, and reduces output into state. | NodeUse focus | Runtime/providers focus | hidden | replay-only; Thesis System Architecture; `docs/project_map.md`; `docs/source_architecture.md` | `architecture/node-use` |
| `authoring/discover` | Discovery lets an operator inspect capabilities and schemas before authoring. | Authoring discovery surface | Capability/schema list | hidden | replay-only; CLI documentation; draft authoring API; challenge UX findings | `authoring/discover` |
| `authoring/author` | Focused operations build and connect the draft. | Draft authoring surface | Workflow structure | hidden | replay-only; CLI documentation; draft authoring API; challenge UX findings | `authoring/author` |
| `authoring/diagnose` | Structured diagnostics identify invalid state instead of leaving the agent to guess. | Diagnostic receipt | Draft authoring surface | hidden | replay-only; CLI documentation; draft authoring API; challenge UX findings | `authoring/diagnose` |
| `authoring/repair` | Repair hints lead from invalid draft state to a valid compiled workflow. | Repair guidance | Diagnostic receipt | hidden | replay-only; CLI documentation; draft authoring API; challenge UX findings | `authoring/repair` |
| `agent-handoff/request` | The thin agent interface receives the report request while the platform owns execution. | Agent request surface | Workflow substrate framing | hidden | replay-only; Constrained demo agent and prepared replay recipe | `agent-handoff/request` |
| `prepared-lifecycle/discover` | The prepared example starts by inspecting its available sources, capabilities, and schemas. | Prepared lifecycle: discovery | Capability/schema evidence | hidden | replay-only; `examples/lda_report_workflow`; deployment inspect replay evidence | `prepared-lifecycle/discover` |
| `prepared-lifecycle/draft` | The example creates a report workflow draft with its steps and routes. | Prepared lifecycle: draft | Workflow definition | hidden | replay-only; `examples/lda_report_workflow`; deployment inspect replay evidence | `prepared-lifecycle/draft` |
| `prepared-lifecycle/validate` | Binding and validation diagnose and repair the prepared draft. | Prepared lifecycle: validation | Diagnostic evidence | hidden | replay-only; `examples/lda_report_workflow`; deployment inspect replay evidence | `prepared-lifecycle/validate` |
| `prepared-lifecycle/artifact` | The validated draft compiles into an immutable artifact. | Prepared lifecycle: artifact | Lifecycle state | hidden | replay-only; `examples/lda_report_workflow`; deployment inspect replay evidence | `prepared-lifecycle/artifact` |
| `prepared-lifecycle/deployment` | Deployment bindings are saved and readiness is validated before a run. | Prepared lifecycle: deployment | Binding/readiness evidence | hidden | replay-only; `examples/lda_report_workflow`; deployment inspect replay evidence | `prepared-lifecycle/deployment` |
| `run-from-deployment/input` | The run begins from selected documents and an issue-board path. | Workflow input panel | Prepared deployment | hidden | live-capable; `workflow.runs.start` replay evidence | `prepared-lifecycle/deployment` |
| `run-from-deployment/operation` | A public operation starts a durable workflow run. | Start operation | Workflow graph | hidden | explicit run; `workflow.runs.start` replay evidence | `run-from-deployment/operation` |
| `run-from-deployment/graph` | The run follows a reusable workflow graph, not a chat transcript. | Workflow graph | Run operation receipt | hidden | live-capable; `workflow.runs.start` replay evidence | `run-from-deployment/operation` |
| `typed-human-boundary/interrupt` | Execution reaches a declared issue-review boundary with a typed interrupt payload. | Interrupt boundary | Workflow graph | hidden | live-capable; typed interrupt payload and resume contract | `run-from-deployment/operation` |
| `typed-human-boundary/approval` | The operator chooses a submitted or revision-requested outcome for the paused run. | Approval decision surface | Interrupt payload | hidden | live-capable; typed interrupt payload and resume contract | `typed-human-boundary/approval` |
| `resume-output-evidence/resume` | The submitted payload resumes the same persisted run. | Resume operation | Approval decision | hidden | live-capable; `workflow.runs.resume`, workflow output, and trace replay evidence | `typed-human-boundary/approval` |
| `resume-output-evidence/output` | The workflow produces the report and issue-board changes. | Output evidence | Resume operation | hidden | live-capable; `workflow.runs.resume`, workflow output, and trace replay evidence | `resume-output-evidence/output` |
| `resume-output-evidence/trace` | Trace frames and protocol evidence remain inspectable after completion. | Trace evidence | Output evidence | hidden | live-capable; `workflow.runs.resume`, workflow output, and trace replay evidence | `resume-output-evidence/trace` |
| `evaluation/cohort` | The evaluation covers 36 audited trials across models, profiles, challenges, and waves. | Evaluation cohort summary | Trial breakdown | hidden | replay-only; Thesis Evaluation and Appendix C | `evaluation/cohort` |
| `evaluation/validity` | Manual audit separates task completion from valid product-surface evidence. | Validity boundary | Evaluation cohort | hidden | replay-only; Thesis Evaluation and Appendix C | `evaluation/validity` |
| `evaluation/findings` | The trials exposed concrete authoring and diagnostic UX gaps. | Findings summary | Validity boundary | hidden | replay-only; Thesis Evaluation and Appendix C | `evaluation/findings` |
| `conclusion/limits` | The prototype is not a production sandbox, scheduler, or broad agent benchmark. | Contribution boundary | Evaluation findings | hidden | replay-only; Thesis Limitations, Future Work, and Conclusion | `conclusion/limits` |
| `conclusion/future` | A live LLM interface, scheduling, and broader evaluation remain future work. | Future-work layers | Contribution boundary | hidden | replay-only; Thesis Limitations, Future Work, and Conclusion | `conclusion/future` |
| `conclusion/conclusion` | The typed substrate makes reusable agent-operated automation inspectable. | Conclusion contribution card | Planner/runtime boundary | hidden | replay-only; Thesis Limitations, Future Work, and Conclusion | `conclusion/conclusion` |
| `conclusion/questions` | The final beat hands the discussion to the examiner using the prepared Q&A branches. | Questions card | Defense Q&A | hidden | replay-only; Thesis Limitations, Future Work, and Conclusion | `conclusion/questions` |

For live-capable and explicit-run beats, use the existing `Live Demo
Fallbacks` section in [`defense-presentation.md`](defense-presentation.md) when
the live target or RPC server is unavailable. The fallback routes above are
replay evidence, not fresh live results.
