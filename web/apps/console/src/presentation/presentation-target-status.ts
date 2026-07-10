export type PresentationTargetHealth =
  | { readonly kind: "replay"; readonly label: string; readonly detail: string }
  | { readonly kind: "checking"; readonly target: string; readonly label: string; readonly detail: string }
  | { readonly kind: "ready"; readonly target: string; readonly label: string; readonly detail: string }
  | { readonly kind: "active"; readonly target: string; readonly label: string; readonly detail: string }
  | { readonly kind: "failed"; readonly target: string | null; readonly label: string; readonly detail: string };

export type TargetProbeState = "none" | "checking" | "ready" | "failed";

const shortTarget = (target: string): string => {
  try {
    const url = new URL(target);
    return `${url.hostname}:${url.port || (url.protocol === "https:" ? "443" : "80")}`;
  } catch {
    return target;
  }
};

export const presentationTargetHealth = ({
  target,
  probe,
  liveActive,
  failureReason,
}: {
  readonly target: string | null;
  readonly probe: TargetProbeState;
  readonly liveActive: boolean;
  readonly failureReason?: string | undefined;
}): PresentationTargetHealth => {
  if (!target) {
    return {
      kind: "replay",
      label: "Replay evidence",
      detail: "reviewed recording",
    };
  }

  if (liveActive && probe === "ready") {
    return {
      kind: "active",
      target,
      label: "Live run active",
      detail: `operations sent to ${shortTarget(target)}`,
    };
  }

  if (probe === "ready") {
    return {
      kind: "ready",
      target,
      label: "Live target ready",
      detail: shortTarget(target),
    };
  }

  if (probe === "checking") {
    return {
      kind: "checking",
      target,
      label: "Live target configured",
      detail: "checking",
    };
  }

  return {
    kind: "failed",
    target,
    label: "Replay fallback",
    detail: failureReason ?? "live target unreachable",
  };
};