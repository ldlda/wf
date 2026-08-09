import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type SyntheticEvent,
} from "react";
import { useNavigate } from "react-router-dom";
import { useConsoleWorkspace } from "../context.js";
import {
  createDraftAuthoringClient,
  type DraftAuthoringClient,
} from "../domain/draft-authoring-client.js";
import type { CapabilityDetail } from "../domain/capability-models.js";
import { useDraftWorkspace } from "../routes/useDraftWorkspace.js";

export type CreateDraftDialogProps = {
  readonly capability: CapabilityDetail | null;
  readonly onClose: () => void;
};

type DialogPhase = "idle" | "saving" | "error";

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

const draftPath = (workspaceId: string, capability: CapabilityDetail | null): string => {
  const path = `/console/drafts/${encodeURIComponent(workspaceId)}`;
  return capability === null
    ? path
    : `${path}?capability=${encodeURIComponent(capability.name)}`;
};

const showModal = (dialog: HTMLDialogElement): void => {
  if (dialog.open) return;
  if (typeof dialog.showModal === "function") {
    try {
      dialog.showModal();
      return;
    } catch {
      // Some test DOMs expose showModal without implementing it.
    }
  }
  dialog.setAttribute("open", "");
};

const closeModal = (dialog: HTMLDialogElement): void => {
  if (!dialog.open) return;
  if (typeof dialog.close === "function") {
    dialog.close();
    return;
  }
  dialog.removeAttribute("open");
};

