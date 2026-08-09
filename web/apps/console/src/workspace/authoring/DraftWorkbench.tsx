import { useCallback, useEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import { useBlocker } from "react-router-dom";
import type { CapabilitySummary } from "../domain/capability-models.js";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import { AuthoringGraph } from "./AuthoringGraph.js";
import { CapabilityPalette } from "./CapabilityPalette.js";
import { ContextInspector } from "./ContextInspector.js";
import { projectAuthoringGraph, type WorkbenchSelection } from "./authoring-graph.js";
import { useAuthoringCapabilityDetail } from "./useAuthoringCapabilityDetail.js";
import { useDraftAuthoring } from "./useDraftAuthoring.js";

type DraftWorkbenchProps = {
  readonly draft: DraftWorkspace;
  readonly capabilities?: ReadonlyArray<CapabilitySummary>;
  readonly initialSelection?: WorkbenchSelection;
  readonly onSelectionChange?: (selection: WorkbenchSelection) => void;
  readonly enableNavigationProtection?: boolean;
};

type MobileSheet = "palette" | "inspector";

const MOBILE_BREAKPOINT = 850;

const EMPTY_CAPABILITIES: ReadonlyArray<CapabilitySummary> = [];

const isMobileViewport = (): boolean =>
  typeof window !== "undefined" && window.innerWidth <= MOBILE_BREAKPOINT;

const useMobileViewport = (): boolean => {
  const [mobile, setMobile] = useState(isMobileViewport);

  useEffect(() => {
    const handleResize = (): void => setMobile(isMobileViewport());
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  return mobile;
};

type MobileSheetProps = {
  readonly id: string;
  readonly label: string;
  readonly closeLabel: string;
  readonly isMobile: boolean;
  readonly open: boolean;
  readonly triggerRef: RefObject<HTMLButtonElement | null>;
  readonly onClose: () => void;
  readonly children: ReactNode;
};

const MobileSheet = ({
  id,
  label,
  closeLabel,
  isMobile,
  open,
  triggerRef,
  onClose,
  children,
}: MobileSheetProps) => {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const wasOpen = useRef(open);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog === null) return;

    const closeDialog = (): void => {
      if (typeof dialog.close === "function") {
        dialog.close();
      } else {
        dialog.removeAttribute("open");
      }
    };

    if (!isMobile) {
      closeDialog();
      dialog.setAttribute("open", "");
      return;
    }

    if (open) {
      if (!dialog.open) {
        if (typeof dialog.showModal === "function") {
          dialog.showModal();
        } else {
          dialog.setAttribute("open", "");
        }
      }
    } else {
      closeDialog();
    }
  }, [isMobile, open]);

  useEffect(() => {
    if (wasOpen.current && !open) triggerRef.current?.focus();
    wasOpen.current = open;
  }, [open, triggerRef]);

  return (
    <dialog
      aria-label={label}
      className="draft-workbench__sheet"
      id={id}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      ref={dialogRef}
    >
      <button className="draft-workbench__sheet-close" onClick={onClose} type="button">
        {closeLabel}
      </button>
      {children}
    </dialog>
  );
};

export const DraftWorkbench = ({
  draft,
  capabilities = EMPTY_CAPABILITIES,
  initialSelection = { kind: "canvas" },
  onSelectionChange,
  enableNavigationProtection = false,
}: DraftWorkbenchProps) => {
  const controller = useDraftAuthoring({ draft, initialSelection });
  const isMobile = useMobileViewport();
  const [openSheet, setOpenSheet] = useState<MobileSheet | null>(null);
  const paletteTriggerRef = useRef<HTMLButtonElement>(null);
  const inspectorTriggerRef = useRef<HTMLButtonElement>(null);
  // Resolve capability details from the controller draft so a newly committed
  // node can immediately render its edit form before the route-level loader refreshes.
  const graph = projectAuthoringGraph(controller.draft.draft);
  let capabilityName: string | null = null;
  if (controller.selection.kind === "capability") {
    capabilityName = controller.selection.qualifiedName;
  } else if (controller.selection.kind === "node") {
    const nodeId = controller.selection.nodeId;
    capabilityName =
      graph.nodes.find((node) => node.id === nodeId)?.data.nodeRef ??
      (controller.preservedCapabilityForm?.kind === "update" &&
      controller.preservedCapabilityForm.input.stepId === nodeId
        ? controller.preservedCapabilityForm.input.capabilityName
        : null);
  }
  const capabilityDetail = useAuthoringCapabilityDetail(capabilityName);
  const select = useCallback(
    (nextSelection: WorkbenchSelection): void => {
      controller.select(nextSelection);
      onSelectionChange?.(nextSelection);
    },
    [controller, onSelectionChange],
  );

  return (
    <>
      {enableNavigationProtection && <DirtyNavigationProtection dirty={controller.dirty} />}
      <div
        className="draft-workbench"
        data-dirty={controller.dirty}
        data-selection-kind={controller.selection.kind}
      >
        <div
          aria-label="Mobile authoring panels"
          className="draft-workbench__mobile-controls"
          role="group"
        >
          <button
            aria-controls="draft-workbench-palette"
            aria-expanded={openSheet === "palette"}
            onClick={() => setOpenSheet("palette")}
            ref={paletteTriggerRef}
            type="button"
          >
            Open capability palette
          </button>
          <button
            aria-controls="draft-workbench-inspector"
            aria-expanded={openSheet === "inspector"}
            onClick={() => setOpenSheet("inspector")}
            ref={inspectorTriggerRef}
            type="button"
          >
            Open context inspector
          </button>
        </div>
        <MobileSheet
          closeLabel="Close capability palette"
          id="draft-workbench-palette"
          isMobile={isMobile}
          label="Capability palette sheet"
          onClose={() => setOpenSheet(null)}
          open={!isMobile || openSheet === "palette"}
          triggerRef={paletteTriggerRef}
        >
          <CapabilityPalette
            capabilities={capabilities}
            onSelectionChange={select}
            selection={controller.selection}
          />
        </MobileSheet>
        <AuthoringGraph
          draft={controller.draft.draft}
          onSelectionChange={select}
          selection={controller.selection}
        />
        <MobileSheet
          closeLabel="Close context inspector"
          id="draft-workbench-inspector"
          isMobile={isMobile}
          label="Context inspector sheet"
          onClose={() => setOpenSheet(null)}
          open={!isMobile || openSheet === "inspector"}
          triggerRef={inspectorTriggerRef}
        >
          <ContextInspector
            capabilities={capabilities}
            capabilityDetail={capabilityDetail.detail}
            capabilityDetailMessage={capabilityDetail.message}
            capabilityDetailPhase={capabilityDetail.phase}
            controller={controller}
            draft={controller.draft}
            selection={controller.selection}
          />
        </MobileSheet>
      </div>
    </>
  );
};

const DirtyNavigationProtection = ({ dirty }: { readonly dirty: boolean }) => {
  const blocker = useBlocker(dirty);
  useEffect(() => {
    if (!dirty) return;
    const handleBeforeUnload = (event: BeforeUnloadEvent): void => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [dirty]);

  if (blocker.state !== "blocked") return null;
  return (
    <aside aria-label="Unsaved changes" className="draft-workbench__navigation-warning" role="alert">
      <p>Unsaved form changes will be lost.</p>
      <button onClick={() => blocker.proceed()} type="button">Leave page</button>
      <button onClick={() => blocker.reset()} type="button">Stay</button>
    </aside>
  );
};
