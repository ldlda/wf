import type { CapabilitySummary } from "../domain/capability-models.js";
import type { WorkbenchSelection } from "./authoring-graph.js";

type CapabilityPaletteProps = {
  readonly capabilities?: ReadonlyArray<CapabilitySummary>;
  readonly selection: WorkbenchSelection;
  readonly onSelectionChange: (selection: WorkbenchSelection) => void;
};

const EMPTY_CAPABILITIES: ReadonlyArray<CapabilitySummary> = [];

export const CapabilityPalette = ({
  capabilities = EMPTY_CAPABILITIES,
  selection,
  onSelectionChange,
}: CapabilityPaletteProps) => (
  <aside aria-label="Capability palette" className="capability-palette" role="region">
    <header className="capability-palette__header">
      <p className="workspace-route-pending__eyebrow">Available interfaces</p>
      <h2>Capabilities</h2>
      <p>Choose a capability to inspect its contract, configure a step, and add it to this graph.</p>
    </header>
    {capabilities.length > 0 ? (
      <ul className="capability-palette__list">
        {capabilities.map((capability) => {
          const isSelected =
            selection.kind === "capability" && selection.qualifiedName === capability.name;
          return (
            <li key={capability.name}>
              <button
                aria-label={capability.name}
                aria-pressed={isSelected}
                className="capability-palette__item"
                data-selected={isSelected}
                onClick={() =>
                  onSelectionChange({ kind: "capability", qualifiedName: capability.name })
                }
                type="button"
              >
                <strong>{capability.name}</strong>
                <span>{capability.kind === "node_spec" ? "Node spec" : "Wrapper artifact"}</span>
              </button>
            </li>
          );
        })}
      </ul>
    ) : (
      <p className="capability-palette__empty">No capability catalog is loaded for this draft yet.</p>
    )}
  </aside>
);
