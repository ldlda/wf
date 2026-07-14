import { describe, expect, it } from "vitest";
import {
  initialPresentationSyncState,
  presentationSyncReducer,
  type PresentationSyncState,
} from "./presentation-sync-state.js";

const grant = {
  sessionId: "session-1",
  code: "ABC123",
  connectionToken: "token-1",
  websocketPath: "/api/presentation-sync/ws" as const,
  snapshot: { hash: "#scene/thesis/title", revision: 0 },
};

const presence = (presenters: number, audience: number) => ({
  presenters,
  audience,
});

const reduce = (
  state: PresentationSyncState,
  action: Parameters<typeof presentationSyncReducer>[1],
): PresentationSyncState => presentationSyncReducer(state, action);

describe("presentationSyncReducer", () => {
  it("tracks create and join progress", () => {
    expect(
      reduce(initialPresentationSyncState, { type: "start_create" }),
    ).toEqual({ kind: "creating" });
    expect(
      reduce(initialPresentationSyncState, {
        type: "start_join",
        code: "a-b c123",
      }),
    ).toEqual({ kind: "joining", code: "a-b c123" });
  });

  it("keeps the grant and initial snapshot while waiting for a peer", () => {
    expect(
      reduce(initialPresentationSyncState, {
        type: "grant_received",
        grant,
      }),
    ).toEqual({
      kind: "waiting",
      grant,
      snapshot: grant.snapshot,
      presence: presence(0, 0),
    });
  });

  it("moves between waiting and connected from peer presence", () => {
    const waiting = reduce(initialPresentationSyncState, {
      type: "grant_received",
      grant,
    });
    const withPresenter = reduce(waiting, {
      type: "presence_received",
      presence: presence(1, 0),
    });
    expect(withPresenter).toMatchObject({ kind: "waiting", presence: presence(1, 0) });

    const connected = reduce(withPresenter, {
      type: "presence_received",
      presence: presence(1, 1),
    });
    expect(connected).toMatchObject({ kind: "connected", presence: presence(1, 1) });

    expect(
      reduce(connected, {
        type: "presence_received",
        presence: presence(1, 0),
      }),
    ).toMatchObject({ kind: "waiting", presence: presence(1, 0) });
  });

  it("accepts snapshots without losing grant or presence", () => {
    const connected = reduce(
      reduce(initialPresentationSyncState, {
        type: "grant_received",
        grant,
      }),
      {
        type: "socket_ready",
        snapshot: { hash: "#scene/thesis/title", revision: 0 },
        presence: presence(1, 1),
      },
    );

    expect(
      reduce(connected, {
        type: "location_snapshot",
        snapshot: { hash: "#scene/problem/direct-actions", revision: 1 },
      }),
    ).toEqual({
      kind: "connected",
      grant,
      snapshot: { hash: "#scene/problem/direct-actions", revision: 1 },
      presence: presence(1, 1),
    });
  });

  it("converges to the server snapshot after a stale publish", () => {
    const connected = reduce(
      reduce(initialPresentationSyncState, {
        type: "grant_received",
        grant,
      }),
      {
        type: "socket_ready",
        snapshot: grant.snapshot,
        presence: presence(1, 1),
      },
    );

    expect(
      reduce(connected, {
        type: "location_rejected",
        snapshot: { hash: "#scene/problem/direct-actions", revision: 4 },
      }),
    ).toMatchObject({
      kind: "connected",
      snapshot: { hash: "#scene/problem/direct-actions", revision: 4 },
    });
  });

  it("retains connected data while reconnecting", () => {
    const connected = reduce(
      reduce(initialPresentationSyncState, {
        type: "grant_received",
        grant,
      }),
      {
        type: "socket_ready",
        snapshot: grant.snapshot,
        presence: presence(1, 1),
      },
    );

    expect(
      reduce(connected, { type: "socket_reconnecting" }),
    ).toEqual({
      kind: "reconnecting",
      grant,
      snapshot: grant.snapshot,
      presence: presence(1, 1),
    });
  });

  it("represents retryable failure, explicit end, and local leave", () => {
    expect(
      reduce(initialPresentationSyncState, {
        type: "failed",
        message: "session not found",
        retryable: true,
      }),
    ).toEqual({
      kind: "failed",
      message: "session not found",
      retryable: true,
    });
    expect(
      reduce(initialPresentationSyncState, {
        type: "session_ended",
        reason: "presenter_ended",
      }),
    ).toEqual({ kind: "ended", reason: "presenter_ended" });
    expect(
      reduce(initialPresentationSyncState, { type: "left" }),
    ).toEqual({ kind: "ended", reason: "left" });
  });
});
