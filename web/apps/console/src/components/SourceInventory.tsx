import type { SourceRecord } from "../app/state.js";

type Props = {
  readonly sources: ReadonlyArray<SourceRecord>;
  readonly loading: boolean;
  readonly error: string | null;
};

export const SourceInventory = ({ sources, loading, error }: Props) => {
  return (
    <section aria-label="Source Inventory">
      <h2>Sources</h2>
      {loading && <p data-testid="sources-loading">Loading sources{"\u2026"}</p>}
      {error && (
        <p data-testid="sources-error" role="alert">
          {error}
        </p>
      )}
      {!loading && !error && sources.length === 0 && (
        <p data-testid="sources-empty">No workflow sources reported.</p>
      )}
      {!loading && !error && sources.length > 0 && (
        <table data-testid="sources-table">
          <thead>
            <tr>
              <th>Source</th>
              <th>Kind</th>
              <th>Description</th>
              <th>Status</th>
              <th>Tools</th>
              <th>Nodes</th>
              <th>Reducers</th>
              <th>Prompts</th>
              <th>Resources</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((s) => (
              <tr key={s.id} data-testid={`source-row-${s.id}`}>
                <td data-testid={`source-id-${s.id}`}>{s.id}</td>
                <td data-testid={`source-kind-${s.id}`}>{s.kind}</td>
                <td data-testid={`source-desc-${s.id}`}>
                  {s.description ?? ""}
                </td>
                <td data-testid={`source-status-${s.id}`}>
                  {s.enabled ? "enabled" : "disabled"}
                </td>
                <td data-testid={`source-tools-${s.id}`}>{s.toolCount}</td>
                <td data-testid={`source-nodes-${s.id}`}>{s.nodeSpecCount}</td>
                <td data-testid={`source-reducers-${s.id}`}>
                  {s.reducerCount}
                </td>
                <td data-testid={`source-prompts-${s.id}`}>{s.promptCount}</td>
                <td data-testid={`source-resources-${s.id}`}>
                  {s.resourceCount}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
};
