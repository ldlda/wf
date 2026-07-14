import { describe, expect, it } from "vitest";
import {
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

describe("presentation sync protocol", () => {
  it("accepts bounded canonical location publishes", () => {
    expect(
      decodeClientSyncMessage(
        JSON.stringify({
          type: "location.publish",
          hash: "#scene/architecture/client/focus/client-operations",
          baseRevision: 4,
          messageId: "msg-4",
        }),
      ),
    ).toEqual({
      ok: true,
      value: {
        type: "location.publish",
        hash: "#scene/architecture/client/focus/client-operations",
        baseRevision: 4,
        messageId: "msg-4",
      },
    });
  });

  it.each(["", "#unknown/x", "scene/thesis/title"])(
    "rejects non-canonical hash %s",
    (hash) => expect(isCanonicalPresentationHash(hash)).toBe(false),
  );

  it("enforces the canonical hash length bound", () => {
    expect(
      isCanonicalPresentationHash(
        `#scene/${"x".repeat(MAX_PRESENTATION_HASH_LENGTH)}`,
      ),
    ).toBe(false);
  });

  it("rejects oversized websocket payloads before JSON decoding", () => {
    const result = decodeClientSyncMessage(
      "x".repeat(MAX_SYNC_MESSAGE_BYTES + 1),
    );
    expect(result).toEqual({ ok: false, error: "message_too_large" });
  });

  it("normalizes human-entered join codes", () => {
    expect(normalizeJoinCode(" ab-cd 7 ")).toBe("ABCD7");
  });

  it.each([
    { type: "location.unknown" },
    {
      type: "location.publish",
      hash: "#scene/thesis/title",
      baseRevision: -1,
      messageId: "msg-1",
    },
    {
      type: "location.publish",
      hash: "#scene/thesis/title",
      baseRevision: 1.5,
      messageId: "msg-1",
    },
    {
      type: "location.publish",
      hash: "#scene/thesis/title",
      baseRevision: 0,
      messageId: "x".repeat(129),
    },
    {
      type: "location.publish",
      hash: `#scene/${"x".repeat(MAX_PRESENTATION_HASH_LENGTH)}`,
      baseRevision: 0,
      messageId: "msg-1",
    },
  ])("rejects invalid client message %#", (message) => {
    expect(decodeClientSyncMessage(JSON.stringify(message))).toEqual({
      ok: false,
      error: "invalid_message",
    });
  });

  it("accepts session end and ping messages", () => {
    expect(decodeClientSyncMessage('{"type":"session.end"}')).toEqual({
      ok: true,
      value: { type: "session.end" },
    });
    expect(
      decodeClientSyncMessage(JSON.stringify({ type: "ping", nonce: "n-1" })),
    ).toEqual({
      ok: true,
      value: { type: "ping", nonce: "n-1" },
    });
  });

  it.each([
    {
      role: "presenter",
      initialHash: "#scene/thesis/title",
    },
    {
      role: "audience",
      initialHash: "#discuss/problem/direct-actions",
    },
  ])("accepts a valid create request %#", (request) => {
    expect(decodeCreateSessionRequest(JSON.stringify(request))).toEqual({
      ok: true,
      value: request,
    });
  });

  it("rejects invalid create request roles and hashes", () => {
    expect(
      decodeCreateSessionRequest(
        JSON.stringify({ role: "moderator", initialHash: "#scene/thesis/title" }),
      ),
    ).toEqual({ ok: false, error: "invalid_message" });
    expect(
      decodeCreateSessionRequest(
        JSON.stringify({ role: "presenter", initialHash: "#unknown/title" }),
      ),
    ).toEqual({ ok: false, error: "invalid_message" });
  });

  it("normalizes and validates join request codes", () => {
    expect(
      decodeJoinSessionRequest(
        JSON.stringify({ role: "audience", code: " ab-cd 7x " }),
      ),
    ).toEqual({
      ok: true,
      value: { role: "audience", code: "ABCD7X" },
    });
    expect(
      decodeJoinSessionRequest(
        JSON.stringify({ role: "audience", code: "AB12" }),
      ),
    ).toEqual({ ok: false, error: "invalid_message" });
    expect(
      decodeJoinSessionRequest(
        JSON.stringify({ role: "moderator", code: "ABCD7X" }),
      ),
    ).toEqual({ ok: false, error: "invalid_message" });
    expect(JOIN_CODE_LENGTH).toBe(6);
  });

  it("decodes every server message variant", () => {
    const messages = [
      {
        type: "location.snapshot",
        snapshot: { hash: "#scene/thesis/title", revision: 3 },
        originatingMessageId: "msg-3",
      },
      {
        type: "location.snapshot",
        snapshot: { hash: "#discuss/problem/direct-actions", revision: 0 },
        originatingMessageId: null,
      },
      {
        type: "presence.snapshot",
        presence: { presenters: 1, audience: 2 },
      },
      {
        type: "location.rejected",
        reason: "stale_revision",
        current: { hash: "#scene/thesis/title", revision: 4 },
        messageId: "msg-stale",
      },
      { type: "session.ended", reason: "presenter_ended" },
      { type: "session.ended", reason: "expired" },
      {
        type: "protocol.error",
        code: "invalid_message",
        message: "invalid payload",
      },
      {
        type: "protocol.error",
        code: "message_too_large",
        message: "payload exceeded limit",
      },
      {
        type: "protocol.error",
        code: "forbidden",
        message: "presenter role required",
      },
    ];

    for (const message of messages) {
      expect(decodeServerSyncMessage(JSON.stringify(message))).toEqual({
        ok: true,
        value: message,
      });
    }
  });

  it("rejects invalid server revisions and presence counts", () => {
    expect(
      decodeServerSyncMessage(
        JSON.stringify({
          type: "location.snapshot",
          snapshot: { hash: "#scene/thesis/title", revision: 1.25 },
          originatingMessageId: null,
        }),
      ),
    ).toEqual({ ok: false, error: "invalid_message" });
    expect(
      decodeServerSyncMessage(
        JSON.stringify({
          type: "presence.snapshot",
          presence: { presenters: -1, audience: 0 },
        }),
      ),
    ).toEqual({ ok: false, error: "invalid_message" });
  });

  it("returns stable errors for malformed JSON", () => {
    expect(decodeClientSyncMessage("not json")).toEqual({
      ok: false,
      error: "invalid_json",
    });
    expect(decodeServerSyncMessage("{")).toEqual({
      ok: false,
      error: "invalid_json",
    });
    expect(decodeCreateSessionRequest("[]")).toEqual({
      ok: false,
      error: "invalid_message",
    });
  });
});
