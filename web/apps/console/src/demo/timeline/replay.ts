import recordingText from "../recordings/lda-report-success.v1.json?raw";
import { decodeDemoRecording, type DemoEvent, type DemoRecording } from "./models.js";

export const loadCanonicalDemoRecording = (): DemoRecording => {
  let parsed: unknown;
  try {
    parsed = JSON.parse(recordingText);
  } catch (error) {
    throw new Error(
      `canonical demo recording is not valid JSON: ${
        error instanceof Error ? error.message : String(error)
      }`,
    );
  }
  return decodeDemoRecording(parsed);
};

export const nextReplayEvent = (
  recording: DemoRecording,
  appliedCount: number,
): DemoEvent | null => recording.events[appliedCount] ?? null;
