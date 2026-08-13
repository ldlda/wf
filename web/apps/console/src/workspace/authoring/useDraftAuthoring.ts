import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useConsoleWorkspace } from "../context.js";
import {
  createDraftAuthoringClient,
  copyStepInputBinding,
  type DraftAuthoringClient,
} from "../domain/draft-authoring-client.js";
import {
  createDraftWorkspaceClient,
  type DraftWorkspaceClient,
} from "../domain/draft-workspace-client.js";
import type {
  DraftWorkspace,
  OutputBinding,
  StepInputBinding,
} from "../domain/draft-workspace-models.js";
import type { CapabilityNodeFormValue } from "./CapabilityNodeForm.js";
import type { RouteFormValue } from "./RouteForm.js";
import {
  deriveInsertionContext,
  type InsertionContext,
  type WorkbenchSelection,
} from "./authoring-graph.js";
import type { CapabilitySetupPatch } from "./selected-step-dataflow.js";

export type DraftAuthoringPhase = "idle" | "saving" | "conflict" | "error";

export interface DraftAuthoringController {
  readonly draft: DraftWorkspace;
  readonly selection: WorkbenchSelection;
  readonly insertionContext: InsertionContext | null;
  readonly dirty: boolean;
  readonly phase: DraftAuthoringPhase;
  readonly message: string | null;
  readonly resetGeneration: number;
  readonly preservedCapabilityForm: PreservedCapabilityForm;
  readonly addCapability: (input: CapabilityNodeFormValue) => Promise<void>;
  readonly updateCapability: (input: CapabilityNodeFormValue) => Promise<void>;
  readonly setStepInputs: (bindings: ReadonlyArray<StepInputBinding>) => Promise<void>;
  readonly setStepOutputs: (bindings: ReadonlyArray<OutputBinding>) => Promise<void>;
  readonly updateSetup: (patch: CapabilitySetupPatch) => Promise<void>;
  readonly setRoute: (input: RouteFormValue) => Promise<void>;
  readonly validate: () => Promise<void>;
  readonly reload: () => Promise<void>;
  readonly reapply: () => Promise<void>;
  readonly rememberCapabilityForm: (
    kind: "add" | "update",
    input: CapabilityNodeFormValue,
  ) => void;
  readonly rememberRouteForm: (input: RouteFormValue) => void;
  readonly select: (selection: WorkbenchSelection) => void;
  readonly markDirty: () => void;
}

export type UseDraftAuthoringOptions = {
  readonly draft: DraftWorkspace;
  readonly initialSelection?: WorkbenchSelection;
};

type AuthoringState = {
  readonly draft: DraftWorkspace;
  readonly draftInput: DraftWorkspace;
  readonly selection: WorkbenchSelection;
  readonly selectionInput: WorkbenchSelection;
  readonly insertionContext: InsertionContext | null;
  readonly dirty: boolean;
  readonly phase: DraftAuthoringPhase;
  readonly message: string | null;
  readonly resetGeneration: number;
};

type Provenance = {
  readonly workspaceId: string;
  readonly connectedTarget: string | null;
  readonly writeExecutor: object | null;
  readonly readExecutor: object | null;
};

type PendingMutation = {
  readonly key: string;
  readonly promise: Promise<void>;
};

type LastSubmission =
  | {
      readonly kind: "add";
      readonly input: CapabilityNodeFormValue;
      readonly insertion: InsertionContext | null;
    }
  | {
      readonly kind: "update";
      readonly targetStepId: string;
      readonly input: CapabilityNodeFormValue;
    }
  | { readonly kind: "route"; readonly input: RouteFormValue }
  | {
      readonly kind: "setup";
      readonly targetStepId: string;
      readonly patch: CapabilitySetupPatch;
    }
  | {
      readonly kind: "inputs";
      readonly targetStepId: string;
      readonly bindings: ReadonlyArray<StepInputBinding>;
    }
  | {
      readonly kind: "outputs";
      readonly targetStepId: string;
      readonly bindings: ReadonlyArray<OutputBinding>;
    }
  | null;

