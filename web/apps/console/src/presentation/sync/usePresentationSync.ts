import {
  useEffect,
  useLayoutEffect,
  useRef,
  useSyncExternalStore,
} from "react";
import {
  normalizeJoinCode,
  type PresentationRole,
  type PresentationSnapshot,
  type SessionGrant,
} from "@lda/presentation-sync";
import {
  createPresentationSyncClient,
  type PresentationSyncClient,
  type PresentationSyncClientDependencies,
} from "./presentation-sync-client.js";
import {
  initialPresentationSyncState,
  presentationSyncReducer,
  type PresentationSyncController,
  type PresentationSyncState,
} from "./presentation-sync-state.js";

export type PresentationSyncHookDependencies =
  Partial<PresentationSyncClientDependencies> & {
    readonly location?: Pick<Location, "href" | "search">;
    readonly history?: { readonly replaceState: unknown };
  };

export type UsePresentationSyncOptions = {
  readonly role: PresentationRole;
  readonly currentHash: string;
  readonly applyRemoteHash: (hash: string) => void;
  readonly dependencies?: PresentationSyncHookDependencies;
  readonly client?: PresentationSyncClient;
};

type BrowserUrlState = {
  readonly location: Pick<Location, "href" | "search">;
  readonly history: { readonly replaceState: unknown };
};

const emptyBrowserUrlState: BrowserUrlState = {
  location: { href: "http://localhost/", search: "" },
  history: { replaceState: () => {} },
};

type InternalController = PresentationSyncController & {
  readonly subscribe: (listener: () => void) => () => void;
  readonly getSnapshot: () => PresentationSyncState;
  readonly mount: () => void;
  readonly dispose: () => void;
  readonly publish: (hash: string) => string | null;
  readonly restoreSavedGrant: () => SessionGrant | null;
  readonly restoreGrant: (grant: SessionGrant) => void;
  readonly resumeJoinSession: (code: string) => void;
  readonly browserUrl: BrowserUrlState;
};

type LastOperation =
  | { readonly kind: "create" }
  | { readonly kind: "join"; readonly code: string }
  | null;

type PendingJoin = {
  readonly code: string;
  readonly promise: Promise<SessionGrant>;
};

const defaultBrowserDependencies = (): {
  readonly client: PresentationSyncClientDependencies;
  readonly url: BrowserUrlState;
} => {
  const browserWindow = globalThis.window;
  return {
    client: {
      fetch: browserWindow.fetch.bind(browserWindow),
      createWebSocket: (url) => new browserWindow.WebSocket(url),
      storage: browserWindow.sessionStorage,
      origin: browserWindow.location.origin,
      protocol: browserWindow.location.protocol,
      setTimeout: browserWindow.setTimeout.bind(browserWindow),
      clearTimeout: browserWindow.clearTimeout.bind(browserWindow),
    },
    url: {
      location: browserWindow.location,
      history: browserWindow.history,
    },
  };
};

const hasCompleteClientDependencies = (
  dependencies: PresentationSyncHookDependencies | undefined,
): dependencies is PresentationSyncClientDependencies &
  Pick<PresentationSyncHookDependencies, "location" | "history"> =>
  dependencies?.fetch !== undefined &&
  dependencies.createWebSocket !== undefined &&
  dependencies.storage !== undefined &&
  dependencies.origin !== undefined &&
  dependencies.protocol !== undefined &&
  dependencies.setTimeout !== undefined &&
  dependencies.clearTimeout !== undefined;

const browserDependenciesFor = (
  dependencies: PresentationSyncHookDependencies | undefined,
  needsClient: boolean,
): {
  readonly client: PresentationSyncClientDependencies | null;
  readonly url: BrowserUrlState;
} => {
  const { location, history, ...clientOverrides } = dependencies ?? {};
  const completeClient = hasCompleteClientDependencies(dependencies);
  if (!needsClient) {
    return {
      client: null,
      url: {
        location: location ?? emptyBrowserUrlState.location,
        history: history ?? emptyBrowserUrlState.history,
      },
    };
  }

  if (completeClient) {
    return {
      client: dependencies,
      url: {
        location: location ?? emptyBrowserUrlState.location,
        history: history ?? emptyBrowserUrlState.history,
      },
    };
  }

  const defaults = defaultBrowserDependencies();
  return {
    client: { ...defaults.client, ...clientOverrides } as PresentationSyncClientDependencies,
    url: {
      location: location ?? defaults.url.location,
      history: history ?? defaults.url.history,
    },
  };
};

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