export const CreateDraftDialog = ({
  capability,
  onClose,
}: CreateDraftDialogProps) => {
  const navigate = useNavigate();
  const { writeExecutor } = useConsoleWorkspace();
  const drafts = useDraftWorkspace(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const onCloseRef = useRef(onClose);
  const lifecycleTokenRef = useRef<number | null>(null);
  const nextLifecycleTokenRef = useRef(0);
  const requestGenerationRef = useRef(0);
  const client = useMemo<DraftAuthoringClient | null>(
    () => (writeExecutor ? createDraftAuthoringClient(writeExecutor) : null),
    [writeExecutor],
  );
  const [workspaceId, setWorkspaceId] = useState("");
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");
  const [phase, setPhase] = useState<DialogPhase>("idle");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog === null) return;
    const lifecycleToken = ++nextLifecycleTokenRef.current;
    lifecycleTokenRef.current = lifecycleToken;
    const previouslyFocused =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    showModal(dialog);
    dialog.querySelector<HTMLElement>("[data-dialog-autofocus]")?.focus();

    return () => {
      if (lifecycleTokenRef.current === lifecycleToken) {
        lifecycleTokenRef.current = null;
      }
      requestGenerationRef.current += 1;
      closeModal(dialog);
      if (previouslyFocused !== null && document.contains(previouslyFocused)) {
        previouslyFocused.focus();
      }
    };
  }, []);

  const invalidatePendingCreate = (): void => {
    requestGenerationRef.current += 1;
  };

  const isCurrentRequest = (
    generation: number,
    lifecycleToken: number,
  ): boolean =>
    lifecycleTokenRef.current === lifecycleToken &&
    requestGenerationRef.current === generation;

  const requestClose = (): void => {
    invalidatePendingCreate();
    onCloseRef.current();
  };

  const handleCancel = (event: SyntheticEvent<HTMLDialogElement>): void => {
    event.preventDefault();
    requestClose();
  };

  const handleDialogClose = (): void => {
    if (lifecycleTokenRef.current === null) return;
    requestClose();
  };

  const createDraft = async (): Promise<void> => {
    if (client === null) {
      setPhase("error");
      setMessage("Connect to a workflow server before creating a draft.");
      return;
    }

    setPhase("saving");
    setMessage(null);
    const lifecycleToken = lifecycleTokenRef.current;
    if (lifecycleToken === null) return;
    const requestGeneration = requestGenerationRef.current + 1;
    requestGenerationRef.current = requestGeneration;
    try {
      const created =
        capability === null
          ? await client.createEmpty({ workspaceId, name, title })
          : await client.createFromCapability({
              workspaceId,
              name,
              title,
              capabilityName: capability.name,
            });
      if (!isCurrentRequest(requestGeneration, lifecycleToken)) return;
      navigate(draftPath(created.workspaceId, capability));
    } catch (error: unknown) {
      if (!isCurrentRequest(requestGeneration, lifecycleToken)) return;
      setPhase("error");
      setMessage(errorMessage(error));
    }
  };

  return (
    <dialog
      aria-labelledby="create-draft-dialog-heading"
      className="draft-create-dialog"
      onCancel={handleCancel}
      onClose={handleDialogClose}
      ref={dialogRef}
    >
      <div className="draft-create-dialog__header">
        <div>
          <p className="workspace-route-pending__eyebrow">
            {capability === null ? "Draft authoring" : "Capability handoff"}
          </p>
          <h2 id="create-draft-dialog-heading">
            {capability === null ? "Create a draft workspace" : "Add capability to draft"}
          </h2>
        </div>
        <button aria-label="Close" onClick={requestClose} type="button">
          Close
        </button>
      </div>

      {capability !== null && (
        <section aria-labelledby="existing-draft-heading" className="draft-create-dialog__section">
          <h3 id="existing-draft-heading">Use an existing draft</h3>
          {drafts.listPhase === "loading" && <p role="status">Loading draft workspaces...</p>}
          {drafts.listPhase === "error" && (
            <p role="alert">{drafts.listMessage ?? "Draft workspace list failed."}</p>
          )}
          {drafts.listPhase === "ready" && drafts.items.length === 0 && (
            <p role="status">No existing draft workspaces are available.</p>
          )}
          {drafts.items.length > 0 && (
            <>
              <label htmlFor="existing-draft">Existing draft</label>
              <select
                id="existing-draft"
                onChange={(event) => setSelectedWorkspaceId(event.target.value)}
                value={selectedWorkspaceId}
              >
                <option value="">Choose a draft workspace</option>
                {drafts.items.map((draft) => (
                  <option key={draft.workspaceId} value={draft.workspaceId}>
                    {draft.title?.trim() || draft.workspaceId} ({draft.workspaceId})
                  </option>
                ))}
              </select>
              <button
                disabled={!selectedWorkspaceId || phase === "saving"}
                onClick={() => {
                  if (selectedWorkspaceId) {
                    navigate(draftPath(selectedWorkspaceId, capability));
                  }
                }}
                type="button"
              >
                Use existing draft
              </button>
            </>
          )}
        </section>
      )}

      <form
        className="draft-create-dialog__section"
        onSubmit={(event) => {
          event.preventDefault();
          void createDraft();
        }}
      >
        <h3>{capability === null ? "New draft" : "Create seeded draft"}</h3>
        <div>
          <label htmlFor="draft-workspace-id">Workspace id</label>
          <input
            id="draft-workspace-id"
            onChange={(event) => setWorkspaceId(event.target.value)}
            required
            type="text"
            value={workspaceId}
            data-dialog-autofocus="true"
          />
        </div>
        <div>
          <label htmlFor="draft-name">Draft name</label>
          <input
            id="draft-name"
            onChange={(event) => setName(event.target.value)}
            required
            type="text"
            value={name}
          />
        </div>
        <div>
          <label htmlFor="draft-title">Title</label>
          <input
            id="draft-title"
            onChange={(event) => setTitle(event.target.value)}
            type="text"
            value={title}
          />
        </div>
        {phase === "error" && message !== null && <p role="alert">{message}</p>}
        <button disabled={phase === "saving"} type="submit">
          {phase === "saving"
            ? "Creating draft..."
            : capability === null
              ? "Create draft"
              : "Create seeded draft"}
        </button>
      </form>
    </dialog>
  );
};
