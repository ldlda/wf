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

## Layered Package Boundary

> Package ownership view, not a runtime call graph.

```mermaid
flowchart TB
  CLI[wf_cli] --> Transport[wf_transport_rpc_http]
  Transport --> Server[wf_server]
  Server --> API[wf_api]
  API --> Artifacts[wf_artifacts]
  API --> Core[wf_core]
  API --> Platform[wf_platform]
  Server --> MCP[wf_sources_mcp]
  Server --> Python[wf_sources_python]
  MCP --> Platform
  Python --> Platform
  Artifacts --> Platform
```

## Workflow Lifecycle

> Simplified view. For the detailed platform-domain version with source inventory
> and diagnostics, see "Platform Domain" below.

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

## Workflow Core

```mermaid
flowchart TD
  Start[Prepare Run] --> ValidateInput[Validate Workflow Input]
  ValidateInput --> Select[Select Ready Frame]
  Select --> Step{Step Type}
  Step --> Node[NodeUse]
  Step --> Condition[Condition]
  Step --> Foreach[Foreach]
  Step --> Subgraph[Subgraph]
  Step --> Interrupt[Interrupt]
  Step --> Join[Join / Minimal Done Step]
  Step --> End[End]
  Node --> ResolveInput[Resolve Input Bindings]
  ResolveInput --> Handler[Invoke NodeDef Handler]
  Handler --> CheckOutcome[Check Declared Outcome]
  CheckOutcome --> StatePatch[Build Reducer-Aware State Patch]
  StatePatch --> Trace[Append Trace Frame]
  Condition --> Trace
  Foreach --> Trace
  Subgraph --> Trace
  Join --> Trace
  Trace --> Route[Route By Outcome Edge]
  Interrupt --> Stop[Persist Interrupt Request]
  End --> Finalize[Project Workflow Output]
  Route --> Select
  Stop --> Resume[Resume Payload + Outcome]
  Resume --> Route
```

## Platform Domain

```mermaid
flowchart LR
  Draft[Draft Workspace] --> DraftValidation[Draft Validation]
  DraftValidation --> Artifact[Workflow Artifact]
  Artifact --> Deployment[Workflow Deployment]
  SourceInventory[Source Inventory] --> DeploymentValidation[Deployment Validation]
  Deployment --> DeploymentValidation
  DeploymentValidation --> Run[Workflow Run]
  Run --> RunRecord[Run Record]
  Run --> Trace[Trace Slice]
  RunRecord --> Resume[Resume If Interrupted / Stopped]
  DeploymentValidation --> Diagnostics[Repairable Diagnostics]
```

## Workflow API Lifecycle Cohesion

```mermaid
flowchart LR
  Context[WorkflowOperationContext] --> API[WorkflowApi]
  API --> Caps[Capability API]
  API --> Drafts[Draft API]
  API --> Artifacts[Artifact API]
  API --> Deployments[Deployment API]
  API --> Runs[Run API]
  Caps --> Specs[WorkflowSpecProvider]
  Drafts --> DraftStore[Draft Store]
  Artifacts --> ArtifactStore[Artifact Store]
  Deployments --> ArtifactStore
  Runs --> RunStore[Run Store]
  Runs --> Runtime[WorkflowRuntimeRunner]
  Runs --> Live[Optional Live Source Checker]
```

## Source Provider Boundary

```mermaid
flowchart LR
  Config[Workflow Config Sources] --> Server[WorkflowServer Composition]
  Server --> Builtin[Platform Sources]
  Server --> MCP[MCP Source Provider]
  Server --> Python[Python Source Provider]
  Builtin --> Inventory[CapabilitySource Inventory]
  MCP --> Inventory
  Python --> Inventory
  Inventory --> API[Workflow API Surface]
  API --> Runtime[Workflow Runtime]
```
