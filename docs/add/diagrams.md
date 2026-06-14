# Diagram Scratchpad

This file is a working library of Mermaid diagrams for the thesis/report. Keep
diagrams here while they are being shaped, then copy stable versions into the
final document when the surrounding prose is ready.

## Main Architecture Spine

```mermaid
flowchart LR
  Owner[Workflow Owner] --> Agent[External LLM Agent]
  Agent --> CLI[wf CLI]
  CLI --> Transport[JSON-RPC Transport]
  Transport --> Server[WorkflowServer]
  Server --> API[Workflow API Surface]
  API --> Core[Workflow Core]
  API --> Platform[Artifacts / Deployments / Runs]
  Server --> Sources[Source Providers]
  Sources --> Builtins[Platform Sources]
  Sources --> MCP[MCP Sources]
  Sources --> Python[Python Sources]
```

## Workflow Lifecycle

```mermaid
flowchart LR
  Draft[Draft Workspace] --> ValidateDraft[Draft Validation]
  ValidateDraft --> Artifact[Workflow Artifact]
  Artifact --> Deployment[Workflow Deployment]
  Deployment --> ValidateDeploy[Deployment Validation]
  ValidateDeploy --> Run[Workflow Run]
  Run --> Trace[Run Trace]
  Run --> Inspect[Run Inspect / List]
  Run --> Resume[Resume If Interrupted]
```

## Source Resolution

```mermaid
flowchart LR
  Ref[Logical Source Requirement] --> PlatformCheck{Platform Source?}
  PlatformCheck -- yes --> Fixed[Fixed Source Id]
  PlatformCheck -- no --> Binding[Deployment Binding]
  Binding --> Concrete[Concrete Source]
  Fixed --> Runtime[Source Runtime / Handler]
  Concrete --> Runtime
  Runtime --> Capability[Workflow Capability]
```

