import { Context, Effect, Layer, Ref, Stream } from "effect";
import {
  HttpBody,
  HttpClient,
  HttpClientRequest,
  HttpClientResponse,
} from "@effect/platform";
import {
  RpcProtocolError,
  UpstreamResponseTooLargeError,
} from "./errors.js";

export type EvidenceRecord = {
  readonly request: {
    readonly url: string;
    readonly method: string;
    readonly body: unknown;
  };
  readonly response: {
    readonly status: number;
    readonly body: unknown;
  } | null;
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
    if (typeof body.body !== "string") return body.body;
    try {
      return JSON.parse(body.body);
    } catch {
      return body.body;
    }
  }
  return null;
};

const bodyText = (body: HttpBody.HttpBody): string | null => {
  if (body._tag === "Uint8Array") {
    return new TextDecoder().decode(body.body);
  }
  if (body._tag === "Raw" && typeof body.body === "string") {
    return body.body;
  }
  return null;
};

const sanitizeJsonRpcRequest = (
  request: HttpClientRequest.HttpClientRequest,
): HttpClientRequest.HttpClientRequest => {
  const text = bodyText(request.body);
  if (text === null) return request;

  let body: unknown;
  try {
    body = JSON.parse(text);
  } catch {
    return request;
  }
  if (!isRecord(body) || Array.isArray(body) || body.jsonrpc !== "2.0") {
    return request;
  }

  const sanitized = {
    jsonrpc: "2.0",
    method: body.method,
    params: "params" in body ? body.params : undefined,
    id: "id" in body ? body.id : undefined,
  };

  return HttpClientRequest.modify(request, {
    body: HttpBody.text(JSON.stringify(sanitized), "application/json"),
  });
};

const readBoundedText = (
  response: HttpClientResponse.HttpClientResponse,
  maxResponseBytes: number,
): Effect.Effect<string, never> => {
  const declaredLength = Number(response.headers["content-length"] ?? "0");
  if (Number.isFinite(declaredLength) && declaredLength > maxResponseBytes) {
    return Effect.die(
      new UpstreamResponseTooLargeError({
        message: `response exceeds ${maxResponseBytes} bytes`,
      }),
    );
  }

  return Stream.runFoldEffect(
    response.stream,
    { chunks: [] as Uint8Array[], size: 0 },
    (accumulator, chunk) => {
      const size = accumulator.size + chunk.byteLength;
      if (size > maxResponseBytes) {
        return Effect.die(
          new UpstreamResponseTooLargeError({
            message: `response exceeds ${maxResponseBytes} bytes`,
          }),
        );
      }
      accumulator.chunks.push(chunk);
      return Effect.succeed({ chunks: accumulator.chunks, size });
    },
  ).pipe(
    Effect.map(({ chunks, size }) => {
      const bytes = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) {
        bytes.set(chunk, offset);
        offset += chunk.byteLength;
      }
      return new TextDecoder().decode(bytes);
    }),
    Effect.orDie,
  );
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const downstreamRpcBodyText = (responseBody: unknown, bodyText: string): string => {
  if (!isRecord(responseBody) || Array.isArray(responseBody) || !("jsonrpc" in responseBody)) {
    return bodyText;
  }

  const requestId = "id" in responseBody ? String(responseBody.id) : "";
  if ("result" in responseBody) {
    return JSON.stringify([
      {
        _tag: "Exit",
        requestId,
        exit: { _tag: "Success", value: responseBody.result },
      },
    ]);
  }
  if ("error" in responseBody) {
    return JSON.stringify([
      {
        _tag: "Exit",
        requestId,
        exit: {
          _tag: "Failure",
          cause: { _tag: "Fail", error: responseBody.error },
        },
      },
    ]);
  }
  return bodyText;
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
  maxResponseBytes: number,
): HttpClient.HttpClient.With<E, R> =>
  client.pipe(
    HttpClient.mapRequest(sanitizeJsonRpcRequest),
    HttpClient.tapRequest((request) =>
      Ref.set(ref, {
        request: {
          url: request.url,
          method: request.method,
          body: readRequestBody(request),
        },
        response: null,
      }),
    ),
    HttpClient.transform((responseEffect, request) =>
      Effect.gen(function* () {
        const response = yield* responseEffect;
        const bodyText = yield* readBoundedText(response, maxResponseBytes);

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

        if (response.status >= 300 && response.status < 400) {
          return yield* Effect.die(
            new RpcProtocolError({
              message: "upstream redirects are not allowed",
            }),
          );
        }

        // RpcClient's HTTP protocol expects Effect-RPC response messages, while
        // the Python wf server returns standard JSON-RPC objects. Preserve the
        // raw object for evidence and translate only the reconstructed body.
        const headers = new Headers(response.headers);
        // The body is rewritten for Effect-RPC, so upstream body metadata no
        // longer describes the reconstructed Response.
        headers.delete("content-length");
        headers.delete("content-encoding");
        headers.delete("transfer-encoding");
        return HttpClientResponse.fromWeb(
          request,
          new Response(downstreamRpcBodyText(responseBody, bodyText), {
            status: response.status,
            headers,
          }),
        );
      }),
    ),
  );
