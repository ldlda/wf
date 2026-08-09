import { useCallback, useEffect } from "react";
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

const EMPTY_CAPABILITIES: ReadonlyArray<CapabilitySummary> = [];

export const DraftWorkbench = ({
  draft,
  capabilities = EMPTY_CAPABILITIES,
  initialSelection = { kind: "canvas" },
  onSelectionChange,
  enableNavigationProtection = false,
}: DraftWorkbenchProps) => {
  const controller = useDraftAuthoring({ draft, initialSelection });
  const graph = projectAuthoringGraph(draft.draft);
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
      <div className="draft-workbench" data-selection-kind={controller.selection.kind}>
        <CapabilityPalette
          capabilities={capabilities}
          onSelectionChange={select}
          selection={controller.selection}
        />
        <AuthoringGraph
          draft={controller.draft.draft}
          onSelectionChange={select}
          selection={controller.selection}
        />
        <ContextInspector
          capabilities={capabilities}
          capabilityDetail={capabilityDetail.detail}
          capabilityDetailMessage={capabilityDetail.message}
          capabilityDetailPhase={capabilityDetail.phase}
          controller={controller}
          draft={controller.draft}
          selection={controller.selection}
        />
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
