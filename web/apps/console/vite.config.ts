import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const backendPort = process.env.WEB_PORT ?? "8787";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Server must listen on this port (set via WEB_PORT env or default 8787)
      "/api": {
        target: `http://127.0.0.1:${backendPort}`,
        configure: (proxy) => {
          proxy.on("error", (error, _request, response) => {
            if (response.headersSent) return;
            const detail =
              error instanceof Error ? ` (${error.message})` : "";
            response.writeHead(502, {
              "content-type": "application/json",
            });
            response.end(
              JSON.stringify({
                ok: false,
                error: {
                  code: "console_backend_unreachable",
                  message:
                    `Console backend unavailable at 127.0.0.1:${backendPort}. ` +
                    `Restart pnpm --dir web dev.${detail}`,
                },
                exchange: { request: null, response: null },
              }),
            );
          });
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
