import { createServer } from "node:net";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { once } from "node:events";
import { fileURLToPath } from "node:url";
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

const INITIAL_HASH = "#scene/thesis/title";
const ARCHITECTURE_FOCUS_HASH =
  "#scene/architecture/runtime/focus/runtime-providers/configured-providers";
const DISCUSSION_HASH = "#discuss/where-is-ai-agent";
const serverEntry = fileURLToPath(new URL("../../server/dist/index.js", import.meta.url));

let server: ChildProcessWithoutNullStreams;
let baseUrl: string;

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

const waitForServer = async (child: ChildProcessWithoutNullStreams): Promise<void> => {
  let output = "";
  child.stdout.on("data", (chunk: Buffer) => {
    output += chunk.toString();
  });
  child.stderr.on("data", (chunk: Buffer) => {
    output += chunk.toString();
  });

  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (child.exitCode !== null) {
      throw new Error(`E2E server exited with ${child.exitCode}:\n${output}`);
    }
    try {
      const response = await fetch(baseUrl);
      if (response.ok) return;
    } catch {
      // The isolated process has not bound its port yet.
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`E2E server did not become ready:\n${output}`);
};

const stopServer = async (): Promise<void> => {
  if (server.exitCode !== null) return;
  const exited = once(server, "exit");
  server.kill("SIGTERM");
  const exitedGracefully = await Promise.race([
    exited.then(() => true),
    new Promise<false>((resolve) => setTimeout(() => resolve(false), 7_000)),
  ]);
  if (exitedGracefully || server.exitCode !== null) return;

  // Never reach beyond the child created by this test when graceful server
  // shutdown fails; force only that recorded process and wait for its exit.
  const forcedExit = once(server, "exit");
  server.kill("SIGKILL");
  await forcedExit;
};

const hashOf = (page: Page): string => new URL(page.url()).hash;

const expectHashes = async (expected: string, ...pages: readonly Page[]): Promise<void> => {
  await expect.poll(() => pages.map(hashOf)).toEqual(pages.map(() => expected));
};

const startSession = async (
  page: Page,
  creatorPath: "/present" | "/presenter",
): Promise<string> => {
  await page.getByRole("button", { name: "Pair presentation" }).click();
  await page.getByRole("button", { name: "Start session" }).click();
  const code = page.locator(".presentation-pairing__code");
  await expect(code).toBeVisible();
  const value = (await code.textContent())?.trim() ?? "";
  const joinPath = creatorPath === "/presenter" ? "/present" : "/presenter";
  const joinUrl = `${baseUrl}${joinPath}?pair=${value}`;
  await expect(page.getByRole("img", { name: "Pairing QR code" })).toHaveAttribute(
    "data-qr-value",
    joinUrl,
  );
  await expect(page.getByRole("link", { name: "Copyable join URL" })).toHaveAttribute(
    "href",
    joinUrl,
  );
  return value;
};

const expectConnected = async (...pages: readonly Page[]): Promise<void> => {
  await Promise.all(
    pages.map((page) =>
      expect(page.getByRole("status", { name: "Connected" })).toBeVisible(),
    ),
  );
};

const openPair = async (
  browser: Browser,
  creatorPath: "/present" | "/presenter",
  joinMethod: "link" | "code" = "link",
): Promise<{
  creatorContext: BrowserContext;
  creator: Page;
  joinerContext: BrowserContext;
  joiner: Page;
}> => {
  const creatorIsPresenter = creatorPath === "/presenter";
  const creatorContext = await browser.newContext({
    viewport: creatorIsPresenter ? { width: 390, height: 844 } : { width: 1280, height: 720 },
  });
  const joinerContext = await browser.newContext({
    viewport: creatorIsPresenter ? { width: 1280, height: 720 } : { width: 390, height: 844 },
  });
  const creator = await creatorContext.newPage();
  await creator.goto(`${baseUrl}${creatorPath}${INITIAL_HASH}`);
  const code = await startSession(creator, creatorPath);
  expect(code).toMatch(/^[A-Z0-9]{6}$/);

  const joinerPath = creatorIsPresenter ? "/present" : "/presenter";
  const joiner = await joinerContext.newPage();
  if (joinMethod === "link") {
    await joiner.goto(`${baseUrl}${joinerPath}?pair=${code}${INITIAL_HASH}`);
  } else {
    await joiner.goto(`${baseUrl}${joinerPath}${INITIAL_HASH}`);
    await joiner.getByRole("button", { name: "Pair presentation" }).click();
    await joiner.getByLabel("Pairing code").fill(code);
    await joiner.getByRole("button", { name: "Join session" }).click();
  }
  await expectConnected(creator, joiner);
  await expectHashes(INITIAL_HASH, creator, joiner);
  return { creatorContext, creator, joinerContext, joiner };
};

test.beforeAll(async () => {
  const port = await reservePort();
  baseUrl = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, [serverEntry], {
    env: {
      ...process.env,
      WEB_HOST: process.env.PRESENTATION_E2E_BIND_HOST ?? "127.0.0.1",
      WEB_PORT: String(port),
    },
    stdio: ["pipe", "pipe", "pipe"],
  });
  await waitForServer(server);
});

test.afterAll(async () => {
  await stopServer();
});

test("synchronizes presenter and audience navigation, reload, fidelity, and termination", async ({ browser }) => {
  const { creatorContext: phoneContext, creator: phone, joinerContext: audienceContext, joiner: audience } =
    await openPair(browser, "/presenter");

  try {
    await phone.getByRole("link", { name: "Next →", exact: true }).click();
    await expectHashes("#scene/thesis/substrate", phone, audience);

    await audience.keyboard.press("ArrowLeft");
    await expectHashes(INITIAL_HASH, phone, audience);

    await audience.evaluate((hash) => {
      window.location.hash = hash;
    }, DISCUSSION_HASH);
    await expectHashes(DISCUSSION_HASH, phone, audience);
    await expect(phone.getByText("Q&A", { exact: true }).first()).toBeVisible();

    await audience.evaluate((hash) => {
      window.location.hash = hash;
    }, ARCHITECTURE_FOCUS_HASH);
    await expectHashes(ARCHITECTURE_FOCUS_HASH, phone, audience);

    await phone.reload();
    await expectConnected(phone, audience);
    await expectHashes(ARCHITECTURE_FOCUS_HASH, phone, audience);

    await phone.getByRole("button", { name: "End presentation" }).click();
    await phone.getByRole("button", { name: "End presentation now" }).click();
    await Promise.all([
      expect(phone.getByText("The presenter ended this session.")).toBeVisible(),
      expect(audience.getByText("The presenter ended this session.")).toBeVisible(),
    ]);
  } finally {
    await phoneContext.close();
    await audienceContext.close();
  }
});

test("supports symmetric creation from the audience route", async ({ browser }) => {
  const { creatorContext: audienceContext, creator: audience, joinerContext: phoneContext, joiner: phone } =
    await openPair(browser, "/present", "code");

  try {
    await audience.keyboard.press("ArrowRight");
    await expectHashes("#scene/thesis/substrate", audience, phone);

    await phone.getByRole("link", { name: "← Previous", exact: true }).click();
    await expectHashes(INITIAL_HASH, audience, phone);

    await phone.getByRole("button", { name: "End presentation" }).click();
    await phone.getByRole("button", { name: "End presentation now" }).click();
    await Promise.all([
      expect(phone.getByText("The presenter ended this session.")).toBeVisible(),
      expect(audience.getByText("The presenter ended this session.")).toBeVisible(),
    ]);
  } finally {
    await audienceContext.close();
    await phoneContext.close();
  }
});
