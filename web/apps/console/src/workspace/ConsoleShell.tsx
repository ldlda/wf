import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import type { ConnectionState } from "../app/state.js";
import { ConnectionHeader } from "../components/ConnectionHeader.js";
import { EvidenceLedger } from "./EvidenceLedger.js";

type Props = {
  readonly connection: ConnectionState;
  readonly onConnect: (target: string) => void;
  readonly onDraftChange: (value: string) => void;
  readonly children: ReactNode;
};

const lifecycleLinks = [
  { label: "Discover", to: "/console/discover" },
  { label: "Drafts", to: "/console/drafts" },
  { label: "Artifacts", to: "/console/artifacts" },
  { label: "Deployments", to: "/console/deployments" },
  { label: "Runs", to: "/console/runs" },
  { label: "Results", to: "/console/results" },
] as const;

export const ConsoleShell = ({
  connection,
  onConnect,
  onDraftChange,
  children,
}: Props) => (
  <div className="console-workspace">
    <a className="console-skip-link" href="#console-workspace-main">
      Skip to main content
    </a>
    <header className="console-workspace__header">
      <ConnectionHeader
        state={connection}
        onSubmit={onConnect}
        onDraftChange={onDraftChange}
      />
    </header>
    <nav aria-label="Workflow lifecycle" className="console-workspace__nav">
      <ul>
        {lifecycleLinks.map((link) => (
          <li key={link.to}>
            <NavLink
              to={link.to}
              className={({ isActive }) => (isActive ? "active" : undefined)}
            >
              {link.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
    <main id="console-workspace-main" aria-label="Console workspace">
      {children}
    </main>
    <aside aria-label="Operation evidence" className="console-workspace__evidence">
      <h2>Operation evidence</h2>
      <EvidenceLedger records={connection.evidence} />
    </aside>
  </div>
);
