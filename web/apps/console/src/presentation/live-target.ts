import { STORAGE_KEY } from "../app/state.js";

export type PresentationTargetState =
  | { readonly mode: "live"; readonly target: string; readonly source: "session-storage" | "default" }
  | { readonly mode: "replay"; readonly target: null; readonly reason: string };

export const DEFAULT_PRESENTATION_TARGET = "http://127.0.0.1:8765/rpc";

const isHttpUrl = (value: string): boolean => {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
};

export const resolvePresentationTarget = (
  storage: Storage | null = typeof sessionStorage === "undefined" ? null : sessionStorage,
): PresentationTargetState => {
  let stored: string | null;
  try {
    stored = storage?.getItem(STORAGE_KEY) ?? null;
  } catch {
    return {
      mode: "replay",
      target: null,
      reason: "session storage is unavailable",
    };
  }

  const target = stored ?? DEFAULT_PRESENTATION_TARGET;
  if (!isHttpUrl(target)) {
    return {
      mode: "replay",
      target: null,
      reason: "presentation target is not an HTTP URL",
    };
  }

  return {
    mode: "live",
    target,
    source: stored ? "session-storage" : "default",
  };
};