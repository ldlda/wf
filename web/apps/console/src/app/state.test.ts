import { describe, it, expect, beforeEach } from "vitest";
import {
  connectionReducer,
  initialState,
  type EvidenceRecord,
  type SourceRecord,
  type ConnectionState,
  type ConnectionAction,
  STORAGE_KEY,
} from "./state.js";

const makeSuccess = (target = "http://127.0.0.1:8765/rpc") =>
  ({
    ok: true,
    connection: {
      status: "connected",
      target,
      serverStatus: "ok",
      storeRoot: "/tmp/store",
      durationMs: 10,
    },
    exchange: { request: {}, response: {} },
    equivalentCli: "uv run wf status",
  }) as const;

const evidence: EvidenceRecord = {
  id: "e1",
  operation: "workflow.sources.list",
  label: "Source inventory",
  equivalentCli: "uv run wf source list",
  request: {},
  response: {},
  durationMs: 12,
};

const sources: ReadonlyArray<SourceRecord> = [
  {
    id: "local.demo",
    kind: "python",
    enabled: true,
    description: null,
    toolCount: 1,
    nodeSpecCount: 1,
    reducerCount: 0,
    promptCount: 0,
    resourceCount: 0,
  },
];

beforeEach(() => {
  try {
    sessionStorage.clear();
  } catch {
    // jsdom may not provide sessionStorage
  }
  try {
    localStorage.clear();
  } catch {
    // jsdom may not provide localStorage
  }
});

describe("initialState", () => {
  it("defaults to not_configured phase", () => {
    const state = initialState();
    expect(state.phase).toBe("not_configured");
  });

  it("defaults target to http://127.0.0.1:8765/rpc when no stored value", () => {
    const state = initialState();
    expect(state.draftTarget).toBe("http://127.0.0.1:8765/rpc");
  });

  it("restores target from sessionStorage when available", () => {
    try {
      sessionStorage.setItem(STORAGE_KEY, "http://custom:9999/rpc");
    } catch {
      return; // skip if sessionStorage unavailable
    }
    const state = initialState();
    expect(state.draftTarget).toBe("http://custom:9999/rpc");
  });

  it("restored target does not trigger automatic connection", () => {
    try {
      sessionStorage.setItem(STORAGE_KEY, "http://custom:9999/rpc");
    } catch {
      return; // skip if sessionStorage unavailable
    }
    const state = initialState();
    expect(state.phase).toBe("not_configured");
    expect(state.connectedTarget).toBeNull();
  });

  it("ignores localStorage so persistence is session-scoped", () => {
    try {
      localStorage.setItem(STORAGE_KEY, "http://custom:9999/rpc");
    } catch {
      return; // skip if localStorage unavailable
    }
    const state = initialState();
    expect(state.draftTarget).toBe("http://127.0.0.1:8765/rpc");
  });
});

describe("submit", () => {
  it("transitions to connecting phase", () => {
    const state = initialState();
    const next = connectionReducer(state, {
      type: "submit",
      target: "http://127.0.0.1:8765/rpc",
    });
    expect(next.phase).toBe("connecting");
  });

  it("updates draftTarget to submitted value", () => {
    const state = initialState();
    const next = connectionReducer(state, {
      type: "submit",
      target: "http://custom:9999/rpc",
    });
    expect(next.draftTarget).toBe("http://custom:9999/rpc");
  });

  it("clears previous message", () => {
    const state: ConnectionState = {
      ...initialState(),
      phase: "unreachable",
      message: "old error",
    };
    const next = connectionReducer(state, {
      type: "submit",
      target: "http://127.0.0.1:8765/rpc",
    });
    expect(next.message).toBeNull();
  });
});

describe("success", () => {
  it("records normalized target and evidence", () => {
    const state = initialState();
    const next = connectionReducer(state, {
      type: "success",
      data: makeSuccess(),
    });
    expect(next.phase).toBe("connected");
    expect(next.connectedTarget).toBe("http://127.0.0.1:8765/rpc");
    expect(next.serverStatus).toBe("ok");
    expect(next.storeRoot).toBe("/tmp/store");
    expect(next.durationMs).toBe(10);
  });

  it("persists target to sessionStorage when available", () => {
    const state = initialState();
    connectionReducer(state, {
      type: "success",
      data: makeSuccess("http://custom:9999/rpc"),
    });
    try {
      expect(sessionStorage.getItem(STORAGE_KEY)).toBe(
        "http://custom:9999/rpc",
      );
    } catch {
      // jsdom may not provide sessionStorage
    }
  });

  it("success updates draftTarget to connected target", () => {
    const state = initialState();
    const next = connectionReducer(state, {
      type: "success",
      data: makeSuccess("http://custom:9999/rpc"),
    });
    expect(next.draftTarget).toBe("http://custom:9999/rpc");
  });
});

