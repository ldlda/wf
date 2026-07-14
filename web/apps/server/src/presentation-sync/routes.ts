import type { upgradeWebSocket } from "@hono/node-server";
import {
  decodeClientSyncMessage,
  decodeCreateSessionRequest,
  decodeJoinSessionRequest,
  type DecodeResult,
  type ServerSyncMessage,
  type SessionGrant,
} from "@lda/presentation-sync";
import type { Hono } from "hono";
import type { PresentationPeer, PresentationRoomService } from "./rooms.js";

type PresentationSyncDependencies = {
  readonly rooms: PresentationRoomService;
  readonly upgradeWebSocket: typeof upgradeWebSocket;
};

type DecodeError = Exclude<DecodeResult<unknown>, { readonly ok: true }>["error"];

const invalidRequest = (error: DecodeError) => ({
  error: {
    code: "invalid_request",
    message: error === "message_too_large" ? "request is too large" : "invalid request",
  },
});

const protocolError = (
  code: "invalid_message" | "message_too_large",
): ServerSyncMessage => ({
  type: "protocol.error",
  code,
  message: code === "message_too_large" ? "message is too large" : "invalid message",
});

export const addPresentationSyncRoutes = (
  app: Hono,
  dependencies: PresentationSyncDependencies,
): void => {
  const { rooms, upgradeWebSocket: upgrade } = dependencies;

  app.post("/api/presentation-sync/sessions", async (c) => {
    const decoded = decodeCreateSessionRequest(await c.req.text());
    if (!decoded.ok) return c.json(invalidRequest(decoded.error), 400);
    const grant: SessionGrant = rooms.create(decoded.value);
    return c.json(grant, 201);
  });

  app.post("/api/presentation-sync/sessions/join", async (c) => {
    const decoded = decodeJoinSessionRequest(await c.req.text());
    if (!decoded.ok) return c.json(invalidRequest(decoded.error), 400);
    try {
      const grant: SessionGrant = rooms.join(decoded.value);
      return c.json(grant, 200);
    } catch (error) {
      const message = error instanceof Error ? error.message : "presentation room not found";
      if (message.includes("opposite role")) {
        return c.json({ error: { code: "invalid_role", message } }, 400);
      }
      return c.json(
        { error: { code: "session_not_found", message: "presentation room not found" } },
        404,
      );
    }
  });

  app.get(
    "/api/presentation-sync/ws",
    upgrade((c) => {
      const token = c.req.query("token") ?? "";
      let peer: PresentationPeer | null = null;

      return {
        onOpen(_event, socket) {
          // Keep one stable adapter per socket. The room service compares this exact
          // identity when old replaced sockets later emit their close callbacks.
          peer = {
            send: (message) => socket.send(JSON.stringify(message)),
            close: (code, reason) => socket.close(code, reason),
          };
          if (token === "" || rooms.connect(token, peer).kind === "not_found") {
            peer.send(protocolError("invalid_message"));
            peer.close(1008, "invalid token");
          }
        },
        onMessage(event) {
          if (peer === null) return;
          if (typeof event.data !== "string") {
            peer.send(protocolError("invalid_message"));
            peer.close(1003, "text messages required");
            return;
          }

          const decoded = decodeClientSyncMessage(event.data);
          if (!decoded.ok) {
            const code =
              decoded.error === "message_too_large"
                ? "message_too_large"
                : "invalid_message";
            peer.send(protocolError(code));
            if (code === "message_too_large") peer.close(1009, "message too large");
            return;
          }

          switch (decoded.value.type) {
            case "location.publish":
              rooms.publish(token, decoded.value);
              break;
            case "ping":
              rooms.ping(token);
              break;
            case "session.end":
              rooms.end(token);
              break;
          }
        },
        onClose() {
          if (peer !== null) rooms.disconnect(token, peer);
        },
      };
    }),
  );
};
