import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { once } from "node:events";
import { promises as fs } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const repoRoot = fileURLToPath(new URL("../../../../", import.meta.url));
const serverEntry = fileURLToPath(new URL("../../server/dist/index.js", import.meta.url));
const exampleSourceRoot = join(repoRoot, "examples", "lda_report_workflow");
const sessionStorageKey = "lda.workflowConsole.target";

type JsonRpcResponse = {
  readonly error?: unknown;
  readonly result?: unknown;
  readonly [key: string]: unknown;
};

type ManagedChild = {
  readonly name: string;
  readonly child: ChildProcessWithoutNullStreams;
  readonly output: () => string;
  readonly spawnError: () => Error | null;
};

let tempRoot: string | undefined;
let rpcTarget: string;
let baseUrl: string;
const managedChildren: ManagedChild[] = [];
const stopRequests = new Set<string>();

const reservePort = async (): Promise<number> => {
  const listener = createServer();
  listener.listen(0, "127.0.0.1");
  await once(listener, "listening");
  const address = listener.address();
  if (address === null || typeof address === "string") {
    listener.close();
    throw new Error("Could not reserve an E2E server port");
  }
  const { port } = address;
  listener.close();
  await once(listener, "close");
  return port;
};

const startChild = (
  name: string,
  command: string,
  args: readonly string[],
  env: NodeJS.ProcessEnv = process.env,
): ManagedChild => {
  const child = spawn(command, args, {
    cwd: repoRoot,
    env,
    stdio: ["pipe", "pipe", "pipe"],
    // On POSIX this makes the recorded root the leader of an owned process
    // group, so uv's Python descendants can be terminated without name/port
    // based cleanup. Windows keeps its scoped taskkill tree path below.
    detached: process.platform !== "win32",
  });
  let output = "";
  let spawnError: Error | null = null;
  child.stdout.on("data", (chunk: Buffer) => {
    output += chunk.toString();
  });
  child.stderr.on("data", (chunk: Buffer) => {
    output += chunk.toString();
  });
  child.on("error", (error) => {
    spawnError = error;
    output += `${error.name}: ${error.message}\n`;
  });
  const managed = { name, child, output: () => output, spawnError: () => spawnError };
  managedChildren.push(managed);
  return managed;
};

const describeExit = (managed: ManagedChild): string =>
  `${managed.name} exited with ${managed.child.exitCode}:\n${managed.output()}`;

const waitForChildExit = async (
  child: ChildProcessWithoutNullStreams,
  timeoutMs = 7_000,
): Promise<void> => {
  if (child.exitCode !== null) return;
  await Promise.race([
    once(child, "exit").then(() => undefined),
    new Promise<void>((resolve) => setTimeout(resolve, timeoutMs)),
  ]);
};

const killWindowsTree = async (pid: number): Promise<void> => {
  await new Promise<void>((resolve) => {
    const killer = spawn("taskkill", ["/F", "/T", "/PID", String(pid)], {
      stdio: "ignore",
    });
    killer.once("close", () => resolve());
    killer.once("error", () => resolve());
  });
};

const killPosixProcessGroup = (pid: number, signal: NodeJS.Signals): void => {
  try {
    process.kill(-pid, signal);
  } catch (error: unknown) {
    if (error instanceof Error && (error as NodeJS.ErrnoException).code === "ESRCH") return;
    throw error;
  }
};

const stopChild = async (managed: ManagedChild): Promise<void> => {
  const { child } = managed;
  stopRequests.add(managed.name);

  if (process.platform === "win32" && child.pid !== undefined) {
    if (child.exitCode !== null) return;
    // uv owns a Python grandchild on Windows, so terminate only this recorded
    // process tree rather than sending a broad port- or name-based kill.
    await killWindowsTree(child.pid);
    await waitForChildExit(child);
    if (child.exitCode === null) {
      await killWindowsTree(child.pid);
      await waitForChildExit(child, 2_000);
    }
    return;
  }

  if (child.pid === undefined) return;
  // The negative PID targets only the process group created by startChild.
  if (child.exitCode === null) killPosixProcessGroup(child.pid, "SIGTERM");
  await waitForChildExit(child);
  if (child.exitCode === null) killPosixProcessGroup(child.pid, "SIGKILL");
  await waitForChildExit(child, 2_000);
};


