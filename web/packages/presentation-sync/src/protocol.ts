import { Schema } from "effect";

export const MAX_SYNC_MESSAGE_BYTES = 16 * 1024;
export const MAX_PRESENTATION_HASH_LENGTH = 2_048;
export const JOIN_CODE_LENGTH = 6;

const MAX_MESSAGE_ID_LENGTH = 128;

export type PresentationRole = "presenter" | "audience";

export type PresentationSnapshot = {
  readonly hash: string;
  readonly revision: number;
};

export type PresentationPresence = {
  readonly presenters: number;
  readonly audience: number;
};

export type CreateSessionRequest = {
  readonly role: PresentationRole;
  readonly initialHash: string;
};

export type JoinSessionRequest = {
  readonly role: PresentationRole;
  readonly code: string;
};

export type SessionGrant = {
  readonly sessionId: string;
  readonly code: string;
  readonly connectionToken: string;
  readonly websocketPath: "/api/presentation-sync/ws";
  readonly snapshot: PresentationSnapshot;
};

export type ClientSyncMessage =
  | {
      readonly type: "location.publish";
      readonly hash: string;
      readonly baseRevision: number;
      readonly messageId: string;
    }
  | { readonly type: "session.end" }
  | { readonly type: "ping"; readonly nonce: string };

export type ServerSyncMessage =
  | {
      readonly type: "location.snapshot";
      readonly snapshot: PresentationSnapshot;
      readonly originatingMessageId: string | null;
    }
  | {
      readonly type: "presence.snapshot";
      readonly presence: PresentationPresence;
    }
  | {
      readonly type: "location.rejected";
      readonly reason: "stale_revision";
      readonly current: PresentationSnapshot;
      readonly messageId: string;
    }
  | {
      readonly type: "session.ended";
      readonly reason: "presenter_ended" | "expired";
    }
  | {
      readonly type: "protocol.error";
      readonly code: "invalid_message" | "message_too_large" | "forbidden";
      readonly message: string;
    };

export type DecodeResult<T> =
  | { readonly ok: true; readonly value: T }
  | {
      readonly ok: false;
      readonly error: "invalid_json" | "invalid_message" | "message_too_large";
    };

export const isCanonicalPresentationHash = (value: string): boolean =>
  value.length > 0 &&
  value.length <= MAX_PRESENTATION_HASH_LENGTH &&
  (value.startsWith("#scene/") || value.startsWith("#discuss/"));

export const normalizeJoinCode = (value: string): string =>
  value.replace(/[\s-]/g, "").toUpperCase();

const PresentationRoleSchema = Schema.Literal("presenter", "audience");
const NonNegativeIntegerSchema = Schema.Number.pipe(
  Schema.int(),
  Schema.between(0, Number.MAX_SAFE_INTEGER),
);
const CanonicalHashSchema = Schema.String.pipe(
  Schema.filter(isCanonicalPresentationHash),
);
const BoundedMessageIdSchema = Schema.String.pipe(
  Schema.maxLength(MAX_MESSAGE_ID_LENGTH),
);
const SnapshotSchema = Schema.Struct({
  hash: CanonicalHashSchema,
  revision: NonNegativeIntegerSchema,
});
const PresenceSchema = Schema.Struct({
  presenters: NonNegativeIntegerSchema,
  audience: NonNegativeIntegerSchema,
});

const ClientSyncMessageSchema = Schema.Union(
  Schema.Struct({
    type: Schema.Literal("location.publish"),
    hash: CanonicalHashSchema,
    baseRevision: NonNegativeIntegerSchema,
    messageId: BoundedMessageIdSchema,
  }),
  Schema.Struct({ type: Schema.Literal("session.end") }),
  Schema.Struct({
    type: Schema.Literal("ping"),
    nonce: BoundedMessageIdSchema,
  }),
);

