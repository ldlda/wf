import { randomUUID } from "node:crypto";
import {
  normalizeJoinCode,
  type ClientSyncMessage,
  type PresentationPresence,
  type PresentationRole,
  type PresentationSnapshot,
  type ServerSyncMessage,
  type SessionGrant,
} from "@lda/presentation-sync";

export const EMPTY_ROOM_GRACE_MS = 10 * 60 * 1_000;
export const ROOM_INACTIVITY_TTL_MS = 2 * 60 * 60 * 1_000;

export type PresentationPeer = {
  readonly send: (message: ServerSyncMessage) => void;
  readonly close: (code: number, reason: string) => void;
};

export type ConnectResult =
  | {
      readonly kind: "connected";
      readonly snapshot: PresentationSnapshot;
      readonly presence: PresentationPresence;
    }
  | { readonly kind: "not_found" };

export type PublishResult =
  | {
      readonly kind: "accepted";
      readonly snapshot: PresentationSnapshot;
    }
  | {
      readonly kind: "stale";
      readonly current: PresentationSnapshot;
    }
  | { readonly kind: "not_found" }
  | { readonly kind: "not_connected" };

export type EndResult =
  | { readonly kind: "ended" }
  | { readonly kind: "forbidden" }
  | { readonly kind: "not_found" }
  | { readonly kind: "not_connected" };

export type PresentationRoomService = ReturnType<
  typeof createPresentationRoomService
>;

type Room = {
  readonly id: string;
  readonly code: string;
  readonly creatorRole: PresentationRole;
  readonly members: Set<Membership>;
  snapshot: PresentationSnapshot;
  lastActivityAt: number;
  emptySince: number | null;
};

type Membership = {
  readonly token: string;
  readonly role: PresentationRole;
  readonly room: Room;
  peer: PresentationPeer | null;
};

const defaultId = (): string => randomUUID();
const defaultCode = (): string => randomUUID().replaceAll("-", "").slice(0, 6);
const defaultToken = (): string => randomUUID();

const nextUnique = (
  makeValue: () => string,
  isUsed: (value: string) => boolean,
  description: string,
): string => {
  for (let attempt = 0; attempt < 1_000; attempt += 1) {
    const value = makeValue();
    if (!isUsed(value)) return value;
  }
  throw new Error(`unable to allocate a unique ${description}`);
};

const makeSnapshotMessage = (
  snapshot: PresentationSnapshot,
  originatingMessageId: string | null,
): ServerSyncMessage => ({
  type: "location.snapshot",
  snapshot,
  originatingMessageId,
});

