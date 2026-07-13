# Authoring Lifecycle Diagram Pass

## Goal

Make Scene 8's prepared authoring lifecycle easier to present without returning
to the older dense split-screen composition. Each beat should contain one large,
immediately legible diagram and a compact factual receipt derived from the same
reviewed evidence already used by the scene.

The result should preserve the current unclipped, spacious layout while making
the empty space explain a lifecycle transformation.

## Design Direction

Scene 8 uses one continuous visual language across all six beats:

- diagram nodes represent workflow or lifecycle objects;
- solid connectors represent existing relationships;
- an open or interrupted connector represents a typed validation failure;
- a newly completed connector represents the repair;
- object identity persists between adjacent beats so the audience sees a
  transformation rather than six unrelated result cards;
- exact product facts remain visible as a compact receipt, not as the primary
  composition.

The prepared assistant remains supporting context. It must not reclaim the
screen area needed by the lifecycle diagram.

## Beat Compositions

### Discover

Show the three configured local source IDs feeding one capability contract.
The contract exposes its input, output, and outcome shape. The source inventory
count and capability name remain in the receipt.

The audience-facing claim is: agents discover typed capabilities before they
author a workflow.

### Draft

Show a large workflow graph:

```text
read_documents --ok--> analyze --ok--> END
```

The step input projection appears on the first connector. Revision, workspace
ID, step count, and route count remain in the receipt. The diagram should reuse
the established workflow graph vocabulary without introducing an independent
graph data model.

The audience-facing claim is: the draft is a mutable, inspectable workflow
structure rather than a hidden chat transcript.

### Diagnose

Reuse the Draft graph in the same spatial arrangement. Render the
`analyze.ok` route as an incomplete connection that stops before `END`. Place
the typed diagnostic beside that break, including its code and path.

The prepared fault-injection command remains available as secondary evidence,
but it must not compete with the broken route.

The audience-facing claim is: validation identifies a concrete graph defect and
the exact location that needs repair.

### Repair

Preserve the Diagnose composition and complete the missing connection. The
route changes from interrupted to valid, revision 3 becomes revision 4, and the
diagnostic count becomes zero. Motion may draw or reveal the repaired segment,
but the final state must remain fully visible when motion is disabled.

The audience-facing claim is: repair is a focused mutation followed by
deterministic revalidation.

### Artifact

Show the repaired draft transforming into a locked, immutable artifact. The
artifact retains the workflow silhouette while gaining an identity and version.
Required source contracts remain visibly attached to it rather than appearing
as an unrelated list.

The receipt contains the artifact ID, version, and exact required source IDs.

The audience-facing claim is: an artifact freezes a validated workflow
definition into a reusable version.

### Deployment

Show the artifact requirements on the left, their concrete configured source
bindings in the middle, and one runnable deployment on the right. This is a
binding map, not another generic card grid. The deployment ID and runnable
status remain in the receipt.

The audience-facing claim is: deployment binds logical requirements to runtime
sources and validates readiness for a persisted run.

## Component Boundary

`AuthoringPhaseVisual` remains the evidence-union dispatcher. Each evidence
variant renders a shared diagram shell containing:

1. a dominant diagram region;
2. an accessible text equivalent or labelled structure;
3. a compact factual receipt.

Shared visual primitives should cover only recurring lifecycle concepts:

- workflow node;
- source or requirement node;
- directed relationship;
- broken relationship;
- lifecycle object identity;
- compact receipt row.

Do not create a general-purpose diagram framework. Reuse an existing graph
renderer when it improves routing or interaction; use semantic HTML and CSS for
fixed one-dimensional mappings. Avoid hand-calculated arbitrary connector
geometry.

## Evidence And Truthfulness

All labels and relationships come from
`PreparedLifecycleStepProjection["evidence"]` or the reviewed evidence catalog.
The visual layer must not introduce a second set of lifecycle facts.

The prepared authoring sequence remains replay evidence. The diagrams must not
imply that Scene 8 performs live authoring RPC calls.

## Responsive Behavior

At 1280x720, the diagram should occupy most of the result height and remain
readable without scrolling. At 1024x768, the diagram may tighten or stack fixed
mapping columns, but the result root must not clip or overflow its bounded
viewport.

On narrower presenter/mobile surfaces, horizontal diagrams may become a
contained, scrollbar-hidden pan region. Factual receipts wrap below the diagram
instead of shrinking labels below readable size.

## Motion

Motion communicates continuity only:

- Draft to Diagnose preserves node positions;
- Diagnose to Repair completes the missing route;
- Repair to Artifact changes object state while preserving the workflow
  silhouette;
- Artifact to Deployment separates requirements into concrete bindings.

No blur, pan-in on unchanged content, bounce, or repeated entrance animation.
Reduced-motion mode renders each final state immediately.

## Accessibility

- Every diagram has a named region.
- Connector meaning is available in text, not color alone.
- Broken and repaired states expose explicit labels.
- IDs and commands remain selectable text.
- Decorative icons are hidden from assistive technology.

## Verification

Add focused tests that assert:

- each beat renders the correct diagram kind;
- Draft, Diagnose, and Repair preserve the same workflow node identities;
- Diagnose exposes the missing `analyze.ok` connection;
- Repair exposes the restored connection and zero diagnostics;
- Artifact preserves the exact artifact identity, version, and requirements;
- Deployment maps every requirement to its configured source;
- no visual introduces facts absent from reviewed evidence.

Run the presentation tests, console typecheck, and production build. Capture all
six beats at 1280x720 plus Discover, Diagnose, and Deployment at 1024x768.
Confirm each result has no unintended internal overflow and remains readable
with reduced motion enabled.

After the visual pass, review the presenter script for all six beats against the
rendered screen. Each beat should support one short spoken claim anchored to the
dominant diagram. Revise the script only when it describes a removed visual,
omits the new focal transformation, or uses terminology that is harder to say
than the diagram requires. Do not expand the script merely because the diagram
contains more detail.

## Out Of Scope

- changing the prepared assistant conversation;
- live authoring RPC execution;
- redesigning the lifecycle rail or presentation chrome;
- adding arbitrary graph editing;
- restoring the previous dense two-screenshot layout.
