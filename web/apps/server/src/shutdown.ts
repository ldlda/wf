type ShutdownClient = {
  readonly close: (code: number, reason: string) => void;
  readonly terminate: () => void;
};

type ShutdownHttpServer = {
  readonly close: (callback: (error?: Error) => void) => unknown;
  readonly closeAllConnections?: () => void;
};

type ShutdownWebSocketServer = {
  readonly clients: ReadonlySet<ShutdownClient>;
  readonly close: (callback: (error?: Error) => void) => void;
};

type ForceTimeout = NodeJS.Timeout;

export const shutdownServer = (dependencies: {
  readonly server: ShutdownHttpServer;
  readonly wss: ShutdownWebSocketServer;
  readonly exit: (code: number) => void;
  readonly setForceTimeout?: (
    callback: () => void,
    milliseconds: number,
  ) => ForceTimeout;
  readonly clearForceTimeout?: (timeout: ForceTimeout) => void;
  readonly forceAfterMs?: number;
}): void => {
  const {
    server,
    wss,
    exit,
    setForceTimeout = (callback, milliseconds) =>
      setTimeout(callback, milliseconds) as NodeJS.Timeout,
    clearForceTimeout = (timeout) => clearTimeout(timeout),
    forceAfterMs = 5_000,
  } = dependencies;
  let httpClosed = false;
  let webSocketsClosed = false;
  let finished = false;

  const finish = (code: number): void => {
    if (finished) return;
    finished = true;
    clearForceTimeout(forceTimeout);
    exit(code);
  };
  const finishNormallyWhenClosed = (): void => {
    if (httpClosed && webSocketsClosed) finish(0);
  };

  // A WebSocket server waits for clients to disconnect before its close callback;
  // initiate their closing handshakes before waiting on either server boundary.
  for (const client of wss.clients) client.close(1001, "server shutdown");

  const forceTimeout = setForceTimeout(() => {
    for (const client of wss.clients) client.terminate();
    server.closeAllConnections?.();
    finish(1);
  }, forceAfterMs);
  forceTimeout.unref();

  wss.close((error) => {
    if (error) {
      finish(1);
      return;
    }
    webSocketsClosed = true;
    finishNormallyWhenClosed();
  });
  server.close((error) => {
    if (error) {
      finish(1);
      return;
    }
    httpClosed = true;
    finishNormallyWhenClosed();
  });
};
