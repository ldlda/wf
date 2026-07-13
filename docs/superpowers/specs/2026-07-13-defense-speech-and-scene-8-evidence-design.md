# Defense Speech And Scene 8 Product Evidence Design

## Purpose

The defense must be easy to say under time pressure and easy to understand for
an audience that has not read the thesis. The current opening script introduces
too many technical nouns before the demonstration gives them concrete meaning.
Scene 8 also presents a prepared validation failure that does not reproduce in
the current product.

This design separates two independently shippable changes:

1. simplify the spoken path through Scenes 1-8; and
2. replace Scene 8's sparse prepared visuals with compact product-result views
   based on reviewed `wf` output.

## Speech Contract

Each beat has one audience goal, one to three anchor terms, and one suggested
sentence. The anchor terms preserve the thesis vocabulary that identifies the
beat; the sentence is rehearsal help, not a word-for-word obligation. The
presenter may use optional notes during Q&A, but the timed path does not require
lists of architecture terms.

The simplified story is:

1. The title is the product ambition; the contribution is the platform below
   the agent.
2. A chat/tool transcript can finish a task, but it is not a reusable workflow.
3. Existing systems solve adjacent problems; this work does not replace them.
4. A planner decides; the runtime executes; the Workflow API is their public
   boundary.
5. A workflow moves through Draft, Artifact, Deployment, and Run.
6. Clients enter through Workflow API; WorkflowServer composes records,
   capabilities, and execution.
7. The demonstration is a prepared example, not a live autonomous planner.
8. The example discovers capabilities, authors a draft, diagnoses a missing
   route, repairs it, saves an artifact, and creates a deployment.

Terms such as provider neutrality, Workflow API, Draft, Artifact, Deployment,
Run, validation, and traces remain explicit anchor terms where they identify a
slide's purpose. More detailed terms such as source resolution, explicit resume
boundaries, and NodeUse remain available in visuals, optional notes, and Q&A.
They are not mandatory opening narration.

The target for Scenes 1-8 is approximately four minutes, including navigation.
The complete must-say path should remain comfortably below the previous 11-minute
target so the presenter can pause and recover without rushing.

## Reviewed Product Evidence

The prepared evidence remains deterministic. It does not call authoring RPCs
while the presentation is running. Its data is hardcoded from a reviewed live
CLI probe against:

```text
uv run wf-rpc-server \
  --config examples/lda_report_workflow/wf.config.json \
  --host 127.0.0.1 \
  --port 8765
```

The reviewed invalid result was produced by removing the `ok` route from the
`analyze` step and running:

```text
uv run wf --url http://127.0.0.1:8765/rpc \
  draft validate presentation_diag_probe2
```

The relevant result is:

```json
{
  "status": "invalid",
  "revision": 3,
  "diagnostics": [
    {
      "code": "missing_outcome_edge",
      "path": "nodes[analyze]",
      "message": "reachable node is missing edges for outcomes ['ok']",
      "details": {}
    }
  ]
}
```

`wf explain missing_outcome_edge` reports that the workflow cannot prove where
execution goes next and recommends routing each missing outcome, using
`__end__` for terminal outcomes.

The reviewed repair is:

```text
wf draft set-route lda_report_workflow \
  --revision 3 \
  --step analyze \
  --outcome ok \
  --to __end__
```

The follow-up validation result is `status: valid`, `revision: 4`, and
`diagnostics: []`.

The disposable probe workspace was deleted after capture.

## Scene 8 Visual Contract

Scene 8 remains a two-column prepared lifecycle surface with supporting chat on
the left and one dominant product result on the right. It does not copy the
full `/console` UI, but it uses the same evidence vocabulary: status, revision,
method, command, records, diagnostics, and bindings.

- Discover shows configured source IDs and one inspected capability contract.
- Draft shows workspace identity, revision, status, step count, route count,
  and the two-step graph.
- Diagnose shows an invalid status, diagnostic code, path, message, and compact
  explanation.
- Repair shows the exact route mutation, why it fixes the graph, and the valid
  follow-up result.
- Artifact shows immutable artifact ID, version, and required sources.
- Deployment shows deployment ID, source bindings, and runnable status.

Diagnose and Repair are two views of one factual validation sequence. Diagnose
does not reveal the successful result early. Repair retains enough diagnostic
context to make the transition understandable.

## Truth Boundaries

- Do not label the prepared authoring sequence as live execution.
- Do not claim that diagnostics automatically repair workflows.
- Do not claim that a missing output projection invalidates this draft; it did
  not reproduce in the current product.
- Do not expose the disposable probe workspace ID in the audience UI.
- The broader root-config server is useful for product exploration but is not
  the evidence source for the deterministic report-workflow scene.

## Verification

- Presenter tests enforce one note per beat, the reduced word budget, and
  synchronization with the readable runbook.
- Projection tests pin the reviewed diagnostic code, path, message, revision,
  exact public repair command, and valid follow-up state.
- Component tests verify each phase's dominant product-result surface and the
  Diagnose-to-Repair information boundary.
- Browser smoke covers all six Scene 8 beats at `1280x720`, `1024x768`, and
  `1920x1080`, including internal chat scrolling and no document overflow.
