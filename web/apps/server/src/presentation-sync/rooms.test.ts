import { describe, expect, it, vi } from "vitest";
import type { ServerSyncMessage } from "@lda/presentation-sync";
import type { PresentationPeer, PresentationRoomService } from "./rooms.js";
import {
  createPresentationRoomService,
  EMPTY_ROOM_GRACE_MS,
  PresentationRoomJoinError,
  ROOM_INACTIVITY_TTL_MS,
} from "./rooms.js";

const peer = (): PresentationPeer & {
  readonly send: ReturnType<typeof vi.fn<PresentationPeer["send"]>>;
  readonly close: ReturnType<typeof vi.fn<PresentationPeer["close"]>>;
} => {
  const send = vi.fn<PresentationPeer["send"]>();
  const close = vi.fn<PresentationPeer["close"]>();
  return { send, close };
};

const makeService = () => {
  let now = 0;
  let id = 0;
  let code = 0;
  let token = 0;
  const service = createPresentationRoomService({
    now: () => now,
    makeId: () => `session-${++id}`,
    makeCode: () => `C${String(++code).padStart(5, "0")}`,
    makeToken: () => `token-${++token}`,
  });
  return {
    service,
    advance: (milliseconds: number) => {
      now += milliseconds;
    },
  };
};

const connectRoom = (service: PresentationRoomService) => {
  const created = service.create({
    role: "presenter",
    initialHash: "#scene/thesis/title",
  });
  const joined = service.join({ role: "audience", code: created.code });
  const presenter = peer();
  const audience = peer();
  service.connect(created.connectionToken, presenter);
  service.connect(joined.connectionToken, audience);
  presenter.send.mockClear();
  presenter.close.mockClear();
  audience.send.mockClear();
  audience.close.mockClear();
  return {
    service,
    presenter,
    audience,
    presenterToken: created.connectionToken,
    audienceToken: joined.connectionToken,
  };
};

const connectedRoom = () => {
  const { service, advance } = makeService();
  return { ...connectRoom(service), advance };
};

