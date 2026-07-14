import { useEffect, useId, useState, type FormEvent } from "react";
import QRCode from "react-qr-code";
import {
  JOIN_CODE_LENGTH,
  normalizeJoinCode,
  type PresentationRole,
} from "@lda/presentation-sync";
import type {
  PresentationSyncController,
  PresentationSyncState,
} from "./presentation-sync-state.js";
import "./presentation-sync.css";

export type PresentationPairingPanelProps = {
  readonly role: PresentationRole;
  readonly controller: PresentationSyncController;
};

const oppositePathFor = (role: PresentationRole): "/present" | "/presenter" =>
  role === "presenter" ? "/present" : "/presenter";

const joinUrlFor = (role: PresentationRole, code: string): string =>
  `${window.location.origin}${oppositePathFor(role)}?pair=${normalizeJoinCode(code)}`;

const statusFor = (state: PresentationSyncState): string | null => {
  switch (state.kind) {
    case "creating":
      return "Creating session";
    case "joining":
      return "Joining session";
    case "waiting":
      return "Waiting for another device";
    case "connected":
      return "Connected";
    case "reconnecting":
      return "Reconnecting";
    case "failed":
      return "Pairing failed";
    case "ended":
      return "Presentation ended";
    case "standalone":
      return null;
  }
};

const pluralize = (count: number, singular: string): string =>
  `${count} ${singular}${count === 1 ? "" : "s"}`;

const endedMessageFor = (
  reason: Extract<PresentationSyncState, { readonly kind: "ended" }>["reason"],
): string => {
  switch (reason) {
    case "presenter_ended":
      return "The presenter ended this session.";
    case "expired":
      return "This pairing session expired.";
    case "left":
      return "You left this pairing session.";
  }
};

const isBusy = (state: PresentationSyncState): boolean =>
  state.kind === "creating" || state.kind === "joining";

const isActive = (
  state: PresentationSyncState,
): state is Extract<
  PresentationSyncState,
  { readonly kind: "waiting" | "connected" | "reconnecting" }
> =>
  state.kind === "waiting" ||
  state.kind === "connected" ||
  state.kind === "reconnecting";

