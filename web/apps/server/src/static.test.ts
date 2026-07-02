import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";
import { Hono } from "hono";
import { addStaticRoutes, validateConsoleRoot } from "./static.js";

let tmpDir: string;

beforeEach(() => {
  tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "static-test-"));
});

afterEach(() => {
  fs.rmSync(tmpDir, { recursive: true, force: true });
});

const createTestApp = (consoleRoot: string) => {
  const app = new Hono();
  addStaticRoutes(app, { consoleRoot });
  return app;
};

describe("validateConsoleRoot", () => {
  it("throws when directory does not exist", () => {
    expect(() => validateConsoleRoot("/nonexistent")).toThrow(
      "Console root not found",
    );
  });

  it("throws when index.html is missing", () => {
    expect(() => validateConsoleRoot(tmpDir)).toThrow(
      "Console root missing index.html",
    );
  });

  it("does not throw for valid root", () => {
    fs.writeFileSync(path.join(tmpDir, "index.html"), "<!DOCTYPE html>");
    expect(() => validateConsoleRoot(tmpDir)).not.toThrow();
  });
});

describe("addStaticRoutes", () => {
  it("serves index.html from root", async () => {
    fs.writeFileSync(
      path.join(tmpDir, "index.html"),
      "<!DOCTYPE html><html><body>test</body></html>",
    );
    const app = createTestApp(tmpDir);
    const res = await app.request("/");
    expect(res.status).toBe(200);
    const text = await res.text();
    expect(text).toContain("test");
  });

  it("serves static assets", async () => {
    fs.mkdirSync(path.join(tmpDir, "assets"), { recursive: true });
    fs.writeFileSync(
      path.join(tmpDir, "assets", "app.js"),
      "console.log('hello')",
    );
    const app = createTestApp(tmpDir);
    const res = await app.request("/assets/app.js");
    expect(res.status).toBe(200);
    const text = await res.text();
    expect(text).toContain("console.log");
  });

  it("SPA fallback serves index.html for unknown routes", async () => {
    fs.writeFileSync(
      path.join(tmpDir, "index.html"),
      "<!DOCTYPE html><html><body>spa</body></html>",
    );
    const app = createTestApp(tmpDir);
    const res = await app.request("/some/client/route");
    expect(res.status).toBe(200);
    const text = await res.text();
    expect(text).toContain("spa");
  });

  it("returns JSON 404 for unknown API routes", async () => {
    fs.writeFileSync(
      path.join(tmpDir, "index.html"),
      "<!DOCTYPE html><html><body>spa</body></html>",
    );
    const app = createTestApp(tmpDir);
    const res = await app.request("/api/unknown", { method: "GET" });
    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error).toBe("not found");
  });

  it("returns JSON 404 for POST to non-API routes", async () => {
    fs.writeFileSync(
      path.join(tmpDir, "index.html"),
      "<!DOCTYPE html><html><body>spa</body></html>",
    );
    const app = createTestApp(tmpDir);
    const res = await app.request("/nonexistent", { method: "POST" });
    expect(res.status).toBe(404);
  });
});
