import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { Either, Schema } from "effect";
import { beforeAll, describe, expect, it } from "vitest";
import { translateJsonSchema } from "./translator.js";

const repositoryRoot = fileURLToPath(new URL("../../../../..", import.meta.url));
const decodeJson = Schema.decodeUnknownSync(Schema.parseJson(Schema.Unknown));

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

let components: Readonly<Record<string, unknown>>;

beforeAll(async () => {
  const text = await readFile(
    `${repositoryRoot}/contracts/workflow-api.manifest.json`,
    "utf8",
  );
  const manifest = decodeJson(text);
  if (!isRecord(manifest) || !isRecord(manifest.components)) {
    throw new Error("invalid checked workflow contract manifest");
  }
  const schemas = manifest.components.schemas;
  if (!isRecord(schemas)) throw new Error("manifest components.schemas is invalid");
  components = schemas;
});

describe("checked workflow manifest translation", () => {
  it("translates and decodes representative health and run results", () => {
    const health = translateJsonSchema(components.HealthResult, { components });
    const run = translateJsonSchema(components.RunResult, { components });
    expect(Either.isRight(health)).toBe(true);
    expect(Either.isRight(run)).toBe(true);
    if (Either.isLeft(health) || Either.isLeft(run)) return;

    expect(
      Either.isRight(
        Schema.decodeUnknownEither(health.right)({
          status: "ok",
          store_root: ".workflow-store",
        }),
      ),
    ).toBe(true);
    expect(
      Either.isRight(
        Schema.decodeUnknownEither(run.right)({
          artifact_id: "art_report",
          artifact_version: 2,
          deployment_id: "report.default",
          diagnostics: [],
          error: null,
          interrupt: null,
          next_actions: {
            can_continue: false,
            can_save_now: null,
            patch_examples: [],
            reason: "run completed",
            recommended_next_tool: null,
            warnings: [],
          },
          outcome: "completed",
          output: { report: "# Report" },
          resume_readiness: null,
          run_id: "run_123",
          status: "completed",
          trace_count: 9,
        }),
      ),
    ).toBe(true);
  });

  it("fails closed on a real oneOf component that is not supported yet", () => {
    const result = translateJsonSchema(components.InputPathBinding, { components });
    expect(Either.isLeft(result)).toBe(true);
    if (Either.isRight(result)) return;
    expect(result.left.keyword).toBe("oneOf");
    expect(result.left.path).toBe("$.properties.path");
  });
});
