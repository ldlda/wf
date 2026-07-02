import * as v from "valibot";

export const DemoEventStageSchema = v.picklist([
  "deployment_check",
  "run_start",
  "interrupt",
  "run_resume",
  "trace_read",
  "completed",
  "failed",
]);

const ResultingIdsSchema = v.object({
  deploymentId: v.nullable(v.string()),
  runId: v.nullable(v.string()),
});

export const DemoEventSchema = v.object({
  id: v.string(),
  sequence: v.pipe(v.number(), v.integer(), v.minValue(0)),
  stage: DemoEventStageSchema,
  operation: v.nullable(v.string()),
  reason: v.string(),
  equivalentCli: v.nullable(v.string()),
  params: v.unknown(),
  rawResponse: v.unknown(),
  interpreted: v.unknown(),
  durationMs: v.pipe(v.number(), v.minValue(0)),
  resultingIds: ResultingIdsSchema,
  recordedAt: v.string(),
});

export const DemoRecordingSchema = v.object({
  schemaVersion: v.literal(1),
  recordingId: v.string(),
  title: v.string(),
  createdAt: v.string(),
  deploymentId: v.literal("lda_report_case_study.default"),
  source: v.literal("reviewed_live_capture"),
  events: v.array(DemoEventSchema),
});

export type DemoEventStage = v.InferOutput<typeof DemoEventStageSchema>;
export type DemoEvent = v.InferOutput<typeof DemoEventSchema>;
export type DemoRecording = v.InferOutput<typeof DemoRecordingSchema>;

export const decodeDemoRecording = (value: unknown): DemoRecording => {
  const recording = v.parse(DemoRecordingSchema, value);
  recording.events.forEach((event, index) => {
    if (event.sequence !== index) {
      throw new Error(`recording event sequence ${event.sequence} does not match index ${index}`);
    }
  });
  return recording;
};