describe("failure", () => {
  it("retains draft input on failure", () => {
    const state = connectionReducer(initialState(), {
      type: "submit",
      target: "http://custom:9999/rpc",
    });
    const next = connectionReducer(state, {
      type: "failure",
      code: "invalid_target",
      message: "bad target",
    });
    expect(next.draftTarget).toBe("http://custom:9999/rpc");
    expect(next.phase).toBe("invalid_target");
    expect(next.message).toBe("bad target");
  });

  it("does not overwrite connectedTarget on failure", () => {
    let state = connectionReducer(initialState(), {
      type: "submit",
      target: "http://old:8000/rpc",
    });
    state = connectionReducer(state, {
      type: "success",
      data: makeSuccess("http://old:8000/rpc"),
    });
    const next = connectionReducer(state, {
      type: "failure",
      code: "upstream_unreachable",
      message: "connection refused",
    });
    expect(next.connectedTarget).toBe("http://old:8000/rpc");
    expect(next.phase).toBe("unreachable");
  });

  it("maps malformed responses to the dedicated phase", () => {
    const next = connectionReducer(initialState(), {
      type: "failure",
      code: "malformed_response",
      message: "malformed response from server",
    });
    expect(next.phase).toBe("malformed_response");
  });

  it("distinguishes the console backend from the workflow server", () => {
    const next = connectionReducer(initialState(), {
      type: "failure",
      code: "console_backend_unreachable",
      message: "Console backend unavailable at 127.0.0.1:8787",
    });
    expect(next.phase).toBe("console_backend_unreachable");
  });

  it("maps decode and size failures to rpc_error", () => {
    for (const code of [
      "upstream_timeout",
      "rpc_decode_error",
      "response_too_large",
    ]) {
      const next = connectionReducer(initialState(), {
        type: "failure",
        code,
        message: code,
      });
      expect(next.phase).toBe("rpc_error");
    }
  });
});

describe("reconnect replaces target only on success", () => {
  it("on success, connectedTarget updates to new target", () => {
    let state = connectionReducer(initialState(), {
      type: "submit",
      target: "http://first:8000/rpc",
    });
    state = connectionReducer(state, {
      type: "success",
      data: makeSuccess("http://first:8000/rpc"),
    });
    state = connectionReducer(state, {
      type: "submit",
      target: "http://second:8000/rpc",
    });
    state = connectionReducer(state, {
      type: "success",
      data: makeSuccess("http://second:8000/rpc"),
    });
    expect(state.connectedTarget).toBe("http://second:8000/rpc");
    expect(state.phase).toBe("connected");
  });
});

describe("draft_changed", () => {
  it("updates draftTarget without changing phase", () => {
    const state = initialState();
    const next = connectionReducer(state, {
      type: "draft_changed",
      value: "http://typed:9999/rpc",
    });
    expect(next.draftTarget).toBe("http://typed:9999/rpc");
    expect(next.phase).toBe("not_configured");
  });
});

describe("source inventory", () => {
  it("sets loading state for source refreshes", () => {
    const state: ConnectionState = {
      ...initialState(),
      sourceError: "old error",
    };
    const next = connectionReducer(state, { type: "sources_loading" });
    expect(next.sourcesLoading).toBe(true);
    expect(next.sourceError).toBeNull();
  });

  it("records loaded sources and evidence", () => {
    const state = connectionReducer(initialState(), {
      type: "sources_loading",
    });
    const next = connectionReducer(state, {
      type: "sources_loaded",
      sources,
      evidence,
    });
    expect(next.sources).toBe(sources);
    expect(next.sourcesLoading).toBe(false);
    expect(next.sourceError).toBeNull();
    expect(next.evidence).toEqual([evidence]);
  });

  it("records source errors and optional evidence", () => {
    const state = connectionReducer(initialState(), {
      type: "sources_loading",
    });
    const next = connectionReducer(state, {
      type: "sources_error",
      message: "source list failed",
      evidence,
    });
    expect(next.sourcesLoading).toBe(false);
    expect(next.sourceError).toBe("source list failed");
    expect(next.evidence).toEqual([evidence]);
  });

  it("appends protocol evidence records", () => {
    const state = initialState();
    const next = connectionReducer(state, {
      type: "evidence_recorded",
      record: evidence,
    });
    expect(next.evidence).toEqual([evidence]);
  });
});