type MutationOptions = {
  readonly nextSelection?: WorkbenchSelection;
  readonly targetStepId?: string;
  readonly allowTargetSelectionChange?: boolean;
  readonly submission?: Exclude<LastSubmission, null>;
};

export type PreservedCapabilityForm =
  | { readonly kind: "add"; readonly input: CapabilityNodeFormValue }
  | { readonly kind: "update"; readonly input: CapabilityNodeFormValue }
  | null;

const canvasSelection: WorkbenchSelection = { kind: "canvas" };

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

const sameProvenance = (left: Provenance, right: Provenance): boolean =>
  left.workspaceId === right.workspaceId &&
  left.connectedTarget === right.connectedTarget &&
  left.writeExecutor === right.writeExecutor &&
  left.readExecutor === right.readExecutor;

const sameSelection = (
  left: WorkbenchSelection,
  right: WorkbenchSelection,
): boolean => {
  if (left.kind !== right.kind) return false;
  if (left.kind === "canvas" || right.kind === "canvas") return true;
  if (left.kind === "capability" && right.kind === "capability") {
    return left.qualifiedName === right.qualifiedName;
  }
  if (left.kind === "node" && right.kind === "node") return left.nodeId === right.nodeId;
  return (
    left.kind === "edge" &&
    right.kind === "edge" &&
    left.stepId === right.stepId &&
    left.outcome === right.outcome
  );
};

const responseMatchesRequest = (
  response: DraftWorkspace,
  requestProvenance: Provenance,
): boolean => response.workspaceId === requestProvenance.workspaceId;

const mutationKey = (kind: string, input: unknown, revision: number): string => {
  const encoded = JSON.stringify(input);
  return `${kind}:${revision}:${encoded ?? "undefined"}`;
};

const copyOutputBinding = (binding: OutputBinding): OutputBinding => ({
  source:
    typeof binding.source === "string"
      ? binding.source
      : { root: binding.source.root, parts: [...binding.source.parts] },
  target:
    typeof binding.target === "string"
      ? binding.target
      : { root: binding.target.root, parts: [...binding.target.parts] },
});

const copyInputBindings = (
  bindings: ReadonlyArray<StepInputBinding>,
): ReadonlyArray<StepInputBinding> => bindings.map(copyStepInputBinding);

const copyOutputBindings = (
  bindings: ReadonlyArray<OutputBinding>,
): ReadonlyArray<OutputBinding> => bindings.map(copyOutputBinding);

const copySetupPatch = (patch: CapabilitySetupPatch): CapabilitySetupPatch => ({
  ...(patch.description !== undefined ? { description: patch.description } : {}),
  ...(patch.retry !== undefined ? { retry: patch.retry } : {}),
  ...(patch.timeoutSeconds !== undefined ? { timeoutSeconds: patch.timeoutSeconds } : {}),
});