const createController = (options: {
  readonly client: PresentationSyncClient;
  readonly getRole: () => PresentationRole;
  readonly getCurrentHash: () => string;
  readonly applyRemoteHash: (hash: string) => void;
  readonly browserUrl: BrowserUrlState;
}): InternalController => {
  let state: PresentationSyncState = initialPresentationSyncState;
  let mounted = true;
  let operationGeneration = 0;
  let currentGrant: SessionGrant | null = null;
  let lastOperation: LastOperation = null;
  let pendingJoin: PendingJoin | null = null;
  const listeners = new Set<() => void>();
  const pendingMessageIds = new Set<string>();

  const notify = (): void => {
    for (const listener of listeners) listener();
  };

  const dispatch = (
    action: Parameters<typeof presentationSyncReducer>[1],
  ): void => {
    const nextState = presentationSyncReducer(state, action);
    if (nextState === state) return;
    state = nextState;
    notify();
  };

  const beginOperation = (): number => {
    operationGeneration += 1;
    return operationGeneration;
  };

  const isCurrentOperation = (generation: number): boolean =>
    mounted && generation === operationGeneration;

  const applySnapshot = (snapshot: PresentationSnapshot): void => {
    if (snapshot.hash === options.getCurrentHash()) return;

    options.applyRemoteHash(snapshot.hash);
  };

  const handleClientEvent = (event: Parameters<PresentationSyncClient["connect"]>[1] extends (
    event: infer Event,
  ) => void
    ? Event
    : never): void => {
    if (!mounted) return;

    switch (event.type) {
      case "open":
        return;
      case "reconnecting":
        dispatch({ type: "socket_reconnecting" });
        return;
      case "ended":
        currentGrant = null;
        pendingMessageIds.clear();
        dispatch({ type: "session_ended", reason: event.reason });
        return;
      case "failed":
        currentGrant = null;
        pendingMessageIds.clear();
        dispatch({
          type: "failed",
          message: event.message,
          retryable: event.retryable,
        });
        return;
      case "message": {
        const message = event.message;
        if (message.type === "location.snapshot") {
          const isOwnPublish =
            message.originatingMessageId !== null &&
            pendingMessageIds.delete(message.originatingMessageId);
          if (!isOwnPublish) applySnapshot(message.snapshot);
          dispatch({ type: "location_snapshot", snapshot: message.snapshot });
          return;
        }
        if (message.type === "location.rejected") {
          pendingMessageIds.delete(message.messageId);
          applySnapshot(message.current);
          dispatch({ type: "location_rejected", snapshot: message.current });
          return;
        }
        if (message.type === "presence.snapshot") {
          dispatch({ type: "presence_received", presence: message.presence });
          return;
        }
        if (message.type === "protocol.error") {
          dispatch({
            type: "failed",
            message: message.message,
            retryable: false,
          });
        }
        return;
      }
    }
  };

  const connectGrant = (grant: SessionGrant): void => {
    currentGrant = grant;
    dispatch({ type: "grant_received", grant });
    options.client.connect(grant, handleClientEvent);
  };

  const publish = (hash: string): string | null => {
    if (state.kind !== "connected") return null;
    const messageId = options.client.publish(hash, state.snapshot.revision);
    if (messageId !== null) pendingMessageIds.add(messageId);
    return messageId;
  };

  const restoreSavedGrant = (): SessionGrant | null =>
    options.client.restoreGrant();

  const restoreGrant = (grant: SessionGrant): void => {
    if (!mounted) return;
    connectGrant(grant);
  };

  const startSession = async (): Promise<void> => {
    const generation = beginOperation();
    lastOperation = { kind: "create" };
    currentGrant = null;
    pendingMessageIds.clear();
    options.client.leave();
    dispatch({ type: "start_create" });
    try {
      const grant = await options.client.create(
        options.getRole(),
        options.getCurrentHash(),
      );
      if (!isCurrentOperation(generation)) return;
      connectGrant(grant);
    } catch (error) {
      if (isCurrentOperation(generation)) {
        dispatch({
          type: "failed",
          message: errorMessage(error),
          retryable: true,
        });
      }
    }
  };

  const joinSession = async (
    code: string,
    reusePending = false,
  ): Promise<void> => {
    const generation = beginOperation();
    const normalizedCode = normalizeJoinCode(code);
    const reusableJoin =
      reusePending && pendingJoin?.code === normalizedCode ? pendingJoin : null;
    lastOperation = { kind: "join", code: normalizedCode };
    currentGrant = null;
    pendingMessageIds.clear();
    options.client.leave();
    dispatch({ type: "start_join", code: normalizedCode });

    let request: Promise<SessionGrant> | null = null;
    try {
      request =
        reusableJoin?.promise ?? options.client.join(options.getRole(), normalizedCode);
      if (reusableJoin === null) {
        pendingJoin = { code: normalizedCode, promise: request };
      }
      const grant = await request;
      if (pendingJoin?.promise === request) pendingJoin = null;
      if (!isCurrentOperation(generation)) return;
      connectGrant(grant);
    } catch (error) {
      if (request !== null && pendingJoin?.promise === request) pendingJoin = null;
      if (isCurrentOperation(generation)) {
        dispatch({
          type: "failed",
          message: errorMessage(error),
          retryable: true,
        });
      }
    }
  };

  const resumeJoinSession = (code: string): void => {
    void joinSession(code, true);
  };

  const retry = (): void => {
    if (lastOperation?.kind === "create") {
      void startSession();
      return;
    }
    if (lastOperation?.kind === "join") void joinSession(lastOperation.code, false);
  };

  const leaveSession = (): void => {
    beginOperation();
    currentGrant = null;
    pendingMessageIds.clear();
    options.client.leave();
    dispatch({ type: "left" });
  };

  const endSession = (): void => {
    beginOperation();
    currentGrant = null;
    pendingMessageIds.clear();
    options.client.end();
    dispatch({ type: "session_ended", reason: "presenter_ended" });
  };

  const subscribe = (listener: () => void): (() => void) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
  };

  const getSnapshot = (): PresentationSyncState => state;

  const mount = (): void => {
    mounted = true;
  };

  const dispose = (): void => {
    beginOperation();
    mounted = false;
    options.client.dispose();
  };

  return {
    get state() {
      return state;
    },
    startSession,
    joinSession,
    retry,
    leaveSession,
    endSession,
    subscribe,
    getSnapshot,
    mount,
    dispose,
    publish,
    restoreSavedGrant,
    restoreGrant,
    resumeJoinSession,
    browserUrl: options.browserUrl,
  };
};