const postJsonRpc = async (
  target: string,
  request: Record<string, unknown>,
): Promise<JsonRpcResponse> => {
  const response = await fetch(target, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  const body = await response.text();
  if (!response.ok) {
    throw new Error(`JSON-RPC request failed with HTTP ${response.status}: ${body}`);
  }
  try {
    return JSON.parse(body) as JsonRpcResponse;
  } catch {
    throw new Error(`JSON-RPC server returned malformed JSON: ${body}`);
  }
};

const waitForRpcServer = async (managed: ManagedChild): Promise<void> => {
  let lastError = "no response";
  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (managed.spawnError()) throw new Error(describeExit(managed));
    if (managed.child.exitCode !== null) throw new Error(describeExit(managed));
    try {
      const response = await postJsonRpc(rpcTarget, {
        jsonrpc: "2.0",
        id: "readiness",
        method: "workflow.health",
        params: {},
      });
      if (response.error === undefined) return;
      lastError = JSON.stringify(response.error);
    } catch (error: unknown) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Workflow RPC server did not become ready: ${lastError}\n${managed.output()}`);
};

const waitForWebServer = async (managed: ManagedChild): Promise<void> => {
  let lastError = "no response";
  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (managed.child.exitCode !== null) throw new Error(describeExit(managed));
    try {
      const response = await fetch(baseUrl);
      if (response.ok) return;
      lastError = `HTTP ${response.status}`;
    } catch (error: unknown) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Workflow console server did not become ready: ${lastError}\n${managed.output()}`);
};

const connect = async (page: Page): Promise<void> => {
  await page.getByLabel("Workflow JSON-RPC URL").fill(rpcTarget);
  await page.getByRole("button", { name: /^(Connect|Reconnect)$/ }).click();
  await expect(page.getByTestId("phase-label")).toHaveText("Connected");
};

const expandEvidence = async (
  page: Page,
  operation: string,
  expected: {
    readonly request: Record<string, unknown>;
    readonly response: Record<string, unknown>;
  },
): Promise<void> => {
  const record = page.locator("details.evidence-record").filter({ hasText: operation }).first();
  await expect(record).toBeVisible();
  await record.locator("summary").click();
  await expect(record.locator(".evidence-detail")).toBeVisible();
  await expect(record).toContainText("Request");
  await expect(record).toContainText("Response");

  const fields = record.locator(".evidence-field");
  const request = JSON.parse(await fields.nth(1).locator("pre").innerText()) as Record<string, unknown>;
  const response = JSON.parse(await fields.nth(2).locator("pre").innerText()) as Record<string, unknown>;
  expect(request).toMatchObject(expected.request);
  expect(response).toMatchObject(expected.response);
};

test.beforeAll(async () => {
  tempRoot = await fs.mkdtemp(join(tmpdir(), "lda-workflow-console-e2e-"));
  const storeRoot = join(tempRoot, "store");
  const configPath = join(tempRoot, "wf.config.json");
  const rpcPort = await reservePort();
  const webPort = await reservePort();
  rpcTarget = `http://127.0.0.1:${rpcPort}/rpc`;
  baseUrl = `http://127.0.0.1:${webPort}`;

  await fs.writeFile(
    configPath,
    JSON.stringify(
      {
        server: {
          store: { kind: "filesystem", root: storeRoot },
          transports: [{ kind: "rpc_http", host: "127.0.0.1", port: rpcPort, path: "/rpc" }],
          sources: [{
            id: "local.lda_docs",
            kind: "python",
            path: exampleSourceRoot,
            module: "document_source",
            registry: "registry",
          }],
        },
      },
      null,
      2,
    ),
    "utf8",
  );

  const rpcServer = startChild(
    "workflow RPC server",
    "uv",
    ["run", "wf-rpc-server", "--config", configPath, "--host", "127.0.0.1", "--port", String(rpcPort)],
  );
  await waitForRpcServer(rpcServer);

  const seedResponse = await postJsonRpc(rpcTarget, {
    jsonrpc: "2.0",
    id: 1,
    method: "workflow.draft_workspaces.create_from_capability",
    params: {
      workspace_id: "console-e2e",
      capability_name: "local.lda_docs.read_documents",
      name: "console_e2e",
      title: "Console E2E Draft",
    },
  });
  expect(seedResponse.error).toBeUndefined();
  expect(seedResponse.result).toBeDefined();

  const webServer = startChild(
    "workflow console server",
    process.execPath,
    [serverEntry],
    { ...process.env, WEB_HOST: "127.0.0.1", WEB_PORT: String(webPort) },
  );
  await waitForWebServer(webServer);
});

