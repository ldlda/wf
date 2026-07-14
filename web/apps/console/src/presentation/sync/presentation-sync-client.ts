import {
  decodeServerSyncMessage,
  decodeSessionGrant,
  normalizeJoinCode,
  type PresentationRole,
  type ServerSyncMessage,
  type SessionGrant,
} from "@lda/presentation-sync";

export const PRESENTATION_SYNC_GRANT_STORAGE_KEY =
  "lda.presentation-sync.connection.v1";

const RECONNECT_BASE_DELAY_MS = 500;
const RECONNECT_MAX_DELAY_MS = 5_000;

export type PresentationSyncClientEvent =
  | { readonly type: "open" }
  | { readonly type: "message"; readonly message: ServerSyncMessage }
  | {
      readonly type: "reconnecting";
      readonly attempt: number;
      readonly delayMs: number;
    }
  | { readonly type: "ended"; readonly reason: "presenter_ended" | "expired" }
  | {
      readonly type: "failed";
      readonly message: string;
      readonly retryable: boolean;
    };

export type PresentationSyncClientDependencies = {
  readonly fetch: typeof fetch;
  readonly createWebSocket: (url: string) => WebSocket;
  readonly storage: Storage;
  readonly origin: string;
  readonly protocol: string;
  readonly setTimeout: typeof window.setTimeout;
  readonly clearTimeout: typeof window.clearTimeout;
};

export type PresentationSyncClient = ReturnType<
  typeof createPresentationSyncClient
>;

const websocketIsOpen = (socket: WebSocket): boolean => socket.readyState === 1;

const routeForOppositeRole = (role: PresentationRole): "/present" | "/presenter" =>
  role === "presenter" ? "/present" : "/presenter";

export const presentationSyncJoinUrl = (
  role: PresentationRole,
  code: string,
  origin: string,
): string => {
  const url = new URL(routeForOppositeRole(role), origin);
  url.searchParams.set("pair", normalizeJoinCode(code));
  return url.toString();
};