export const createPresentationRoomService = (options: {
  readonly now?: () => number;
  readonly makeId?: () => string;
  readonly makeCode?: () => string;
  readonly makeToken?: () => string;
} = {}) => {
  const now = options.now ?? Date.now;
  const makeId = options.makeId ?? defaultId;
  const makeCode = options.makeCode ?? defaultCode;
  const makeToken = options.makeToken ?? defaultToken;

  const roomsById = new Map<string, Room>();
  const roomIdByCode = new Map<string, string>();
  const membershipByToken = new Map<string, Membership>();

  const presenceFor = (room: Room): PresentationPresence => {
    let presenters = 0;
    let audience = 0;
    for (const membership of room.members) {
      if (membership.peer === null) continue;
      if (membership.role === "presenter") presenters += 1;
      else audience += 1;
    }
    return { presenters, audience };
  };

  const forEachPeer = (room: Room, callback: (peer: PresentationPeer) => void) => {
    for (const membership of room.members) {
      if (membership.peer !== null) callback(membership.peer);
    }
  };

  const broadcastPresence = (room: Room): PresentationPresence => {
    const presence = presenceFor(room);
    const message: ServerSyncMessage = {
      type: "presence.snapshot",
      presence,
    };
    forEachPeer(room, (peer) => peer.send(message));
    return presence;
  };

  const grantFor = (room: Room, token: string): SessionGrant => ({
    sessionId: room.id,
    code: room.code,
    connectionToken: token,
    websocketPath: "/api/presentation-sync/ws",
    snapshot: room.snapshot,
  });

  const removeRoom = (room: Room): void => {
    roomsById.delete(room.id);
    if (roomIdByCode.get(room.code) === room.id) {
      roomIdByCode.delete(room.code);
    }
    for (const membership of room.members) {
      membershipByToken.delete(membership.token);
    }
  };

  const endRoom = (room: Room, reason: "presenter_ended" | "expired"): void => {
    const message: ServerSyncMessage = { type: "session.ended", reason };
    forEachPeer(room, (peer) => {
      peer.send(message);
      peer.close(1000, reason);
    });
    removeRoom(room);
  };

  return {
    create(input: {
      readonly role: PresentationRole;
      readonly initialHash: string;
    }): SessionGrant {
      const id = nextUnique(makeId, (value) => roomsById.has(value), "room id");
      const code = nextUnique(
        () => normalizeJoinCode(makeCode()),
        (value) => roomIdByCode.has(value),
        "room code",
      );
      const token = nextUnique(
        makeToken,
        (value) => membershipByToken.has(value),
        "connection token",
      );
      const room: Room = {
        id,
        code,
        creatorRole: input.role,
        members: new Set(),
        snapshot: { hash: input.initialHash, revision: 0 },
        lastActivityAt: now(),
        emptySince: null,
      };
      const membership: Membership = {
        token,
        role: input.role,
        room,
        peer: null,
      };
      room.members.add(membership);
      roomsById.set(room.id, room);
      roomIdByCode.set(room.code, room.id);
      membershipByToken.set(membership.token, membership);
      return grantFor(room, token);
    },

    join(input: {
      readonly role: PresentationRole;
      readonly code: string;
    }): SessionGrant {
      const code = normalizeJoinCode(input.code);
      const roomId = roomIdByCode.get(code);
      const room = roomId === undefined ? undefined : roomsById.get(roomId);
      if (room === undefined) {
        throw new Error("presentation room not found");
      }
      if (input.role === room.creatorRole) {
        throw new Error("presentation room requires the opposite role");
      }

      const token = nextUnique(
        makeToken,
        (value) => membershipByToken.has(value),
        "connection token",
      );
      const membership: Membership = {
        token,
        role: input.role,
        room,
        peer: null,
      };
      room.members.add(membership);
      membershipByToken.set(membership.token, membership);
      room.lastActivityAt = now();
      return grantFor(room, token);
    },

    connect(token: string, peer: PresentationPeer): ConnectResult {
      const membership = membershipByToken.get(token);
      const room = membership?.room;
      if (membership === undefined || room === undefined || !roomsById.has(room.id)) {
        return { kind: "not_found" };
      }

      if (membership.peer !== null) {
        membership.peer.close(4001, "replaced");
      }
      membership.peer = peer;
      room.emptySince = null;
      room.lastActivityAt = now();
      peer.send(makeSnapshotMessage(room.snapshot, null));
      const presence = broadcastPresence(room);
      return { kind: "connected", snapshot: room.snapshot, presence };
    },

    disconnect(token: string, peer: PresentationPeer): void {
      const membership = membershipByToken.get(token);
      const room = membership?.room;
      if (
        membership === undefined ||
        room === undefined ||
        !roomsById.has(room.id) ||
        membership.peer === null ||
        membership.peer !== peer
      ) {
        return;
      }

      membership.peer = null;
      room.lastActivityAt = now();
      const presence = presenceFor(room);
      if (presence.presenters + presence.audience === 0) {
        // Empty-room grace starts only after the final active socket leaves;
        // disconnected membership tokens remain valid until this room expires.
        room.emptySince = room.lastActivityAt;
      } else {
        broadcastPresence(room);
      }
    },

    publish(
      token: string,
      message: Extract<ClientSyncMessage, { type: "location.publish" }>,
    ): PublishResult {
      const membership = membershipByToken.get(token);
      const room = membership?.room;
      if (membership === undefined || room === undefined || !roomsById.has(room.id)) {
        return { kind: "not_found" };
      }
      if (membership.peer === null) return { kind: "not_connected" };

      room.lastActivityAt = now();
      if (message.baseRevision !== room.snapshot.revision) {
        membership.peer.send({
          type: "location.rejected",
          reason: "stale_revision",
          current: room.snapshot,
          messageId: message.messageId,
        });
        return { kind: "stale", current: room.snapshot };
      }

      // Equal-base publishes converge by accepting the first one processed;
      // every later publisher receives that already-accepted snapshot as stale.
      room.snapshot = {
        hash: message.hash,
        revision: room.snapshot.revision + 1,
      };
      forEachPeer(room, (peer) =>
        peer.send(makeSnapshotMessage(room.snapshot, message.messageId)),
      );
      return { kind: "accepted", snapshot: room.snapshot };
    },

    ping(token: string): void {
      const membership = membershipByToken.get(token);
      const room = membership?.room;
      if (
        membership === undefined ||
        room === undefined ||
        !roomsById.has(room.id) ||
        membership.peer === null
      ) {
        return;
      }
      room.lastActivityAt = now();
    },

    end(token: string): EndResult {
      const membership = membershipByToken.get(token);
      const room = membership?.room;
      if (membership === undefined || room === undefined || !roomsById.has(room.id)) {
        return { kind: "not_found" };
      }
      if (membership.peer === null) return { kind: "not_connected" };
      if (membership.role !== "presenter") {
        room.lastActivityAt = now();
        membership.peer.send({
          type: "protocol.error",
          code: "forbidden",
          message: "only the presenter can end the session",
        });
        return { kind: "forbidden" };
      }

      endRoom(room, "presenter_ended");
      return { kind: "ended" };
    },

    sweepExpired(): number {
      const currentTime = now();
      let expiredRooms = 0;
      for (const room of [...roomsById.values()]) {
        const emptyExpired =
          room.emptySince !== null &&
          currentTime - room.emptySince >= EMPTY_ROOM_GRACE_MS;
        const inactive =
          currentTime - room.lastActivityAt >= ROOM_INACTIVITY_TTL_MS;
        if (!emptyExpired && !inactive) continue;
        expiredRooms += 1;
        endRoom(room, "expired");
      }
      return expiredRooms;
    },
  };
};