const pairCodeFromUrl = (url: BrowserUrlState): string | null => {
  const pair = new URL(url.location.href).searchParams.get("pair");
  if (pair === null || normalizeJoinCode(pair) === "") return null;

  const consumed = new URL(url.location.href);
  consumed.searchParams.delete("pair");
  if (typeof url.history.replaceState === "function") {
    url.history.replaceState(
      null,
      "",
      `${consumed.pathname}${consumed.search}${consumed.hash}`,
    );
  }
  return normalizeJoinCode(pair);
};

export const usePresentationSync = ({
  role,
  currentHash,
  applyRemoteHash,
  dependencies,
  client: injectedClient,
}: UsePresentationSyncOptions): PresentationSyncController => {
  const roleRef = useRef(role);
  const currentHashRef = useRef(currentHash);
  const applyRemoteHashRef = useRef(applyRemoteHash);
  const remoteHashInFlightRef = useRef<string | null>(null);
  const lastObservedHashRef = useRef(currentHash);

  useLayoutEffect(() => {
    roleRef.current = role;
    currentHashRef.current = currentHash;
    applyRemoteHashRef.current = applyRemoteHash;
  }, [applyRemoteHash, currentHash, role]);

  const controllerRef = useRef<InternalController | null>(null);
  const pairCodeRef = useRef<string | null>(null);
  if (controllerRef.current === null) {
    const browser = browserDependenciesFor(dependencies, injectedClient === undefined);
    const client =
      injectedClient ??
      (browser.client === null
        ? (() => { throw new Error("presentation sync client dependencies unavailable"); })()
        : createPresentationSyncClient(browser.client));
    controllerRef.current = createController({
      client,
      getRole: () => roleRef.current,
      getCurrentHash: () => currentHashRef.current,
      applyRemoteHash: (hash) => {
        // Set this immediately before applying so the next hash effect consumes
        // the remote update instead of echoing it as another revision.
        remoteHashInFlightRef.current = hash;
        applyRemoteHashRef.current(hash);
      },
      browserUrl: browser.url,
    });
  }
  const controller = controllerRef.current;
  if (controller === null) throw new Error("presentation sync controller unavailable");
  const state = useSyncExternalStore(
    controller.subscribe,
    controller.getSnapshot,
    controller.getSnapshot,
  );

  useEffect(() => {
    controller.mount();
    const restoredGrant = controller.restoreSavedGrant();
    if (restoredGrant !== null) controller.restoreGrant(restoredGrant);
    else {
      const pairCode = pairCodeRef.current ?? pairCodeFromUrl(controller.browserUrl);
      pairCodeRef.current = pairCode;
      if (pairCode !== null) controller.resumeJoinSession(pairCode);
    }
    return () => controller.dispose();
  }, [controller, injectedClient]);

  useEffect(() => {
    const remoteHash = remoteHashInFlightRef.current;
    if (remoteHash !== null) {
      if (remoteHash === currentHash) {
        lastObservedHashRef.current = currentHash;
        remoteHashInFlightRef.current = null;
        return;
      }

      // A rerender caused by connection state can observe the old hash before
      // the route callback updates it. Keep suppression armed for that case,
      // but treat a genuinely changed hash as local navigation.
      if (lastObservedHashRef.current === currentHash) return;
      remoteHashInFlightRef.current = null;
    }

    if (lastObservedHashRef.current === currentHash) return;
    lastObservedHashRef.current = currentHash;
    if (state.kind !== "connected") return;

    controller.publish(currentHash);
  }, [controller, currentHash, state.kind]);

  return {
    state,
    startSession: controller.startSession,
    joinSession: controller.joinSession,
    retry: controller.retry,
    leaveSession: controller.leaveSession,
    endSession: controller.endSession,
  };
};
