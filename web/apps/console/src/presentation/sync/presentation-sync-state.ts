import type {
  PresentationPresence,
  PresentationSnapshot,
  SessionGrant,
} from "@lda/presentation-sync";

export type ConnectedSyncState = {
  readonly grant: SessionGrant;
  readonly snapshot: PresentationSnapshot;
  readonly presence: PresentationPresence;
};

export type PresentationSyncState =
  | { readonly kind: "standalone" }
  | { readonly kind: "creating" }
  | { readonly kind: "joining"; readonly code: string }
  | (ConnectedSyncState & {
      readonly kind: "waiting" | "connected" | "reconnecting";
    })
  | {
      readonly kind: "failed";
      readonly message: string;
      readonly retryable: boolean;
    }
  | {
      readonly kind: "ended";
      readonly reason: "presenter_ended" | "expired" | "left";
    };

export type PresentationSyncAction =
  | { readonly type: "start_create" }
  | { readonly type: "start_join"; readonly code: string }
  | { readonly type: "grant_received"; readonly grant: SessionGrant }
  | {
      readonly type: "socket_ready";
      readonly snapshot: PresentationSnapshot;
      readonly presence: PresentationPresence;
    }
  | { readonly type: "presence_received"; readonly presence: PresentationPresence }
  | { readonly type: "location_snapshot"; readonly snapshot: PresentationSnapshot }
  | { readonly type: "location_rejected"; readonly snapshot: PresentationSnapshot }
  | { readonly type: "socket_reconnecting" }
  | {
      readonly type: "failed";
      readonly message: string;
      readonly retryable: boolean;
    }
  | {
      readonly type: "session_ended";
      readonly reason: "presenter_ended" | "expired";
    }
  | { readonly type: "left" };

export type PresentationSyncController = {
  readonly state: PresentationSyncState;
  readonly startSession: () => Promise<void>;
  readonly joinSession: (code: string) => Promise<void>;
  readonly retry: () => void;
  readonly leaveSession: () => void;
  readonly endSession: () => void;
};

export const initialPresentationSyncState: PresentationSyncState = {
  kind: "standalone",
};

const emptyPresence: PresentationPresence = { presenters: 0, audience: 0 };

const connectedKindFor = (
  presence: PresentationPresence,
): "waiting" | "connected" =>
  presence.presenters > 0 && presence.audience > 0
    ? "connected"
    : "waiting";

const withPresence = (
  state: PresentationSyncState,
  presence: PresentationPresence,
): PresentationSyncState => {
  if (
    state.kind !== "waiting" &&
    state.kind !== "connected" &&
    state.kind !== "reconnecting"
  ) {
    return state;
  }

  return {
    ...state,
    kind: connectedKindFor(presence),
    presence,
  };
};

const withSnapshot = (
  state: PresentationSyncState,
  snapshot: PresentationSnapshot,
): PresentationSyncState => {
  if (
    state.kind !== "waiting" &&
    state.kind !== "connected" &&
    state.kind !== "reconnecting"
  ) {
    return state;
  }

  return { ...state, snapshot };
};

export const presentationSyncReducer = (
  state: PresentationSyncState,
  action: PresentationSyncAction,
): PresentationSyncState => {
  switch (action.type) {
    case "start_create":
      return { kind: "creating" };
    case "start_join":
      return { kind: "joining", code: action.code };
    case "grant_received":
      return {
        kind: "waiting",
        grant: action.grant,
        snapshot: action.grant.snapshot,
        presence: emptyPresence,
      };
    case "socket_ready":
      if (
        state.kind !== "waiting" &&
        state.kind !== "connected" &&
        state.kind !== "reconnecting"
      ) {
        return state;
      }
      return {
        ...state,
        kind: connectedKindFor(action.presence),
        snapshot: action.snapshot,
        presence: action.presence,
      };
    case "presence_received":
      return withPresence(state, action.presence);
    case "location_snapshot":
    case "location_rejected":
      return withSnapshot(state, action.snapshot);
    case "socket_reconnecting":
      if (
        state.kind !== "waiting" &&
        state.kind !== "connected" &&
        state.kind !== "reconnecting"
      ) {
        return state;
      }
      return { ...state, kind: "reconnecting" };
    case "failed":
      return {
        kind: "failed",
        message: action.message,
        retryable: action.retryable,
      };
    case "session_ended":
      return { kind: "ended", reason: action.reason };
    case "left":
      return { kind: "ended", reason: "left" };
  }
};