export const PresentationPairingPanel = ({
  role,
  controller,
}: PresentationPairingPanelProps) => {
  const { state } = controller;
  const [isOpen, setIsOpen] = useState(
    () => state.kind !== "standalone" && state.kind !== "connected",
  );
  const [code, setCode] = useState("");
  const [copyStatus, setCopyStatus] = useState("");
  const [isConfirmingEnd, setIsConfirmingEnd] = useState(false);
  const status = statusFor(state);
  const idPrefix = useId();
  const panelId = `${idPrefix}-panel`;
  const inputId = `${idPrefix}-code`;
  const inputCode = state.kind === "joining" ? state.code : code;
  const normalizedInputCode = normalizeJoinCode(inputCode);
  const compactPresence = state.kind === "connected"
    ? `${pluralize(state.presence.presenters, "presenter")} · ${pluralize(state.presence.audience, "audience")}`
    : null;
  const triggerLabel = ["Pair presentation", status, compactPresence]
    .filter((part) => part !== null)
    .join(" ");

  // Connection gets out of the deck's way once. Terminal details reopen, while
  // same-state rerenders preserve a user's manual toggle choice.
  useEffect(() => {
    if (state.kind === "connected") {
      setIsOpen(false);
      return;
    }
    if (
      state.kind === "creating" ||
      state.kind === "joining" ||
      state.kind === "waiting" ||
      state.kind === "failed" ||
      state.kind === "ended"
    ) {
      setIsOpen(true);
    }
  }, [state.kind]);

  const openPanel = (): void => setIsOpen((open) => !open);

  const startSession = (): void => {
    void controller.startSession();
  };

  const joinSession = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (normalizedInputCode.length !== JOIN_CODE_LENGTH) return;
    void controller.joinSession(normalizedInputCode);
  };

  const copyJoinUrl = async (joinUrl: string): Promise<void> => {
    if (navigator.clipboard === undefined) {
      setCopyStatus("Copy unavailable; use the link directly");
      return;
    }

    try {
      await navigator.clipboard.writeText(joinUrl);
      setCopyStatus("Join link copied");
    } catch {
      setCopyStatus("Copy unavailable; use the link directly");
    }
  };

  const endSession = (): void => {
    controller.endSession();
    setIsConfirmingEnd(false);
  };

  return (
    <aside
      className="presentation-pairing"
      data-open={isOpen}
      data-role={role}
      data-state={state.kind}
      data-surface-owner={isOpen ? "root" : "trigger"}
      aria-label="Presentation pairing"
    >
      <button
        className="presentation-pairing__trigger"
        type="button"
        aria-controls={panelId}
        aria-expanded={isOpen}
        aria-label={triggerLabel}
        onClick={openPanel}
      >
        <span>Pair presentation</span>
        {status && (
          <span className="presentation-pairing__trigger-status">
            {compactPresence === null ? status : `${status} · ${compactPresence}`}
          </span>
        )}
      </button>

      {isOpen && (
        <section className="presentation-pairing__body" id={panelId}>
          <header className="presentation-pairing__header">
            <div>
              <span className="presentation-pairing__eyebrow">LAN presentation</span>
              <h2>Pair presentation</h2>
            </div>
            <span
              className="presentation-pairing__status"
              role="status"
              aria-label={status ?? "Not paired"}
            >
              {status ?? "Not paired"}
            </span>
          </header>

          {(state.kind === "standalone" || isBusy(state)) && (
            <div className="presentation-pairing__setup">
              <button
                className="presentation-pairing__primary"
                type="button"
                onClick={startSession}
                disabled={isBusy(state)}
                aria-busy={state.kind === "creating"}
                aria-label="Start session"
              >
                {state.kind === "creating" ? "Creating session…" : "Start session"}
              </button>
              <div className="presentation-pairing__divider" aria-hidden="true">
                <span>or join with a code</span>
              </div>
              <form onSubmit={joinSession}>
                <label htmlFor={inputId}>Pairing code</label>
                <div className="presentation-pairing__join-row">
                  <input
                    id={inputId}
                    value={inputCode}
                    onChange={(event) => setCode(normalizeJoinCode(event.target.value))}
                    inputMode="text"
                    autoComplete="off"
                    maxLength={6}
                    spellCheck={false}
                    disabled={isBusy(state)}
                  />
                  <button
                    type="submit"
                    disabled={isBusy(state) || normalizedInputCode.length !== JOIN_CODE_LENGTH}
                    aria-label="Join session"
                  >
                    {state.kind === "joining" ? "Joining…" : "Join session"}
                  </button>
                </div>
              </form>
            </div>
          )}

          {isActive(state) && (
            <div className="presentation-pairing__active">
              <div className="presentation-pairing__qr" role="img" aria-label="Pairing QR code" data-qr-value={joinUrlFor(role, state.grant.code)}>
                <QRCode value={joinUrlFor(role, state.grant.code)} size={156} title="Scan to pair this presentation" />
              </div>
              <div className="presentation-pairing__details">
                <p className="presentation-pairing__instruction">
                  {state.kind === "waiting"
                    ? "Scan this code or enter it on the other device."
                    : "Use this code to add another device."}
                </p>
                <p className="presentation-pairing__code" aria-label="Pairing code">
                  {normalizeJoinCode(state.grant.code)}
                </p>
                <dl className="presentation-pairing__presence">
                  <div>
                    <dt>Peers</dt>
                    <dd>
                      {`${pluralize(state.presence.presenters, "presenter")} · ${pluralize(state.presence.audience, "audience")}`}
                    </dd>
                  </div>
                </dl>
                <div className="presentation-pairing__link-row">
                  <a href={joinUrlFor(role, state.grant.code)}>Copyable join URL</a>
                  <button
                    type="button"
                    className="presentation-pairing__copy"
                    onClick={() => void copyJoinUrl(joinUrlFor(role, state.grant.code))}
                  >
                    Copy join link
                  </button>
                </div>
                <span className="presentation-pairing__copy-status" role="status" aria-live="polite">
                  {copyStatus}
                </span>
                {role === "presenter" && state.kind === "connected" && (
                  <div className="presentation-pairing__end">
                    {isConfirmingEnd ? (
                      <div className="presentation-pairing__confirmation" role="alertdialog" aria-label="End presentation confirmation">
                        <strong>End presentation for everyone?</strong>
                        <div>
                          <button type="button" onClick={endSession}>End presentation now</button>
                          <button type="button" onClick={() => setIsConfirmingEnd(false)}>Keep session</button>
                        </div>
                      </div>
                    ) : (
                      <button type="button" onClick={() => setIsConfirmingEnd(true)}>End presentation</button>
                    )}
                  </div>
                )}
                {role === "audience" && (
                  <button type="button" className="presentation-pairing__leave" onClick={controller.leaveSession}>
                    Leave session
                  </button>
                )}
              </div>
            </div>
          )}

          {state.kind === "failed" && (
            <div className="presentation-pairing__message" role="alert">
              <p>{state.message}</p>
              {state.retryable && (
                <button type="button" onClick={controller.retry}>Retry pairing</button>
              )}
            </div>
          )}

          {state.kind === "ended" && (
            <div className="presentation-pairing__message">
              <p>{endedMessageFor(state.reason)}</p>
            </div>
          )}
        </section>
      )}
    </aside>
  );
};
