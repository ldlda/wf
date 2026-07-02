import type { DemoEvent } from "../demo/timeline/models.js";
import { formatJson } from "./format.js";

type OperationBlockProps = {
  readonly event: DemoEvent;
};

export const OperationBlock = ({ event }: OperationBlockProps) => (
  <section className="operation-block" aria-label={`${event.stage} operation`}>
    <header>
      <p>{event.operation ?? event.stage}</p>
      <small>{event.durationMs} ms</small>
    </header>
    {event.equivalentCli && (
      <pre className="operation-block__command"><code>{event.equivalentCli}</code></pre>
    )}
    <div className="operation-block__grid">
      <section>
        <h3>Raw</h3>
        <pre><code>{formatJson(event.rawResponse)}</code></pre>
      </section>
      <section>
        <h3>Interpreted</h3>
        <pre><code>{formatJson(event.interpreted)}</code></pre>
      </section>
    </div>
    <footer>
      <span>{event.resultingIds.deploymentId}</span>
      {event.resultingIds.runId && <span>{event.resultingIds.runId}</span>}
    </footer>
  </section>
);
