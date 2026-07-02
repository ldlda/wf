import { describe, expect, it } from "vitest";
import { Effect, Ref } from "effect";
import { RpcClient, RpcGroup, RpcSerialization } from "@effect/rpc";
import { FetchHttpClient, HttpClient } from "@effect/platform";
import { WorkflowHealth, WorkflowSourcesList } from "./rpcs.js";
import { withEvidenceCapture, type EvidenceRecord } from "./evidence.js";

const LIVE = process.env.LIVE_PYTHON_SERVER === "1";
const describeLive = LIVE ? describe : describe.skip;

const TARGET = "http://127.0.0.1:8765/rpc";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const run = <A>(eff: Effect.Effect<A, any, any>): Promise<A> =>
  Effect.runPromise(eff as Effect.Effect<A, never, never>);

describeLive("interop: live Python server", () => {
  it("workflow.health returns ok", async () => {
    const group = RpcGroup.make(WorkflowHealth);
    const result = await run(
      Effect.gen(function* () {
        const client = yield* RpcClient.make(group as any).pipe(
          Effect.provide(RpcSerialization.layerJsonRpc()),
          Effect.provide(FetchHttpClient.layer),
          Effect.provide(
            RpcClient.layerProtocolHttp({ url: TARGET } as any),
          ),
        );
        return yield* (client as any)["workflow.health"]({});
      }).pipe(
        Effect.scoped,
        Effect.provide(FetchHttpClient.layer),
        Effect.provide(RpcSerialization.layerJsonRpc()),
      ),
    );
    expect(result).toEqual({
      status: "ok",
      store_root: expect.any(String),
    });
  });

  it("workflow.sources.list returns paginated results", async () => {
    const group = RpcGroup.make(WorkflowSourcesList);
    const result = await run(
      Effect.gen(function* () {
        const client = yield* RpcClient.make(group as any).pipe(
          Effect.provide(RpcSerialization.layerJsonRpc()),
          Effect.provide(FetchHttpClient.layer),
          Effect.provide(
            RpcClient.layerProtocolHttp({ url: TARGET } as any),
          ),
        );
        return yield* (client as any)["workflow.sources.list"]({
          limit: 10,
        });
      }).pipe(
        Effect.scoped,
        Effect.provide(FetchHttpClient.layer),
        Effect.provide(RpcSerialization.layerJsonRpc()),
      ),
    );
    const typed = result as {
      sources: unknown[];
      next_cursor: string | null;
      total: number;
    };
    expect(typed.sources).toBeInstanceOf(Array);
    expect(typeof typed.total).toBe("number");
  });

  it("handles standard JSON-RPC errors gracefully", async () => {
    const group = RpcGroup.make(WorkflowSourcesList);
    const exit = await Effect.runPromiseExit(
      Effect.gen(function* () {
        const client = yield* RpcClient.make(group as any).pipe(
          Effect.provide(RpcSerialization.layerJsonRpc()),
          Effect.provide(FetchHttpClient.layer),
          Effect.provide(
            RpcClient.layerProtocolHttp({ url: TARGET } as any),
          ),
        );
        return yield* (client as any)["workflow.sources.list"]({
          cursor: "nonexistent",
        });
      }).pipe(
        Effect.scoped,
        Effect.provide(FetchHttpClient.layer),
        Effect.provide(RpcSerialization.layerJsonRpc()),
      ) as Effect.Effect<unknown, never, never>,
    );
    expect(exit._tag).toBe("Success");
  });

  it("raw evidence capture works", async () => {
    const evidenceRef = Effect.runSync(Ref.make<EvidenceRecord | null>(null));

    const group = RpcGroup.make(WorkflowHealth);
    const result = await run(
      Effect.gen(function* () {
        const httpClient = yield* HttpClient.HttpClient;
        const transformed = withEvidenceCapture(httpClient, evidenceRef);

        const protocolLayer = RpcClient.layerProtocolHttp({
          url: TARGET,
          transformClient: () => transformed,
        } as any);

        const client = yield* RpcClient.make(group as any).pipe(
          Effect.provide(RpcSerialization.layerJsonRpc()),
          Effect.provide(FetchHttpClient.layer),
          Effect.provide(protocolLayer),
        );

        return yield* (client as any)["workflow.health"]({});
      }).pipe(
        Effect.scoped,
        Effect.provide(FetchHttpClient.layer),
        Effect.provide(RpcSerialization.layerJsonRpc()),
      ),
    );

    const evidence = Effect.runSync(Ref.get(evidenceRef));
    expect(evidence).not.toBeNull();
    expect(evidence!.request.url).toContain("/rpc");
    expect(evidence!.response.status).toBe(200);
  });
});