export const useDraftAuthoring = ({
  draft: initialDraft,
  initialSelection = canvasSelection,
}: UseDraftAuthoringOptions): DraftAuthoringController => {
  const { connectedTarget, readExecutor, writeExecutor } = useConsoleWorkspace();
  const authoringClient = useMemo<DraftAuthoringClient | null>(
    () => (writeExecutor ? createDraftAuthoringClient(writeExecutor) : null),
    [writeExecutor],
  );
  const workspaceClient = useMemo<DraftWorkspaceClient | null>(
    () => (readExecutor ? createDraftWorkspaceClient(readExecutor) : null),
    [readExecutor],
  );
  const [state, setState] = useState<AuthoringState>(() => ({
    draft: initialDraft,
    draftInput: initialDraft,
    selection: initialSelection,
    selectionInput: initialSelection,
    insertionContext: deriveInsertionContext(initialSelection),
    dirty: false,
    phase: "idle",
    message: null,
    resetGeneration: 0,
  }));
  const pendingRef = useRef<PendingMutation | null>(null);
  // The draft is confirmed canonical state. Selected-step forms own active
  // tabs and unsaved rows; this ref stores only the exact mutation payload
  // needed for an explicit conflict reapply.
  const lastSubmissionRef = useRef<LastSubmission>(null);
  const [preservedCapabilityForm, setPreservedCapabilityForm] =
    useState<PreservedCapabilityForm>(null);

  const adoptsDraftInput =
    state.draftInput !== initialDraft &&
    (initialDraft.workspaceId !== state.draft.workspaceId || !state.dirty);
  const draft = adoptsDraftInput ? initialDraft : state.draft;
  const adoptsSelectionInput = !sameSelection(state.selectionInput, initialSelection);
  const selection = adoptsSelectionInput ? initialSelection : state.selection;
  const insertionContext =
    adoptsSelectionInput && initialSelection.kind === "edge"
      ? deriveInsertionContext(initialSelection)
      : state.insertionContext;
  const resetGeneration =
    state.resetGeneration + (adoptsDraftInput || adoptsSelectionInput ? 1 : 0);
  const currentProvenance: Provenance = useMemo(() => ({
    workspaceId: draft.workspaceId,
    connectedTarget,
    writeExecutor,
    readExecutor,
  }), [connectedTarget, draft.workspaceId, readExecutor, writeExecutor]);
  const currentDraftRef = useRef(draft);
  const currentSelectionRef = useRef(selection);
  const currentInsertionContextRef = useRef(insertionContext);
  const currentProvenanceRef = useRef(currentProvenance);

  useEffect(() => {
    currentDraftRef.current = draft;
    currentSelectionRef.current = selection;
    currentInsertionContextRef.current = insertionContext;
    currentProvenanceRef.current = currentProvenance;
  }, [currentProvenance, draft, insertionContext, selection]);

  const select = useCallback((selection: WorkbenchSelection): void => {
    setState((current) => ({
      ...current,
      selection,
      selectionInput: initialSelection,
      insertionContext:
        selection.kind === "edge"
          ? deriveInsertionContext(selection)
          : selection.kind === "capability"
            ? current.insertionContext
            : null,
    }));
  }, [initialSelection]);

  const markDirty = useCallback((): void => {
    setState((current) =>
      current.dirty ? current : { ...current, dirty: true, phase: "idle", message: null },
    );
  }, []);

  const commitResponse = useCallback(
    (
      response: DraftWorkspace,
      requestProvenance: Provenance,
      nextSelection?: WorkbenchSelection,
    ): boolean => {
      if (
        !sameProvenance(requestProvenance, currentProvenanceRef.current) ||
        !responseMatchesRequest(response, requestProvenance)
      ) return false;
      setState((current) => ({
        ...current,
        draft: response,
        selection:
          response.status === "conflict"
            ? current.selection
            : nextSelection ?? current.selection,
        insertionContext:
          response.status === "conflict" || nextSelection?.kind !== "node"
            ? current.insertionContext
            : null,
        dirty: response.status === "conflict" ? true : false,
        phase: response.status === "conflict" ? "conflict" : "idle",
        message:
          response.status === "conflict"
            ? (response.diagnostics[0]?.message ?? "The draft changed on the server.")
            : null,
        resetGeneration:
          response.status === "conflict" ? current.resetGeneration : current.resetGeneration + 1,
      }));
      return true;
    },
    [],
  );

  const runMutation = useCallback(
    (
      kind: string,
      input: unknown,
      operation: (client: DraftAuthoringClient, requestDraft: DraftWorkspace) => Promise<DraftWorkspace>,
      options: MutationOptions = {},
    ): Promise<void> => {
      const requestDraft = currentDraftRef.current;
      const key = mutationKey(kind, input, requestDraft.revision);
      const pending = pendingRef.current;
      if (pending?.key === key) return pending.promise;
      if (pending !== null) {
        const error = new Error("Another draft authoring request is in progress.");
        setState((current) => ({
          ...current,
          dirty: true,
          phase: "error",
          message: error.message,
        }));
        return Promise.reject(error);
      }
      if (!authoringClient) {
        return Promise.resolve().then(() => {
          setState((current) => ({
            ...current,
            dirty: true,
            phase: "error",
            message: "Connect to a workflow server before authoring a draft.",
          }));
        });
      }

      if (options.submission !== undefined) {
        lastSubmissionRef.current = options.submission;
        setPreservedCapabilityForm(
          options.submission.kind === "add" || options.submission.kind === "update"
            ? { kind: options.submission.kind, input: options.submission.input }
            : null,
        );
      }
      const requestProvenance = currentProvenanceRef.current;
      setState((current) => ({
        ...current,
        dirty: true,
        phase: "saving",
        message: null,
      }));
      const promise = operation(authoringClient, requestDraft)
        .then((response) => {
          if (!sameProvenance(requestProvenance, currentProvenanceRef.current)) return;
          const targetIsCurrent =
            options.targetStepId === undefined ||
            options.allowTargetSelectionChange === true ||
            (currentSelectionRef.current.kind === "node" &&
              currentSelectionRef.current.nodeId === options.targetStepId);
          if (!targetIsCurrent) {
            // Do not reset the newly selected inspector with a response for the
            // previous node. The canonical server state remains reloadable.
            setState((current) => ({
              ...current,
              dirty: true,
              phase: "idle",
              message: null,
            }));
            return;
          }
          const committed = commitResponse(response, requestProvenance, options.nextSelection);
          if (!committed && sameProvenance(requestProvenance, currentProvenanceRef.current)) {
            throw new Error("The authoring response did not match the requested workspace.");
          }
        })
        .catch((error: unknown) => {
          if (!sameProvenance(requestProvenance, currentProvenanceRef.current)) return;
          setState((current) => ({
            ...current,
            dirty: true,
            phase: "error",
            message: errorMessage(error),
          }));
        })
        .finally(() => {
          if (pendingRef.current?.promise === promise) pendingRef.current = null;
        });
      pendingRef.current = { key, promise };
      return promise;
    },
    [authoringClient, commitResponse],
  );

  const submitCapabilityAdd = useCallback(
    (
      input: CapabilityNodeFormValue,
      insertion: InsertionContext | null,
    ): Promise<void> => {
      return runMutation(
        "add",
        { input, insertion },
        (client, requestDraft) =>
          client.addCapabilityStep({
            workspaceId: requestDraft.workspaceId,
            revision: requestDraft.revision,
            stepId: input.stepId,
            capabilityName: input.capabilityName,
            ...(insertion?.routeFromStep
              ? { routeFromStep: insertion.routeFromStep }
              : {}),
            ...(insertion?.routeFromOutcome
              ? { routeFromOutcome: insertion.routeFromOutcome }
              : {}),
            ...(input.routes !== undefined ? { routes: input.routes } : {}),
            ...(input.inputMap !== undefined ? { inputMap: input.inputMap } : {}),
            ...(input.inputBindings !== undefined ? { inputBindings: input.inputBindings } : {}),
            ...(input.bindOutputs !== undefined ? { bindOutputs: input.bindOutputs } : {}),
            ...(input.description === undefined ? {} : { description: input.description }),
            ...(input.retry === undefined ? {} : { retry: input.retry }),
            ...(input.timeoutSeconds === undefined ? {} : { timeoutSeconds: input.timeoutSeconds }),
          }),
        {
          nextSelection: { kind: "node", nodeId: input.stepId },
          submission: { kind: "add", input, insertion },
        },
      );
    },
    [runMutation],
  );

  const addCapability = useCallback(
    (input: CapabilityNodeFormValue): Promise<void> =>
      submitCapabilityAdd(input, currentInsertionContextRef.current),
    [submitCapabilityAdd],
  );

  const submitCapabilityUpdate = useCallback(
    (
      targetStepId: string,
      input: CapabilityNodeFormValue,
      allowTargetSelectionChange = false,
    ): Promise<void> => {
      // Persist the immutable mutation target with the form. A conflict may
      // outlive the current graph selection before the operator reapplies it.
      return runMutation(
        "update",
        { targetStepId, input },
        (client, requestDraft) =>
          client.updateCapabilityStep({
            workspaceId: requestDraft.workspaceId,
            revision: requestDraft.revision,
            stepId: targetStepId,
            update: {
              input: input.inputBindings,
              ...(input.description === undefined ? {} : { description: input.description }),
              ...(input.retry === undefined ? {} : { retry: input.retry }),
              ...(input.timeoutSeconds === undefined ? {} : { timeoutSeconds: input.timeoutSeconds }),
            },
          }),
        {
          targetStepId,
          allowTargetSelectionChange,
          submission: { kind: "update", targetStepId, input },
        },
      );
    },
    [runMutation],
  );

  const updateCapability = useCallback(
    (input: CapabilityNodeFormValue): Promise<void> => {
      // The form's Step id is display-only for updates; mutation targets stay
      // bound to the node selected when the operator opened the inspector.
      const targetStepId =
        currentSelectionRef.current.kind === "node"
          ? currentSelectionRef.current.nodeId
          : input.stepId;
      return submitCapabilityUpdate(targetStepId, input);
    },
    [submitCapabilityUpdate],
  );

  const selectedStepId = useCallback((): string | null => {
    const selection = currentSelectionRef.current;
    return selection.kind === "node" ? selection.nodeId : null;
  }, []);

  const missingSelectedStep = useCallback((): Promise<void> => {
    const error = new Error("Select a capability node before editing its dataflow.");
    setState((current) => ({
      ...current,
      dirty: true,
      phase: "error",
      message: error.message,
    }));
    return Promise.reject(error);
  }, []);

  const submitSetup = useCallback(
    (
      targetStepId: string,
      patch: CapabilitySetupPatch,
      allowTargetSelectionChange = false,
    ): Promise<void> => {
      const submittedPatch = copySetupPatch(patch);
      const update = {
        ...(submittedPatch.description !== undefined
          ? { description: submittedPatch.description }
          : {}),
        ...(submittedPatch.retry !== undefined ? { retry: submittedPatch.retry } : {}),
        ...(submittedPatch.timeoutSeconds !== undefined
          ? { timeoutSeconds: submittedPatch.timeoutSeconds }
          : {}),
      };
      return runMutation(
        "setup",
        { targetStepId, patch: submittedPatch },
        (client, requestDraft) =>
          client.updateCapabilityStep({
            workspaceId: requestDraft.workspaceId,
            revision: requestDraft.revision,
            stepId: targetStepId,
            update,
          }),
        {
          targetStepId,
          allowTargetSelectionChange,
          submission: { kind: "setup", targetStepId, patch: submittedPatch },
        },
      );
    },
    [runMutation],
  );

  const submitStepInputs = useCallback(
    (
      targetStepId: string,
      bindings: ReadonlyArray<StepInputBinding>,
      allowTargetSelectionChange = false,
    ): Promise<void> => {
      const submittedBindings = copyInputBindings(bindings);
      return runMutation(
        "inputs",
        { targetStepId, bindings: submittedBindings },
        (client, requestDraft) =>
          client.setStepInputBindings({
            workspaceId: requestDraft.workspaceId,
            revision: requestDraft.revision,
            stepId: targetStepId,
            bindings: submittedBindings,
          }),
        {
          targetStepId,
          allowTargetSelectionChange,
          submission: { kind: "inputs", targetStepId, bindings: submittedBindings },
        },
      );
    },
    [runMutation],
  );

  const submitStepOutputs = useCallback(
    (
      targetStepId: string,
      bindings: ReadonlyArray<OutputBinding>,
      allowTargetSelectionChange = false,
    ): Promise<void> => {
      const submittedBindings = copyOutputBindings(bindings);
      return runMutation(
        "outputs",
        { targetStepId, bindings: submittedBindings },
        (client, requestDraft) =>
          client.setStepOutputBindings({
            workspaceId: requestDraft.workspaceId,
            revision: requestDraft.revision,
            stepId: targetStepId,
            bindings: submittedBindings,
          }),
        {
          targetStepId,
          allowTargetSelectionChange,
          submission: { kind: "outputs", targetStepId, bindings: submittedBindings },
        },
      );
    },
    [runMutation],
  );

  const updateSetup = useCallback(
    (patch: CapabilitySetupPatch): Promise<void> => {
      const targetStepId = selectedStepId();
      return targetStepId === null
        ? missingSelectedStep()
        : submitSetup(targetStepId, patch);
    },
    [missingSelectedStep, selectedStepId, submitSetup],
  );

  const setStepInputs = useCallback(
    (bindings: ReadonlyArray<StepInputBinding>): Promise<void> => {
      const targetStepId = selectedStepId();
      return targetStepId === null
        ? missingSelectedStep()
        : submitStepInputs(targetStepId, bindings);
    },
    [missingSelectedStep, selectedStepId, submitStepInputs],
  );

  const setStepOutputs = useCallback(
    (bindings: ReadonlyArray<OutputBinding>): Promise<void> => {
      const targetStepId = selectedStepId();
      return targetStepId === null
        ? missingSelectedStep()
        : submitStepOutputs(targetStepId, bindings);
    },
    [missingSelectedStep, selectedStepId, submitStepOutputs],
  );

  const setRoute = useCallback(
    (input: RouteFormValue): Promise<void> => {
      return runMutation(
        "route",
        input,
        (client, requestDraft) =>
          client.setRoute({
            workspaceId: requestDraft.workspaceId,
            revision: requestDraft.revision,
            stepId: input.stepId,
            outcome: input.outcome,
            target: input.target,
          }),
        { submission: { kind: "route", input } },
      );
    },
    [runMutation],
  );

  const validate = useCallback((): Promise<void> => {
    if (!authoringClient) {
      setState((current) => ({
        ...current,
        phase: "error",
        message: "Connect to a workflow server before validating a draft.",
      }));
      return Promise.resolve();
    }
    const requestProvenance = currentProvenanceRef.current;
    const key = mutationKey("validate", requestProvenance.workspaceId, currentDraftRef.current.revision);
    const pending = pendingRef.current;
    if (pending?.key === key) return pending.promise;
    if (pending !== null) {
      const error = new Error("Another draft authoring request is in progress.");
      setState((current) => ({ ...current, phase: "error", message: error.message }));
      return Promise.reject(error);
    }
    setState((current) => ({ ...current, phase: "saving", message: null }));
    const promise = authoringClient
      .validate(requestProvenance.workspaceId)
      .then((response) => {
        const committed = commitResponse(response, requestProvenance);
        if (!committed && sameProvenance(requestProvenance, currentProvenanceRef.current)) {
          throw new Error("The validation response did not match the requested workspace.");
        }
      })
      .catch((error: unknown) => {
        if (!sameProvenance(requestProvenance, currentProvenanceRef.current)) return;
        setState((current) => ({ ...current, phase: "error", message: errorMessage(error) }));
      })
      .finally(() => {
        if (pendingRef.current?.promise === promise) pendingRef.current = null;
      });
    pendingRef.current = { key, promise };
    return promise;
  }, [authoringClient, commitResponse]);

  const reload = useCallback((): Promise<void> => {
    if (!workspaceClient) return Promise.resolve();
    const requestProvenance = currentProvenanceRef.current;
    const workspaceId = currentDraftRef.current.workspaceId;
    const key = mutationKey("reload", workspaceId, currentDraftRef.current.revision);
    const pending = pendingRef.current;
    if (pending?.key === key) return pending.promise;
    if (pending !== null) {
      const error = new Error("Another draft authoring request is in progress.");
      setState((current) => ({ ...current, phase: "error", message: error.message }));
      return Promise.reject(error);
    }
    const promise = workspaceClient
      .load(workspaceId)
      .then((response) => {
        if (
          !sameProvenance(requestProvenance, currentProvenanceRef.current) ||
          !responseMatchesRequest(response, requestProvenance)
        ) {
          if (sameProvenance(requestProvenance, currentProvenanceRef.current)) {
            setState((current) => ({
              ...current,
              phase: "error",
              message: "The reload response did not match the requested workspace.",
            }));
          }
          return;
        }
        setState((current) => ({
          ...current,
          draft: response,
          draftInput: initialDraft,
          dirty: false,
          phase: "idle",
          message: null,
          resetGeneration: current.resetGeneration + 1,
        }));
      })
      .catch((error: unknown) => {
        if (!sameProvenance(requestProvenance, currentProvenanceRef.current)) return;
        setState((current) => ({ ...current, phase: "error", message: errorMessage(error) }));
      })
      .finally(() => {
        if (pendingRef.current?.promise === promise) pendingRef.current = null;
      });
    pendingRef.current = { key, promise };
    return promise;
  }, [initialDraft, workspaceClient]);

  const reapply = useCallback((): Promise<void> => {
    const last = lastSubmissionRef.current;
    if (last === null) return Promise.resolve();
    if (last.kind === "add") return submitCapabilityAdd(last.input, last.insertion);
    if (last.kind === "update") {
      return submitCapabilityUpdate(last.targetStepId, last.input, true);
    }
    if (last.kind === "route") return setRoute(last.input);
    if (last.kind === "setup") return submitSetup(last.targetStepId, last.patch, true);
    if (last.kind === "inputs") return submitStepInputs(last.targetStepId, last.bindings, true);
    return submitStepOutputs(last.targetStepId, last.bindings, true);
  }, [
    setRoute,
    submitCapabilityAdd,
    submitCapabilityUpdate,
    submitSetup,
    submitStepInputs,
    submitStepOutputs,
  ]);

  const rememberCapabilityForm = useCallback(
    (kind: "add" | "update", input: CapabilityNodeFormValue): void => {
      if (kind === "add") {
        const previous = lastSubmissionRef.current;
        const insertion =
          previous?.kind === "add"
            ? previous.insertion
            : currentInsertionContextRef.current;
        lastSubmissionRef.current = { kind, input, insertion };
        setPreservedCapabilityForm({ kind, input });
        return;
      }
      const previous = lastSubmissionRef.current;
      const targetStepId =
        previous?.kind === "update"
          ? previous.targetStepId
          : currentSelectionRef.current.kind === "node"
            ? currentSelectionRef.current.nodeId
            : input.stepId;
      lastSubmissionRef.current = { kind, targetStepId, input };
      setPreservedCapabilityForm({ kind, input });
    },
    [],
  );

  const rememberRouteForm = useCallback((input: RouteFormValue): void => {
    lastSubmissionRef.current = { kind: "route", input };
    setPreservedCapabilityForm(null);
  }, []);

  return {
    draft,
    selection,
    insertionContext,
    dirty: state.dirty,
    phase: state.phase,
    message: state.message,
    resetGeneration,
    addCapability,
    updateCapability,
    setStepInputs,
    setStepOutputs,
    updateSetup,
    setRoute,
    validate,
    reload,
    reapply,
    preservedCapabilityForm,
    rememberCapabilityForm,
    rememberRouteForm,
    select,
    markDirty,
  };
};
