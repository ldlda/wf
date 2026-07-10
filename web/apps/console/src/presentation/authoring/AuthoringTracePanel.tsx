import { useCallback, useEffect, useRef, useState } from "react";
import { projectPreparedAuthoringPhase } from "./authoring-projection.js";
import type { AuthoringPhaseId } from "./authoring-recording.js";

type AuthoringTracePanelProps = {
  readonly phase: AuthoringPhaseId;
  readonly open: boolean;
  readonly onOpen: () => void;
  readonly onClose: () => void;
};

const allPhases: readonly AuthoringPhaseId[] = [
  "discover",
  "draft",
  "validate",
  "artifact",
  "deployment",
];

/**
 * Dialog-style overlay showing the prepared authoring trace.
 *
 * The trigger button is always rendered so it can serve as the focus anchor
 * after the dialog closes (the DOM node persists across open/close cycles;
 * removing it would lose the focus target).
 */
export const AuthoringTracePanel = ({ phase, open, onOpen, onClose }: AuthoringTracePanelProps) => {
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [expandedPhase, setExpandedPhase] = useState<AuthoringPhaseId>(phase);

  useEffect(() => {
    if (!open) {
      triggerRef.current?.focus();
      return;
    }
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  const togglePhase = useCallback((p: AuthoringPhaseId) => {
    setExpandedPhase((prev) => (prev === p ? prev : p));
  }, []);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className="authoring-trace-panel__trigger"
        onClick={onOpen}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        Agent trace
      </button>
      {open && (
        <>
          <div className="authoring-trace-panel__backdrop" onClick={onClose} />
          <div
            className="authoring-trace-panel__dialog"
            role="dialog"
            aria-label="Authoring trace"
            aria-modal="true"
          >
            <div className="authoring-trace-panel__header">
              <strong>Authoring trace</strong>
              <button type="button" onClick={onClose} aria-label="Close trace">×</button>
            </div>
            <div className="authoring-trace-panel__phases">
              {allPhases.map((p) => {
                const projection = projectPreparedAuthoringPhase(p);
                const isExpanded = p === expandedPhase;
                return (
                  <div key={p} className="authoring-trace-panel__phase" data-expanded={isExpanded}>
                    <button
                      type="button"
                      className="authoring-trace-panel__phase-header"
                      onClick={() => togglePhase(p)}
                      aria-expanded={isExpanded}
                    >
                      <span>{projection.label}</span>
                      <small>{projection.commands.length} commands</small>
                    </button>
                    {isExpanded && (
                      <div className="authoring-trace-panel__commands">
                        {projection.commands.map((cmd, i) => (
                          <div key={`${p}-${i}`} className="authoring-trace-panel__command">
                            <div className="authoring-trace-panel__command-line">
                              <code>$ {cmd.command}</code>
                            </div>
                            <p className="authoring-trace-panel__command-summary">{cmd.summary}</p>
                            <span
                              className="authoring-trace-panel__command-result"
                              data-result={cmd.result}
                            >
                              {cmd.result === "success" ? "✓" : "⚡"} {cmd.result}
                            </span>
                            {cmd.detail && (
                              <pre className="authoring-trace-panel__command-detail">
                                {cmd.detail}
                              </pre>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </>
  );
};
