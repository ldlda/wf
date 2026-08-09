import { useEffect, useMemo, useState } from "react";
import { useConsoleWorkspace } from "../context.js";
import {
  createCapabilityClient,
  type CapabilityClient,
} from "../domain/capability-client.js";
import type { CapabilityDetail } from "../domain/capability-models.js";
import type { ConsoleReadExecutor } from "../domain/read-executor.js";

export type AuthoringCapabilityDetailState = {
  readonly phase: "disconnected" | "loading" | "ready" | "error";
  readonly detail: CapabilityDetail | null;
  readonly message: string | null;
};

type Request = {
  readonly name: string;
  readonly target: string;
  readonly executor: ConsoleReadExecutor;
};

type DetailState = {
  readonly request: Request | null;
  readonly detail: CapabilityDetail | null;
  readonly message: string | null;
};

const sameRequest = (left: Request | null, right: Request | null): boolean =>
  left !== null &&
  right !== null &&
  left.name === right.name &&
  left.target === right.target &&
  left.executor === right.executor;

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

export const useAuthoringCapabilityDetail = (
  name: string | null,
): AuthoringCapabilityDetailState => {
  const { connectedTarget, readExecutor } = useConsoleWorkspace();
  const client = useMemo<CapabilityClient | null>(
    () => (readExecutor ? createCapabilityClient(readExecutor) : null),
    [readExecutor],
  );
  const request = useMemo<Request | null>(
    () => {
      if (!client || !connectedTarget || !name || !readExecutor) return null;
      return { name, target: connectedTarget, executor: readExecutor };
    },
    [client, connectedTarget, name, readExecutor],
  );
  const [state, setState] = useState<DetailState>({
    request: null,
    detail: null,
    message: null,
  });

  useEffect(() => {
    if (!client || request === null) return;
    let active = true;
    void client.inspect(request.name)
      .then((detail) => {
        if (!active) return;
        setState({ request, detail, message: null });
      })
      .catch((error: unknown) => {
        if (!active) return;
        setState({ request, detail: null, message: errorMessage(error) });
      });
    return () => {
      active = false;
    };
  }, [client, request]);

  if (request === null) {
    return { phase: "disconnected", detail: null, message: null };
  }
  if (!sameRequest(state.request, request)) {
    return { phase: "loading", detail: null, message: null };
  }
  if (state.message !== null) {
    return { phase: "error", detail: null, message: state.message };
  }
  return { phase: "ready", detail: state.detail, message: null };
};
