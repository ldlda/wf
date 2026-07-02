import { Hono } from "hono";
import { serveStatic } from "@hono/node-server/serve-static";
import * as fs from "node:fs";
import * as path from "node:path";

export type StaticOptions = {
  readonly consoleRoot: string;
};

export function validateConsoleRoot(consoleRoot: string): void {
  if (!fs.existsSync(consoleRoot)) {
    throw new Error(`Console root not found: ${consoleRoot}`);
  }
  const indexPath = path.join(consoleRoot, "index.html");
  if (!fs.existsSync(indexPath)) {
    throw new Error(`Console root missing index.html: ${consoleRoot}`);
  }
}

export function addStaticRoutes(
  app: Hono,
  options: StaticOptions,
): void {
  const { consoleRoot } = options;

  app.all("/api/*", (c) => c.json({ error: "not found" }, 404));
  app.use("/assets/*", serveStatic({ root: consoleRoot }));
  app.get("*", serveStatic({ root: consoleRoot, path: "index.html" }));
  app.all("*", (c) => c.json({ error: "not found" }, 404));
}