const ServerSyncMessageSchema = Schema.Union(
  Schema.Struct({
    type: Schema.Literal("location.snapshot"),
    snapshot: SnapshotSchema,
    originatingMessageId: Schema.NullOr(BoundedMessageIdSchema),
  }),
  Schema.Struct({
    type: Schema.Literal("presence.snapshot"),
    presence: PresenceSchema,
  }),
  Schema.Struct({
    type: Schema.Literal("location.rejected"),
    reason: Schema.Literal("stale_revision"),
    current: SnapshotSchema,
    messageId: BoundedMessageIdSchema,
  }),
  Schema.Struct({
    type: Schema.Literal("session.ended"),
    reason: Schema.Literal("presenter_ended", "expired"),
  }),
  Schema.Struct({
    type: Schema.Literal("protocol.error"),
    code: Schema.Literal("invalid_message", "message_too_large", "forbidden"),
    message: Schema.String,
  }),
);

const CreateSessionRequestSchema = Schema.Struct({
  role: PresentationRoleSchema,
  initialHash: CanonicalHashSchema,
});

const JoinSessionRequestSchema = Schema.Struct({
  role: PresentationRoleSchema,
  code: Schema.String.pipe(
    Schema.filter((value) => value.length === JOIN_CODE_LENGTH),
  ),
});

const SessionCredentialSchema = Schema.String.pipe(
  Schema.minLength(1),
  Schema.maxLength(MAX_MESSAGE_ID_LENGTH),
);
const SessionCodeSchema = Schema.String.pipe(
  Schema.filter((value) => value.length === JOIN_CODE_LENGTH),
);
const SessionGrantSchema = Schema.Struct({
  sessionId: SessionCredentialSchema,
  code: SessionCodeSchema,
  connectionToken: SessionCredentialSchema,
  websocketPath: Schema.Literal("/api/presentation-sync/ws"),
  snapshot: SnapshotSchema,
});

const parseJson = (input: string): DecodeResult<unknown> => {
  // Measure UTF-8 bytes before parsing so websocket limits match transport size.
  if (new TextEncoder().encode(input).byteLength > MAX_SYNC_MESSAGE_BYTES) {
    return { ok: false, error: "message_too_large" };
  }

  try {
    return { ok: true, value: JSON.parse(input) as unknown };
  } catch {
    return { ok: false, error: "invalid_json" };
  }
};

const decodeSchema = <T>(
  input: string,
  schema: Schema.Schema<T>,
): DecodeResult<T> => {
  const parsed = parseJson(input);
  if (!parsed.ok) return parsed;

  try {
    return {
      ok: true,
      value: Schema.decodeUnknownSync(schema, { onExcessProperty: "error" })(
        parsed.value,
      ),
    };
  } catch {
    return { ok: false, error: "invalid_message" };
  }
};

export const decodeClientSyncMessage = (
  input: string,
): DecodeResult<ClientSyncMessage> =>
  decodeSchema(input, ClientSyncMessageSchema);

export const decodeServerSyncMessage = (
  input: string,
): DecodeResult<ServerSyncMessage> =>
  decodeSchema(input, ServerSyncMessageSchema);

export const decodeCreateSessionRequest = (
  input: string,
): DecodeResult<CreateSessionRequest> =>
  decodeSchema(input, CreateSessionRequestSchema);

export const decodeJoinSessionRequest = (
  input: string,
): DecodeResult<JoinSessionRequest> => {
  const parsed = parseJson(input);
  if (!parsed.ok) return parsed;

  const normalized =
    // Normalize before schema decoding so the exact length applies to user input
    // after harmless separators have been removed.
    typeof parsed.value === "object" &&
    parsed.value !== null &&
    !Array.isArray(parsed.value) &&
    "code" in parsed.value &&
    typeof parsed.value.code === "string"
      ? { ...parsed.value, code: normalizeJoinCode(parsed.value.code) }
      : parsed.value;

  try {
    return {
      ok: true,
      value: Schema.decodeUnknownSync(JoinSessionRequestSchema, {
        onExcessProperty: "error",
      })(normalized),
    };
  } catch {
    return { ok: false, error: "invalid_message" };
  }
};

export const decodeSessionGrant = (
  input: string,
): DecodeResult<SessionGrant> => decodeSchema(input, SessionGrantSchema);