test.afterAll(async () => {
  for (const managed of [...managedChildren].reverse()) {
    await stopChild(managed);
  }
  if (tempRoot !== undefined) {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
  expect([...stopRequests].toSorted()).toEqual(
    managedChildren.map(({ name }) => name).toSorted(),
  );
});

test("verifies desktop discovery, draft inspection, and evidence receipts", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();
  try {
    await page.goto(`${baseUrl}/console/discover`);
    await connect(page);

    const capability = page.getByRole("button", { name: /local\.lda_docs\.read_documents/ });
    await expect(capability).toBeVisible();
    await capability.click();
    await expect(page.getByRole("heading", { name: "Input schema" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Output schema" })).toBeVisible();

    await page.getByRole("link", { name: "Drafts", exact: true }).click();
    await expect(page).toHaveURL(`${baseUrl}/console/drafts`);
    await page.getByRole("link", { name: "Console E2E Draft", exact: true }).click();
    await expect(page).toHaveURL(`${baseUrl}/console/drafts/console-e2e`);
    await expect(page.getByRole("heading", { name: "Console E2E Draft" })).toBeVisible();
    await expect(page.locator(".draft-detail__workspace-id")).toHaveText("console-e2e");
    await expect(page.locator('[data-status="valid"]').first()).toHaveText("Valid");

    const summary = page.getByRole("heading", { name: "Draft summary" }).locator("..");
    await expect(summary.getByText("Revision", { exact: true }).locator("..").getByText("Revision 1", { exact: true })).toBeVisible();
    await expect(summary.getByText("Step count", { exact: true }).locator("..").getByText("1", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Diagnostics" })).toBeVisible();

    await page.getByText("Raw draft document", { exact: true }).click();
    await expect(page.getByRole("region", { name: "Raw draft JSON, horizontally scrollable" })).toContainText(
      "local.lda_docs.read_documents",
    );

    await expandEvidence(page, "workflow.capabilities.list", {
      request: {
        jsonrpc: "2.0",
        method: "workflow.capabilities.list",
        params: { limit: 50 },
      },
      response: {
        jsonrpc: "2.0",
        result: { capabilities: expect.any(Array) },
      },
    });
    await expandEvidence(page, "workflow.draft_workspaces.get", {
      request: {
        jsonrpc: "2.0",
        method: "workflow.draft_workspaces.get",
        params: { workspace_id: "console-e2e", include_draft: true },
      },
      response: {
        jsonrpc: "2.0",
        result: {
          workspace_id: "console-e2e",
          revision: 1,
          draft: expect.any(Object),
        },
      },
    });
  } finally {
    await context.close();
  }
});

test("keeps mobile draft inspection read-only and horizontally navigable", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await context.addInitScript(
    ({ key, target }: { readonly key: string; readonly target: string }) => {
      sessionStorage.setItem(key, target);
    },
    { key: sessionStorageKey, target: rpcTarget },
  );
  const page = await context.newPage();
  try {
    await page.goto(`${baseUrl}/console/drafts/console-e2e`);
    await connect(page);
    await expect(page.getByRole("heading", { name: "Console E2E Draft" })).toBeVisible();

    const nav = page.locator('nav[aria-label="Workflow lifecycle"]');
    await expect(nav).toHaveCSS("overflow-x", "auto");
    await expect.poll(() => nav.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true);
    await page.getByRole("button", { name: "Open context inspector" }).click();
    await expect(page.getByRole("heading", { name: "Draft summary" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Diagnostics" })).toBeVisible();

    await page.getByText("Raw draft document", { exact: true }).click();
    await expect(page.getByRole("region", { name: "Raw draft JSON, horizontally scrollable" })).toBeVisible();

    const deferredMutationButtons = page.locator(".authoring-inspector__deferred-actions button");
    await expect(deferredMutationButtons).toHaveCount(6);
    await expect(deferredMutationButtons.locator(":not([disabled])")).toHaveCount(0);
    await expect(page.getByRole("link", { name: /graph/i })).toHaveCount(0);
  } finally {
    await context.close();
  }
});

test("authors a draft through real mutations, reloads its direct URL, and repeats add/inspect on mobile", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();
  const workspaceId = "console-authoring-e2e";
  try {
    await page.goto(`${baseUrl}/console/drafts`);
    await connect(page);
    await page.getByRole("button", { name: "New draft" }).click();
    await page.getByLabel("Workspace id").fill(workspaceId);
    await page.getByLabel("Draft name").fill("console_authoring_e2e");
    await page.getByLabel("Title").fill("Console Authoring E2E");
    await page.getByRole("button", { name: "Create draft" }).click();
    await expect(page).toHaveURL(`${baseUrl}/console/drafts/${workspaceId}`);
    await expect(page.getByRole("heading", { name: "Console Authoring E2E" })).toBeVisible();

    const capability = "local.lda_docs.list_documents";
    await page.getByRole("button", { name: capability, exact: true }).click();
    await expect(page.getByRole("button", { name: "Add node" })).toBeVisible();
    await page.getByRole("textbox", { name: "Step id" }).fill("list_documents");
    await page.getByRole("button", { name: "Add node" }).click();
    await expect(page.getByTestId("rf__node-list_documents")).toBeVisible();
    await expandEvidence(page, "workflow.draft_workspaces.create_empty", {
      request: {
        jsonrpc: "2.0",
        method: "workflow.draft_workspaces.create_empty",
        params: { workspace_id: workspaceId, name: "console_authoring_e2e", title: "Console Authoring E2E" },
      },
      response: { result: { workspace_id: workspaceId, revision: 1 } },
    });
    await expandEvidence(page, "workflow.draft_workspaces.add_step_from_capability", {
      request: {
        jsonrpc: "2.0",
        method: "workflow.draft_workspaces.add_step_from_capability",
        params: { workspace_id: workspaceId, revision: 1, step_id: "list_documents", capability_name: capability },
      },
      response: { result: { workspace_id: workspaceId, revision: 2 } },
    });

    await page.getByRole("button", { name: /list_documents.*ok.*__end__/ }).click();
    await expect(page.getByRole("heading", { name: "Route inspector" })).toBeVisible();
    await page.getByRole("button", { name: capability, exact: true }).click();
    const inspectorSheet = page.getByRole("dialog", { name: "Context inspector sheet" });
    await expect(inspectorSheet.getByRole("heading", { name: capability })).toBeVisible();
    const secondStepId = inspectorSheet.getByRole("textbox", { name: "Step id" });
    await secondStepId.fill("list_documents_next");
    await secondStepId.press("Enter");
    await expect(
      page.locator(".evidence-op").filter({ hasText: "workflow.draft_workspaces.add_step_from_capability" }),
    ).toHaveCount(2);
    await expect(page.getByTestId("rf__node-list_documents_next")).toBeVisible();
    await page.getByTestId("rf__node-list_documents_next").getByRole("button").click();

    const description = page.getByRole("textbox", { name: "Description" });
    await description.fill("Second capability edit");
    await description.press("Enter");
    await expect(page.getByTestId("rf__node-list_documents_next")).toBeVisible();
    await expandEvidence(page, "workflow.draft_workspaces.update_capability_step", {
      request: {
        jsonrpc: "2.0",
        method: "workflow.draft_workspaces.update_capability_step",
        params: { workspace_id: workspaceId, revision: 3, step_id: "list_documents_next" },
      },
      response: { result: { workspace_id: workspaceId, revision: 4 } },
    });

    await page.getByRole("button", { name: /list_documents_next.*ok.*__end__/ }).click();
    const targetStep = page.getByRole("textbox", { name: "Target step" });
    await targetStep.fill("__end__");
    await targetStep.press("Enter");
    await expect(page.getByRole("button", { name: /list_documents_next.*ok.*__end__/ })).toBeVisible();
    await expandEvidence(page, "workflow.draft_workspaces.set_route", {
      request: {
        jsonrpc: "2.0",
        method: "workflow.draft_workspaces.set_route",
        params: { workspace_id: workspaceId, revision: 4, step_id: "list_documents_next", outcome: "ok", target: "__end__" },
      },
      response: { result: { workspace_id: workspaceId, revision: 5 } },
    });

    await page.reload();
    await connect(page);
    const summary = page.getByRole("heading", { name: "Draft summary" }).locator("..");
    await page.getByRole("button", { name: "Validate draft" }).press("Enter");
    await expect(
      page.locator(".evidence-op").filter({ hasText: "workflow.draft_workspaces.validate" }),
    ).toBeVisible();
    await expect(summary).toContainText("Revision 5");
    await expect(summary).toContainText("Invalid");
    await expect(page.getByRole("heading", { name: "Diagnostics" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Diagnostics" })).toContainText("draft_invalid");
    await page.getByText("Raw draft document", { exact: true }).click();
    await expect(page.getByRole("region", { name: "Raw draft JSON, horizontally scrollable" })).toContainText(
      "list_documents_next",
    );
    await expandEvidence(page, "workflow.draft_workspaces.validate", {
      request: {
        jsonrpc: "2.0",
        method: "workflow.draft_workspaces.validate",
        params: { workspace_id: workspaceId },
      },
      response: { result: { workspace_id: workspaceId, revision: 5 } },
    });

    await page.reload();
    await connect(page);
    await expect(page).toHaveURL(`${baseUrl}/console/drafts/${workspaceId}`);
    await expect(page.getByTestId("rf__node-list_documents")).toBeVisible();
    await expect(page.getByTestId("rf__node-list_documents_next")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Draft summary" }).locator("..")).toContainText("Revision 5");
    await expect(page.getByRole("heading", { name: "Diagnostics" })).toBeVisible();
    await expandEvidence(page, "workflow.draft_workspaces.get", {
      request: {
        jsonrpc: "2.0",
        method: "workflow.draft_workspaces.get",
        params: { workspace_id: workspaceId, include_draft: true },
      },
      response: { result: { workspace_id: workspaceId, revision: 5, draft: expect.any(Object) } },
    });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    await connect(page);
    await page.getByRole("button", { name: "Open capability palette" }).click();
    await page.getByRole("button", { name: capability, exact: true }).click();
    await page.getByRole("button", { name: "Close capability palette" }).click();
    await page.getByRole("button", { name: "Open context inspector" }).click();
    await expect(page.getByRole("heading", { name: capability })).toBeVisible();
    const mobileInspector = page.getByRole("dialog", { name: "Context inspector sheet" });
    await expect(mobileInspector).toHaveCSS("height", "844px");
    await expect(mobileInspector.locator(".context-inspector")).toHaveCSS("overflow-y", "auto");
    await page.getByRole("textbox", { name: "Step id" }).fill("mobile_list_documents");
    await page.getByRole("button", { name: "Close context inspector" }).click();
    await page.getByRole("button", { name: "Open context inspector" }).click();
    await expect(page.getByRole("textbox", { name: "Step id" })).toHaveValue("mobile_list_documents");
    await page.getByRole("button", { name: "Add node" }).click();
    await expect(page.getByTestId("rf__node-mobile_list_documents")).toBeVisible();
    await expect(page.getByRole("region", { name: "Workflow graph" })).toBeVisible();
  } finally {
    await context.close();
  }
});
