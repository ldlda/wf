import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useConsoleWorkspace } from "../context.js";
import {
  createDraftAuthoringClient,
  type DraftAuthoringClient,
} from "../domain/draft-authoring-client.js";
import {
  createDraftWorkspaceClient,
  type DraftWorkspaceClient,
} from "../domain/draft-workspace-client.js";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import type { CapabilityNodeFormValue } from "./CapabilityNodeForm.js";
import type { RouteFormValue } from "./RouteForm.js";
import { deriveInsertionContext, type WorkbenchSelection } from "./authoring-graph.js";

export type DraftAuthoringPhase = "idle" | "saving" | "conflict" | "error";

export interface DraftAuthoringController {
  readonly draft: DraftWorkspace;
  readonly selection: WorkbenchSelection;
  readonly dirty: boolean;
  readonly phase: DraftAuthoringPhase;
  readonly message: string | null;
  readonly resetGeneration: number;
  readonly preservedCapabilityForm: PreservedCapabilityForm;
  readonly addCapability: (input: CapabilityNodeFormValue) => Promise<void>;
  readonly updateCapability: (input: CapabilityNodeFormValue) => Promise<void>;
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
  | { readonly kind: "add"; readonly input: CapabilityNodeFormValue }
  | { readonly kind: "update"; readonly input: CapabilityNodeFormValue }
  | { readonly kind: "route"; readonly input: RouteFormValue }
  | null;

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
    dirty: false,
    phase: "idle",
    message: null,
    resetGeneration: 0,
  }));
  const pendingRef = useRef<PendingMutation | null>(null);
  const lastSubmissionRef = useRef<LastSubmission>(null);

  const adoptsDraftInput =
    state.draftInput !== initialDraft &&
    (initialDraft.workspaceId !== state.draft.workspaceId || !state.dirty);
  const draft = adoptsDraftInput ? initialDraft : state.draft;
  const adoptsSelectionInput = !sameSelection(state.selectionInput, initialSelection);
  const selection = adoptsSelectionInput ? initialSelection : state.selection;
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
  const currentProvenanceRef = useRef(currentProvenance);

  useEffect(() => {
    currentDraftRef.current = draft;
    currentSelectionRef.current = selection;
    currentProvenanceRef.current = currentProvenance;
  }, [currentProvenance, draft, selection]);

  const select = useCallback((selection: WorkbenchSelection): void => {
    setState((current) => ({
      ...current,
      selection,
      selectionInput: initialSelection,
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
      nextSelection?: WorkbenchSelection,
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

      const requestProvenance = currentProvenanceRef.current;
      setState((current) => ({
        ...current,
        dirty: true,
        phase: "saving",
        message: null,
      }));
      const promise = operation(authoringClient, requestDraft)
        .then((response) => {
          const committed = commitResponse(response, requestProvenance, nextSelection);
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

  const addCapability = useCallback(
    (input: CapabilityNodeFormValue): Promise<void> => {
      lastSubmissionRef.current = { kind: "add", input };
      const insertion = deriveInsertionContext(currentSelectionRef.current);
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
            description: input.description,
            retry: input.retry,
            timeoutSeconds: input.timeoutSeconds,
          }),
        { kind: "node", nodeId: input.stepId },
      );
    },
    [runMutation],
  );

  const updateCapability = useCallback(
    (input: CapabilityNodeFormValue): Promise<void> => {
      lastSubmissionRef.current = { kind: "update", input };
      return runMutation(
        "update",
        input,
        (client, requestDraft) =>
          client.updateCapabilityStep({
            workspaceId: requestDraft.workspaceId,
            revision: requestDraft.revision,
            stepId: input.stepId,
            update: {
              description: input.description,
              input: input.inputBindings,
              retry: input.retry,
              timeoutSeconds: input.timeoutSeconds,
            },
          }),
      );
    },
    [runMutation],
  );

  const setRoute = useCallback(
    (input: RouteFormValue): Promise<void> => {
      lastSubmissionRef.current = { kind: "route", input };
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
    return workspaceClient
      .load(currentDraftRef.current.workspaceId)
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
      });
  }, [initialDraft, workspaceClient]);

  const reapply = useCallback((): Promise<void> => {
    const last = lastSubmissionRef.current;
    if (last === null) return Promise.resolve();
    if (last.kind === "add") return addCapability(last.input);
    if (last.kind === "update") return updateCapability(last.input);
    return setRoute(last.input);
  }, [addCapability, setRoute, updateCapability]);

  const rememberCapabilityForm = useCallback(
    (kind: "add" | "update", input: CapabilityNodeFormValue): void => {
      lastSubmissionRef.current = { kind, input };
    },
    [],
  );

  const rememberRouteForm = useCallback((input: RouteFormValue): void => {
    lastSubmissionRef.current = { kind: "route", input };
  }, []);

  return {
    draft,
    selection,
    dirty: state.dirty,
    phase: state.phase,
    message: state.message,
    resetGeneration,
    addCapability,
    updateCapability,
    setRoute,
    validate,
    reload,
    reapply,
    preservedCapabilityForm:
      lastSubmissionRef.current?.kind === "add" || lastSubmissionRef.current?.kind === "update"
        ? lastSubmissionRef.current
        : null,
    rememberCapabilityForm,
    rememberRouteForm,
    select,
    markDirty,
  };
};
