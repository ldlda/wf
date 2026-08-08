import { useState } from "react";
import type { CapabilitySummary } from "../domain/capability-models.js";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import { AuthoringGraph } from "./AuthoringGraph.js";
import { CapabilityPalette } from "./CapabilityPalette.js";
import { ContextInspector } from "./ContextInspector.js";
import type { WorkbenchSelection } from "./authoring-graph.js";

type DraftWorkbenchProps = {
  readonly draft: DraftWorkspace;
  readonly capabilities?: ReadonlyArray<CapabilitySummary>;
  readonly initialSelection?: WorkbenchSelection;
  readonly onSelectionChange?: (selection: WorkbenchSelection) => void;
};

export const DraftWorkbench = ({
  draft,
  capabilities = [],
  initialSelection = { kind: "canvas" },
  onSelectionChange,
}: DraftWorkbenchProps) => {
  const [selection, setSelection] = useState<WorkbenchSelection>(initialSelection);
  const select = (nextSelection: WorkbenchSelection): void => {
    setSelection(nextSelection);
    onSelectionChange?.(nextSelection);
  };

  return (
    <div className="draft-workbench" data-selection-kind={selection.kind}>
      <CapabilityPalette
        capabilities={capabilities}
        onSelectionChange={select}
        selection={selection}
      />
      <AuthoringGraph draft={draft.draft} onSelectionChange={select} selection={selection} />
      <ContextInspector capabilities={capabilities} draft={draft} selection={selection} />
    </div>
  );
};
