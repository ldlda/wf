export type TraceFrameView = {
  readonly nodeId: string;
  readonly stepType: string;
  readonly outcome: string;
  readonly inputSummary: string;
  readonly outputSummary: string;
  readonly stateChangeCount: number;
  readonly raw: Record<string, unknown>;
};

type TraceFrame = {
  readonly nodeId: string;
  readonly stepType: string;
  readonly resolvedInput: Record<string, unknown>;
  readonly outcome: string;
  readonly output: Record<string, unknown>;
  readonly stateChanges: Record<string, unknown>;
};

type TracePage = {
  readonly frames: ReadonlyArray<TraceFrame>;
  readonly traceStart: number;
  readonly traceLimit: number;
  readonly traceTruncated: boolean;
};

type TraceFramesResult = {
  readonly frames: ReadonlyArray<TraceFrameView>;
  readonly traceStart: number;
  readonly traceLimit: number;
  readonly traceTruncated: boolean;
};

const summarizeObject = (obj: Record<string, unknown>, maxKeys = 3): string => {
  const keys = Object.keys(obj);
  if (keys.length === 0) return "{}";
  const displayed = keys.slice(0, maxKeys);
  const parts = displayed.map((k) => `${k}: ${typeof obj[k]}`);
  if (keys.length > maxKeys) {
    parts.push(`+${keys.length - maxKeys} more`);
  }
  return `{ ${parts.join(", ")} }`;
};

export const buildTraceFrames = (page: TracePage): TraceFramesResult => {
  const frames: TraceFrameView[] = page.frames.map((frame) => ({
    nodeId: frame.nodeId,
    stepType: frame.stepType,
    outcome: frame.outcome,
    inputSummary: summarizeObject(frame.resolvedInput),
    outputSummary: summarizeObject(frame.output),
    stateChangeCount: Object.keys(frame.stateChanges).length,
    raw: frame as unknown as Record<string, unknown>,
  }));

  return {
    frames,
    traceStart: page.traceStart,
    traceLimit: page.traceLimit,
    traceTruncated: page.traceTruncated,
  };
};
