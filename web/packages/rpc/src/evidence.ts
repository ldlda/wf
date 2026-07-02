import { Context, Effect, Layer, Ref } from "effect";
import { HttpClient, HttpClientRequest, HttpClientResponse } from "@effect/platform";

export type EvidenceRecord = {
  readonly request: {
    readonly url: string;
    readonly method: string;
    readonly body: unknown;
  };
  readonly response: { readonly status: number; readonly body: unknown };
};

export const EvidenceRef = Context.GenericTag<Ref.Ref<EvidenceRecord | null>>(
  "EvidenceRef",
);

export const makeEvidenceLayer = Layer.sync(
  EvidenceRef,
  () => Ref.unsafeMake<EvidenceRecord | null>(null),
);

const readRequestBody = (
  request: HttpClientRequest.HttpClientRequest,
): unknown => {
  const body = request.body;
  if (body._tag === "Uint8Array") {
    try {
      return JSON.parse(new TextDecoder().decode(body.body));
    } catch {
      return body.body;
    }
  }
  if (body._tag === "Raw") {
    return body.body;
  }
  return null;
};

/**
 * Wrap an HttpClient to capture raw request/response evidence per-call.
 *
 * Buffers the response body once, records it for the evidence drawer,
 * then reconstructs the response so RpcClient can still read it.
 */
export const withEvidenceCapture = <E, R>(
  client: HttpClient.HttpClient.With<E, R>,
  ref: Ref.Ref<EvidenceRecord | null>,
): HttpClient.HttpClient.With<E, R> =>
  client.pipe(
    HttpClient.transform((responseEffect, request) =>
      Effect.gen(function* () {
        const response = yield* responseEffect;

        // Buffer the body text once so we can record it AND reconstruct the response
        const bodyText = yield* Effect.catchAll(
          response.text,
          () => Effect.succeed(""),
        );

        let responseBody: unknown;
        try {
          responseBody = JSON.parse(bodyText);
        } catch {
          responseBody = bodyText;
        }

        yield* Ref.set(ref, {
          request: {
            url: request.url,
            method: request.method,
            body: readRequestBody(request),
          },
          response: { status: response.status, body: responseBody },
        });

        // Reconstruct a fresh response from the buffered text so downstream
        // consumers (RpcClient) can still read the body.
        return HttpClientResponse.fromWeb(
          request,
          new Response(bodyText, {
            status: response.status,
            headers: new Headers(
              Object.entries(response.headers as Record<string, string>),
            ),
          }),
        );
      }),
    ),
  );
