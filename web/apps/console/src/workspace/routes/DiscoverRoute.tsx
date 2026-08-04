import { Boxes, PackageOpen } from "lucide-react";
import type {
  CapabilityDetail,
  CapabilitySummary,
} from "../domain/capability-models.js";
import { useCapabilityDiscovery } from "./useCapabilityDiscovery.js";

const formatKind = (kind: CapabilitySummary["kind"]): string =>
  kind === "node_spec" ? "Node spec" : "Wrapper artifact";

const KindIcon = ({ kind }: { readonly kind: CapabilitySummary["kind"] }) => {
  const Icon = kind === "node_spec" ? Boxes : PackageOpen;
  return <Icon aria-hidden="true" size={16} strokeWidth={1.8} />;
};

const SchemaBlock = ({
  heading,
  value,
}: {
  readonly heading: string;
  readonly value: Record<string, unknown>;
}) => (
  <div className="capability-discovery__schema-block">
    <h3>{heading}</h3>
    <pre>{JSON.stringify(value, null, 2)}</pre>
  </div>
);

const CapabilityRow = ({
  item,
  selected,
  onInspect,
}: {
  readonly item: CapabilitySummary;
  readonly selected: boolean;
  readonly onInspect: (qualifiedName: string) => void;
}) => (
  <li>
    <button
      className="capability-discovery__row"
      data-selected={selected}
      aria-controls="capability-detail"
      aria-pressed={selected}
      onClick={() => onInspect(item.name)}
      type="button"
    >
      <span className="capability-discovery__row-heading">
        <span className="capability-discovery__kind">
          <KindIcon kind={item.kind} />
          <span>{formatKind(item.kind)}</span>
        </span>
        <strong>{item.name}</strong>
      </span>
      <span className="capability-discovery__row-meta">
        <span>Source: {item.sourceId}</span>
        <span>Inputs: {item.inputFields.length > 0 ? item.inputFields.join(", ") : "none"}</span>
        <span>Outputs: {item.outputFields.length > 0 ? item.outputFields.join(", ") : "none"}</span>
        <span>Outcomes: {item.outcomes.length > 0 ? item.outcomes.join(", ") : "none"}</span>
      </span>
      {item.description && <span className="capability-discovery__description">{item.description}</span>}
    </button>
  </li>
);

const DetailView = ({ detail }: { readonly detail: CapabilityDetail }) => (
  <section aria-labelledby="capability-detail-heading" className="capability-discovery__detail" id="capability-detail">
    <p className="workspace-route-pending__eyebrow">Selected contract</p>
    <h2 id="capability-detail-heading">{detail.name}</h2>
    <dl className="capability-discovery__facts">
      <div><dt>Kind</dt><dd>{formatKind(detail.kind)}</dd></div>
      <div><dt>Source</dt><dd>{detail.sourceId}</dd></div>
      <div><dt>Async</dt><dd>{detail.isAsync ? "yes" : "no"}</dd></div>
      <div><dt>Outcomes</dt><dd>{detail.outcomes.join(", ") || "none"}</dd></div>
    </dl>
    <div className="capability-discovery__schemas">
      <SchemaBlock heading="Input schema" value={detail.inputSchema} />
      <SchemaBlock heading="Output schema" value={detail.outputSchema} />
      <SchemaBlock heading="Wrapper hints" value={detail.wrapperHints} />
    </div>
  </section>
);

export const DiscoverRoute = () => {
  const discovery = useCapabilityDiscovery();
  const isReady = discovery.phase === "ready";

  return (
    <div className="capability-discovery">
      <header className="capability-discovery__header">
        <p className="workspace-route-pending__eyebrow">Capability catalog</p>
        <h1>Discover capabilities</h1>
        <p>Inspect the typed contracts available to workflow authors before drafting.</p>
      </header>

      <form
        className="capability-discovery__filters"
        onSubmit={(event) => {
          event.preventDefault();
          discovery.search();
        }}
      >
        <div>
          <label htmlFor="capability-search">Search capabilities</label>
          <input
            id="capability-search"
            onChange={(event) => discovery.setQuery(event.target.value)}
            type="text"
            value={discovery.query}
          />
        </div>
        <div>
          <label htmlFor="capability-source">Filter by source</label>
          <input
            id="capability-source"
            onChange={(event) => discovery.setSourceId(event.target.value)}
            type="text"
            value={discovery.sourceId}
          />
        </div>
        <button type="submit">Search</button>
      </form>

      <div className="capability-discovery__panes">
        <section aria-labelledby="capability-results-heading" className="capability-discovery__results">
          <div className="capability-discovery__section-heading">
            <div>
              <p className="workspace-route-pending__eyebrow">Available interfaces</p>
              <h2 id="capability-results-heading">Capabilities</h2>
            </div>
            {isReady && <span className="capability-discovery__count">{discovery.items.length} shown</span>}
          </div>

          {discovery.phase === "disconnected" && (
            <p role="status">Connect a workflow server to discover capabilities.</p>
          )}
          {discovery.phase === "loading" && <p role="status">Loading capabilities...</p>}
          {discovery.phase === "error" && (
            <p role="alert">{discovery.message ?? "Capability discovery failed."}</p>
          )}
          {isReady && discovery.items.length === 0 && (
            <p role="status">No capabilities match the current filters.</p>
          )}
          {discovery.items.length > 0 && (
            <ul className="capability-discovery__list">
              {discovery.items.map((item) => (
                <CapabilityRow
                  item={item}
                  key={item.name}
                  onInspect={discovery.inspect}
                  selected={discovery.selected?.name === item.name}
                />
              ))}
            </ul>
          )}
          {discovery.nextCursor && (
            <button
              disabled={discovery.phase === "loading"}
              onClick={discovery.loadMore}
              type="button"
            >
              Load more capabilities
            </button>
          )}
        </section>

        {discovery.selected ? (
          <DetailView detail={discovery.selected} />
        ) : (
          <section aria-labelledby="capability-detail-empty-heading" className="capability-discovery__detail capability-discovery__detail--empty" id="capability-detail">
            <p className="workspace-route-pending__eyebrow">Contract detail</p>
            <h2 id="capability-detail-empty-heading">Select a capability</h2>
            <p>Choose a result to inspect its input, output, and wrapper contract.</p>
          </section>
        )}
      </div>
    </div>
  );
};