export const createPresentationSyncClient = (
  dependencies: PresentationSyncClientDependencies,
) => {
  let currentGrant: SessionGrant | null = null;
  let socket: WebSocket | null = null;
  let active = false;
  let reconnectAttempt = 0;
  let reconnectTimer: number | null = null;
  let clientMessageCounter = 0;
  let emit: (event: PresentationSyncClientEvent) => void = () => {};

  const clearReconnectTimer = (): void => {
    if (reconnectTimer === null) return;
    dependencies.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  };

  const clearSavedGrant = (): void => {
    dependencies.storage.removeItem(PRESENTATION_SYNC_GRANT_STORAGE_KEY);
  };

  const saveGrant = (grant: SessionGrant): void => {
    dependencies.storage.setItem(
      PRESENTATION_SYNC_GRANT_STORAGE_KEY,
      JSON.stringify(grant),
    );
  };

  const restoreGrant = (): SessionGrant | null => {
    const encoded = dependencies.storage.getItem(
      PRESENTATION_SYNC_GRANT_STORAGE_KEY,
    );
    if (encoded === null) return null;

    const decoded = decodeSessionGrant(encoded);
    if (!decoded.ok) {
      clearSavedGrant();
      return null;
    }
    return decoded.value;
  };

  const websocketUrlFor = (grant: SessionGrant): string => {
    const url = new URL(grant.websocketPath, dependencies.origin);
    url.protocol = dependencies.protocol === "https:" ? "wss:" : "ws:";
    url.searchParams.set("token", grant.connectionToken);
    return url.toString();
  };

  const closeSocket = (): void => {
    const currentSocket = socket;
    socket = null;
    if (currentSocket === null || currentSocket.readyState >= 2) return;
    currentSocket.close(1000, "closed");
  };

  const scheduleReconnect = (): void => {
    if (!active || currentGrant === null || reconnectTimer !== null) return;

    reconnectAttempt += 1;
    const delayMs =
      reconnectAttempt <= 3
        ? RECONNECT_BASE_DELAY_MS * 2 ** (reconnectAttempt - 1)
        : RECONNECT_MAX_DELAY_MS;
    emit({ type: "reconnecting", attempt: reconnectAttempt, delayMs });
    reconnectTimer = dependencies.setTimeout(() => {
      reconnectTimer = null;
      if (active && currentGrant !== null) openSocket();
    }, delayMs);
  };

  const handleServerMessage = (
    currentSocket: WebSocket,
    data: unknown,
  ): void => {
    if (currentSocket !== socket || !active) return;
    if (typeof data !== "string") {
      active = false;
      clearSavedGrant();
      emit({
        type: "failed",
        message: "server sent a non-text synchronization frame",
        retryable: false,
      });
      currentSocket.close(1003, "text messages required");
      return;
    }

    const decoded = decodeServerSyncMessage(data);
    if (!decoded.ok) {
      active = false;
      clearSavedGrant();
      emit({
        type: "failed",
        message: "server sent an invalid synchronization frame",
        retryable: false,
      });
      currentSocket.close(1003, "invalid server message");
      return;
    }

    const message = decoded.value;
    if (message.type === "session.ended") {
      active = false;
      clearReconnectTimer();
      clearSavedGrant();
      emit({ type: "ended", reason: message.reason });
      return;
    }

    if (
      message.type === "protocol.error" &&
      (message.code === "forbidden" || message.code === "invalid_message")
    ) {
      active = false;
      clearReconnectTimer();
      clearSavedGrant();
      emit({ type: "failed", message: message.message, retryable: false });
      currentSocket.close(1008, message.message);
      return;
    }

    emit({ type: "message", message });
  };

  const openSocket = (): void => {
    if (!active || currentGrant === null) return;
    const nextSocket = dependencies.createWebSocket(websocketUrlFor(currentGrant));
    socket = nextSocket;

    nextSocket.onopen = () => {
      if (nextSocket !== socket || !active) return;
      reconnectAttempt = 0;
      emit({ type: "open" });
    };
    nextSocket.onmessage = (event) => {
      handleServerMessage(nextSocket, event.data);
    };
    nextSocket.onerror = () => {
      if (nextSocket === socket && active) nextSocket.close(1006, "socket error");
    };
    nextSocket.onclose = (event) => {
      if (nextSocket !== socket) return;
      socket = null;
      if (!active) return;
      if (event.code === 1008) {
        active = false;
        clearReconnectTimer();
        clearSavedGrant();
        emit({
          type: "failed",
          message: event.reason || "synchronization session is no longer valid",
          retryable: false,
        });
        return;
      }
      scheduleReconnect();
    };
  };

  const requestGrant = async (
    path: "/api/presentation-sync/sessions" | "/api/presentation-sync/sessions/join",
    body: unknown,
  ): Promise<SessionGrant> => {
    const response = await dependencies.fetch(
      new URL(path, dependencies.origin).toString(),
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      },
    );
    const responseText = await response.text();
    if (!response.ok) {
      let message = "unable to establish presentation synchronization";
      try {
        const parsed = JSON.parse(responseText) as unknown;
        if (
          typeof parsed === "object" &&
          parsed !== null &&
          "error" in parsed &&
          typeof parsed.error === "object" &&
          parsed.error !== null &&
          "message" in parsed.error &&
          typeof parsed.error.message === "string"
        ) {
          message = parsed.error.message;
        }
      } catch {
        // The status is still enough to expose a retryable pairing failure.
      }
      throw new Error(message);
    }

    const decoded = decodeSessionGrant(responseText);
    if (!decoded.ok) throw new Error("server returned an invalid session grant");
    saveGrant(decoded.value);
    return decoded.value;
  };

  const create = async (
    role: PresentationRole,
    initialHash: string,
  ): Promise<SessionGrant> =>
    requestGrant("/api/presentation-sync/sessions", { role, initialHash });

  const join = async (
    role: PresentationRole,
    code: string,
  ): Promise<SessionGrant> =>
    requestGrant("/api/presentation-sync/sessions/join", {
      role,
      code: normalizeJoinCode(code),
    });

  const connect = (
    grant: SessionGrant,
    onEvent: (event: PresentationSyncClientEvent) => void,
  ): void => {
    active = true;
    currentGrant = grant;
    emit = onEvent;
    reconnectAttempt = 0;
    clearReconnectTimer();
    saveGrant(grant);
    closeSocket();
    openSocket();
  };

  const publish = (hash: string, baseRevision: number): string | null => {
    if (socket === null || !websocketIsOpen(socket) || !active) return null;
    clientMessageCounter += 1;
    const messageId = `${clientMessageCounter}-${globalThis.crypto.randomUUID()}`;
    socket.send(
      JSON.stringify({
        type: "location.publish",
        hash,
        baseRevision,
        messageId,
      }),
    );
    return messageId;
  };

  const end = (): void => {
    active = false;
    clearReconnectTimer();
    if (socket !== null && websocketIsOpen(socket)) {
      socket.send(JSON.stringify({ type: "session.end" }));
    }
    clearSavedGrant();
    closeSocket();
  };

  const leave = (): void => {
    active = false;
    clearReconnectTimer();
    clearSavedGrant();
    closeSocket();
  };

  const dispose = (): void => {
    active = false;
    clearReconnectTimer();
    closeSocket();
    emit = () => {};
  };

  return {
    create,
    join,
    connect,
    publish,
    end,
    leave,
    restoreGrant,
    dispose,
  };
};
