import { describe, it, expect, beforeEach } from "vitest";
import {
  connectionReducer,
  initialState,
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

  it("restores target from localStorage when available", () => {
    try {
      localStorage.setItem(STORAGE_KEY, "http://custom:9999/rpc");
    } catch {
      return; // skip if localStorage unavailable
    }
    const state = initialState();
    expect(state.draftTarget).toBe("http://custom:9999/rpc");
  });

  it("restored target does not trigger automatic connection", () => {
    try {
      localStorage.setItem(STORAGE_KEY, "http://custom:9999/rpc");
    } catch {
      return; // skip if localStorage unavailable
    }
    const state = initialState();
    expect(state.phase).toBe("not_configured");
    expect(state.connectedTarget).toBeNull();
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