describe("createPresentationRoomService", () => {
  it("creates a room at revision zero and joins the opposite role", () => {
    const { service } = makeService();
    const created = service.create({
      role: "presenter",
      initialHash: "#scene/thesis/title",
    });
    const joined = service.join({ role: "audience", code: created.code });

    expect(created.snapshot).toEqual({ hash: "#scene/thesis/title", revision: 0 });
    expect(joined.sessionId).toBe(created.sessionId);
    expect(joined.snapshot).toEqual(created.snapshot);
    expect(joined.connectionToken).not.toBe(created.connectionToken);
  });

  it("reports missing sessions and invalid roles with stable typed errors", () => {
    const { service } = makeService();
    const created = service.create({
      role: "presenter",
      initialHash: "#scene/thesis/title",
    });

    for (const [input, code] of [
      [{ role: "audience" as const, code: "NOPE00" }, "session_not_found"],
      [{ role: "presenter" as const, code: created.code }, "invalid_role"],
    ] as const) {
      try {
        service.join(input);
        throw new Error("expected join to fail");
      } catch (error) {
        expect(error).toBeInstanceOf(PresentationRoomJoinError);
        expect((error as PresentationRoomJoinError).code).toBe(code);
      }
    }
  });

  it("allocates unique room codes", () => {
    const { service } = makeService();

    const first = service.create({ role: "presenter", initialHash: "#scene/one" });
    const second = service.create({ role: "presenter", initialHash: "#scene/two" });

    expect(first.code).not.toBe(second.code);
  });

  it("sends the initial snapshot and presence when a peer connects", () => {
    const { service } = makeService();
    const created = service.create({ role: "presenter", initialHash: "#scene/one" });
    const presenter = peer();

    expect(service.connect(created.connectionToken, presenter)).toEqual({
      kind: "connected",
      snapshot: { hash: "#scene/one", revision: 0 },
      presence: { presenters: 1, audience: 0 },
    });
    expect(presenter.send.mock.calls).toEqual([
      [
        {
          type: "location.snapshot",
          snapshot: { hash: "#scene/one", revision: 0 },
          originatingMessageId: null,
        },
      ],
      [
        {
          type: "presence.snapshot",
          presence: { presenters: 1, audience: 0 },
        },
      ],
    ]);
  });

  it("replaces an existing connection for a duplicate token", () => {
    const { service } = makeService();
    const created = service.create({ role: "presenter", initialHash: "#scene/one" });
    const original = peer();
    const replacement = peer();
    service.connect(created.connectionToken, original);
    original.send.mockClear();

    expect(service.connect(created.connectionToken, replacement).kind).toBe(
      "connected",
    );
    expect(original.close).toHaveBeenCalledWith(4001, "replaced");
    expect(original.send).not.toHaveBeenCalled();
    expect(replacement.send).toHaveBeenCalledWith({
      type: "location.snapshot",
      snapshot: { hash: "#scene/one", revision: 0 },
      originatingMessageId: null,
    });
  });

  it("does not disconnect a replacement when the old peer closes", () => {
    const { service } = makeService();
    const created = service.create({ role: "presenter", initialHash: "#scene/one" });
    const oldPeer = peer();
    const newPeer = peer();
    service.connect(created.connectionToken, oldPeer);
    service.connect(created.connectionToken, newPeer);
    newPeer.send.mockClear();

    service.disconnect(created.connectionToken, oldPeer);

    expect(service.publish(created.connectionToken, newPeer, {
      type: "location.publish",
      hash: "#scene/replacement-survives",
      baseRevision: 0,
      messageId: "replacement-1",
    }).kind).toBe("accepted");
    expect(newPeer.send).toHaveBeenCalledWith({
      type: "location.snapshot",
      snapshot: { hash: "#scene/replacement-survives", revision: 1 },
      originatingMessageId: "replacement-1",
    });
  });

  it("rejects publish and end commands from a replaced presenter peer", () => {
    const { service } = makeService();
    const created = service.create({ role: "presenter", initialHash: "#scene/one" });
    const oldPeer = peer();
    const replacement = peer();
    service.connect(created.connectionToken, oldPeer);
    service.connect(created.connectionToken, replacement);
    replacement.send.mockClear();

    expect(service.publish(created.connectionToken, oldPeer, {
      type: "location.publish",
      hash: "#scene/stale-peer",
      baseRevision: 0,
      messageId: "old-1",
    })).toEqual({ kind: "not_connected" });
    expect(service.end(created.connectionToken, oldPeer)).toEqual({
      kind: "not_connected",
    });
    expect(replacement.close).not.toHaveBeenCalled();

    expect(service.publish(created.connectionToken, replacement, {
      type: "location.publish",
      hash: "#scene/replacement-active",
      baseRevision: 0,
      messageId: "new-1",
    }).kind).toBe("accepted");
  });

  it("does not let a replaced peer touch room activity", () => {
    const { service, advance } = makeService();
    const created = service.create({ role: "presenter", initialHash: "#scene/one" });
    const oldPeer = peer();
    const replacement = peer();
    service.connect(created.connectionToken, oldPeer);
    service.connect(created.connectionToken, replacement);

    advance(ROOM_INACTIVITY_TTL_MS);
    service.ping(created.connectionToken, oldPeer);

    expect(service.sweepExpired()).toBe(1);
  });

  it("accepts one publish and rejects a stale competing publish", () => {
    const { service, presenter, audience, presenterToken, audienceToken } =
      connectedRoom();

    expect(
      service.publish(presenterToken, presenter, {
        type: "location.publish",
        hash: "#scene/problem/direct-actions",
        baseRevision: 0,
        messageId: "presenter-1",
      }).kind,
    ).toBe("accepted");
    expect(service.publish(audienceToken, audience, {
      type: "location.publish",
      hash: "#scene/positioning/landscape",
      baseRevision: 0,
      messageId: "audience-stale",
    })).toEqual({
      kind: "stale",
      current: { hash: "#scene/problem/direct-actions", revision: 1 },
    });
    expect(presenter.send).toHaveBeenCalledTimes(1);
    expect(presenter.send).toHaveBeenCalledWith({
      type: "location.snapshot",
      snapshot: { hash: "#scene/problem/direct-actions", revision: 1 },
      originatingMessageId: "presenter-1",
    });
    expect(audience.send).toHaveBeenCalledTimes(2);
    expect(audience.send).toHaveBeenCalledWith({
      type: "location.rejected",
      reason: "stale_revision",
      current: { hash: "#scene/problem/direct-actions", revision: 1 },
      messageId: "audience-stale",
    });
  });

  it("broadcasts presence after a peer disconnects", () => {
    const { service, presenter, audience, presenterToken, audienceToken } =
      connectedRoom();

    service.disconnect(audienceToken, audience);

    expect(presenter.send).toHaveBeenCalledWith({
      type: "presence.snapshot",
      presence: { presenters: 1, audience: 0 },
    });
    expect(audience.send).not.toHaveBeenCalled();
    expect(service.publish(presenterToken, presenter, {
      type: "location.publish",
      hash: "#scene/after-disconnect",
      baseRevision: 0,
      messageId: "presenter-2",
    }).kind).toBe("accepted");
  });

  it("allows reconnecting within the ten-minute empty-room grace", () => {
    const {
      service,
      advance,
      presenter,
      presenterToken,
      audienceToken,
      audience,
    } = connectedRoom();

    service.disconnect(presenterToken, presenter);
    service.disconnect(audienceToken, audience);
    advance(EMPTY_ROOM_GRACE_MS - 1);
    expect(service.sweepExpired()).toBe(0);

    const replacement = peer();
    expect(service.connect(presenterToken, replacement).kind).toBe("connected");
    expect(presenter.close).not.toHaveBeenCalled();
  });

  it("expires an empty room after the ten-minute grace", () => {
    const {
      service,
      advance,
      presenterToken,
      presenter,
      audienceToken,
      audience,
    } = connectedRoom();

    service.disconnect(presenterToken, presenter);
    service.disconnect(audienceToken, audience);
    advance(EMPTY_ROOM_GRACE_MS);

    expect(service.sweepExpired()).toBe(1);
    expect(service.connect(presenterToken, peer()).kind).toBe("not_found");
  });

  it("expires an active room after two hours without activity", () => {
    const { service, advance, presenter, audience } = connectedRoom();

    advance(ROOM_INACTIVITY_TTL_MS - 1);
    expect(service.sweepExpired()).toBe(0);
    advance(1);

    expect(service.sweepExpired()).toBe(1);
    const ended: ServerSyncMessage = {
      type: "session.ended",
      reason: "expired",
    };
    expect(presenter.send).toHaveBeenCalledWith(ended);
    expect(audience.send).toHaveBeenCalledWith(ended);
    expect(presenter.close).toHaveBeenCalledWith(1000, "expired");
    expect(audience.close).toHaveBeenCalledWith(1000, "expired");
  });

  it("counts ping as room activity", () => {
    const { service, advance, presenter, presenterToken } = connectedRoom();

    advance(ROOM_INACTIVITY_TTL_MS - 1);
    service.ping(presenterToken, presenter);
    advance(ROOM_INACTIVITY_TTL_MS - 1);
    expect(service.sweepExpired()).toBe(0);
    advance(1);
    expect(service.sweepExpired()).toBe(1);
  });

  it("ends a room when the presenter terminates it", () => {
    const { service, presenter, audience, presenterToken } = connectedRoom();

    expect(service.end(presenterToken, presenter)).toEqual({ kind: "ended" });
    expect(presenter.send).toHaveBeenCalledWith({
      type: "session.ended",
      reason: "presenter_ended",
    });
    expect(audience.send).toHaveBeenCalledWith({
      type: "session.ended",
      reason: "presenter_ended",
    });
    expect(presenter.close).toHaveBeenCalledWith(1000, "presenter_ended");
    expect(audience.close).toHaveBeenCalledWith(1000, "presenter_ended");
  });

  it("rejects audience termination without ending the room", () => {
    const { service, presenter, audience, audienceToken, presenterToken } =
      connectedRoom();

    expect(service.end(audienceToken, audience)).toEqual({ kind: "forbidden" });
    expect(audience.send).toHaveBeenCalledWith({
      type: "protocol.error",
      code: "forbidden",
      message: "only the presenter can end the session",
    });
    expect(presenter.send).not.toHaveBeenCalled();
    expect(service.publish(presenterToken, presenter, {
      type: "location.publish",
      hash: "#scene/still-active",
      baseRevision: 0,
      messageId: "presenter-3",
    }).kind).toBe("accepted");
  });

  it("does not broadcast location changes between rooms", () => {
    const { service } = makeService();
    const first = connectRoom(service);
    const second = connectRoom(service);

    expect(service.publish(first.presenterToken, first.presenter, {
      type: "location.publish",
      hash: "#scene/first-room",
      baseRevision: 0,
      messageId: "first-room-1",
    }).kind).toBe("accepted");
    expect(first.audience.send).toHaveBeenCalledTimes(1);
    expect(second.presenter.send).not.toHaveBeenCalled();
    expect(second.audience.send).not.toHaveBeenCalled();
  });
});
