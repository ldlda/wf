import { describe, expect, it } from "vitest";
import type { EvidenceRecord } from "../../app/state.js";
import {
  retainEvidence,
  sanitizeEvidenceRecord,
  sanitizeEvidenceValue,
} from "./evidence-policy.js";

const jsonByteLength = (value: unknown): number =>
  new TextEncoder().encode(JSON.stringify(value)).length;

const makeRecord = (id: string, request: unknown = {}, response: unknown = {}): EvidenceRecord => ({
  id,
  target: "http://console.test/rpc",
  operation: "workflow.capabilities.list",
  label: "List capabilities",
  equivalentCli: "uv run wf cap list",
  request,
  response,
  durationMs: 4,
});

describe("evidence policy", () => {
  it("redacts sensitive keys case-insensitively before traversing their values", () => {
    const secret: Record<string, unknown> = {};
    secret.self = secret;
    const value = {
      Authorization: secret,
      aUtHoRiZaTiOn: "Bearer another-secret",
      value: "ok",
    };

    expect(sanitizeEvidenceValue(value)).toEqual({
      Authorization: "[redacted]",
      aUtHoRiZaTiOn: "[redacted]",
      value: "ok",
    });
    expect(value.Authorization).toBe(secret);
  });

  it("redacts only the approved sensitive keys with case-insensitive matching", () => {
    const sanitized = sanitizeEvidenceValue({
      AUTHORIZATION: "authorization-secret",
      Cookie: "cookie-secret",
      "SET-COOKIE": "set-cookie-secret",
      ToKeN: "token-secret",
      Access_Token: "access-token-secret",
      REFRESH_TOKEN: "refresh-token-secret",
      Secret: "secret-value",
      PASSWORD: "password-secret",
      Api_Key: "api-key-secret",
      "API-KEY": "api-key-secret",
      tokenCount: 3,
      authorizationStatus: "ok",
      cookieJar: "safe",
      secretary: "safe",
    }) as Record<string, unknown>;

    for (const key of [
      "AUTHORIZATION",
      "Cookie",
      "SET-COOKIE",
      "ToKeN",
      "Access_Token",
      "REFRESH_TOKEN",
      "Secret",
      "PASSWORD",
      "Api_Key",
      "API-KEY",
    ]) {
      expect(sanitized[key]).toBe("[redacted]");
    }
    expect(sanitized.tokenCount).toBe(3);
    expect(sanitized.authorizationStatus).toBe("ok");
    expect(sanitized.cookieJar).toBe("safe");
    expect(sanitized.secretary).toBe("safe");
  });

  it("truncates recursive depth with a stable marker", () => {
    let value: unknown = { leaf: true };
    for (let index = 0; index < 20; index += 1) {
      value = { nested: value };
    }

    const sanitized = sanitizeEvidenceValue(value);
    const serialized = JSON.stringify(sanitized);
    expect(serialized).toContain("[truncated: depth limit]");
    expect(serialized).not.toContain("[object Object]");
  });

  it("truncates oversized strings with a stable marker", () => {
    const sanitized = sanitizeEvidenceValue("x".repeat(20_000));

    expect(sanitized).toMatch(/x+\[truncated: evidence limit\]$/);
    expect(String(sanitized).length).toBeLessThan(20_000);
  });

  it("truncates array and object entries deterministically", () => {
    const array = sanitizeEvidenceValue(Array.from({ length: 150 }, (_, index) => index));
    const object = sanitizeEvidenceValue(
      Object.fromEntries(Array.from({ length: 150 }, (_, index) => [`entry-${index}`, index])),
    );

    expect(Array.isArray(array)).toBe(true);
    expect((array as unknown[]).at(-1)).toBe("[truncated: evidence limit]");
    expect((object as Record<string, unknown>)["[truncated: evidence limit]"]).toBe(
      "[truncated: evidence limit]",
    );
  });

  it("keeps each sanitized value within the 32 KiB UTF-8 budget", () => {
    const record = sanitizeEvidenceRecord(
      makeRecord(
        "large",
        { payload: "request-😀".repeat(20_000) },
        { payload: "response-漢".repeat(20_000) },
      ),
    );

    expect(jsonByteLength(record.request)).toBeLessThanOrEqual(32 * 1024);
    expect(jsonByteLength(record.response)).toBeLessThanOrEqual(32 * 1024);
  });

  it("replaces retained CLI metadata when the raw request has an exact sensitive key", () => {
    const record = makeRecord(
      "secret-cli",
      {
        jsonrpc: "2.0",
        method: "workflow.capabilities.call",
        params: {
          qualified_name: "local.example.login",
          payload: { password: "correct horse battery staple" },
        },
        id: 7,
      },
    );
    const originalCli =
      "uv run wf cap call local.example.login --input '{\"password\":\"correct horse battery staple\"}'";
    const recordWithCli = { ...record, equivalentCli: originalCli };

    const sanitized = sanitizeEvidenceRecord(recordWithCli);

    expect(sanitized.equivalentCli).toBe("[redacted: sensitive request]");
    expect(sanitized.equivalentCli).not.toContain("correct horse");
    expect(recordWithCli.equivalentCli).toBe(originalCli);
  });

  it("does not redact CLI metadata for near-match request keys", () => {
    const record = makeRecord("safe-cli", {
      params: {
        payload: {
          password_hint: "first pet",
          tokenCount: 3,
        },
      },
    });

    expect(sanitizeEvidenceRecord(record).equivalentCli).toBe(
      "uv run wf cap list",
    );
  });

  it("deterministically bounds a near-256 KiB retained CLI string", () => {
    const record = {
      ...makeRecord("large-cli", { params: { payload: { value: "safe" } } }),
      equivalentCli: `uv run wf cap call local.example.echo --input '${"x".repeat(255 * 1024)}'`,
    };

    const first = sanitizeEvidenceRecord(record).equivalentCli;
    const second = sanitizeEvidenceRecord(record).equivalentCli;

    expect(new TextEncoder().encode(first).length).toBeLessThanOrEqual(4096);
    expect(first).toBe(second);
    expect(first).toMatch(/\[truncated: evidence limit\]$/);
    expect(record.equivalentCli.length).toBeGreaterThan(250 * 1024);
  });

  it("preserves ordinary scalar data", () => {
    expect(sanitizeEvidenceValue({ ok: true, count: 3, empty: null, text: "hello" })).toEqual({
      ok: true,
      count: 3,
      empty: null,
      text: "hello",
    });
  });

  it("handles cyclic and non-JSON values without throwing", () => {
    const value: Record<string, unknown> = {
      bigint: 123n,
      missing: undefined,
      callable: () => "not JSON",
    };
    value.cycle = value;

    expect(() => sanitizeEvidenceValue(value)).not.toThrow();
    expect(() => JSON.stringify(sanitizeEvidenceValue(value))).not.toThrow();
  });

  it("retains only the newest 100 sanitized records", () => {
    const records = Array.from({ length: 100 }, (_, index) => makeRecord(`record-${index}`));
    const retained = retainEvidence(records, makeRecord("record-100", { token: "secret" }));

    expect(retained).toHaveLength(100);
    expect(retained[0]?.id).toBe("record-1");
    expect(retained.at(-1)).toMatchObject({
      id: "record-100",
      request: { token: "[redacted]" },
    });
    expect(retained).not.toBe(records);
  });
});
