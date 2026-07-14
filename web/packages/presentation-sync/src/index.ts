export {
  JOIN_CODE_LENGTH,
  MAX_PRESENTATION_HASH_LENGTH,
  MAX_SYNC_MESSAGE_BYTES,
  decodeClientSyncMessage,
  decodeCreateSessionRequest,
  decodeJoinSessionRequest,
  decodeServerSyncMessage,
  isCanonicalPresentationHash,
  normalizeJoinCode,
} from "./protocol.js";

export type {
  ClientSyncMessage,
  CreateSessionRequest,
  DecodeResult,
  JoinSessionRequest,
  PresentationPresence,
  PresentationRole,
  PresentationSnapshot,
  ServerSyncMessage,
  SessionGrant,
} from "./protocol.js";
