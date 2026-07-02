# lda.chat Workflow Console

A local React console for inspecting workflow JSON-RPC servers. Connects to a
loopback `wf-rpc-server` through a Hono proxy, displays source inventory and
raw protocol evidence.

## Quick Start

```powershell
# Terminal 1: workflow JSON-RPC server
uv run wf-rpc-server --config wf.config.json --host 127.0.0.1 --port 8765

# Terminal 2: development (Vite + Hono)
pnpm --dir web install
pnpm --dir web dev
```

Open `http://127.0.0.1:5173` in the browser. Paste the target URL:

```text
http://127.0.0.1:8765/rpc
```

Click **Connect**. The console will:

1. Validate the target is a loopback address
2. Call `workflow.health` on the upstream server
3. Display connection status and source inventory
4. Show raw protocol evidence for each operation

## Production Build

```powershell
pnpm --dir web build
pnpm --dir web start
```

A single Hono process serves the built React application and API routes from
`http://127.0.0.1:8787`.

## Commands

| Command | Description |
|---------|-------------|
| `pnpm --dir web install` | Install all workspace dependencies |
| `pnpm --dir web dev` | Start Vite + Hono development servers |
| `pnpm --dir web test` | Run all test suites |
| `pnpm --dir web typecheck` | Run TypeScript type checking |
| `pnpm --dir web build` | Build the React console for production |
| `pnpm --dir web start` | Start the production Hono server |

## Architecture

```text
web/
  apps/
    console/    React + Vite frontend
    server/     Hono local server (API + static serving)
  packages/
    rpc/        Effect-based JSON-RPC client, schemas, and errors
```

The browser communicates with Hono at `/api/connect` and `/api/rpc`. Hono
validates targets against loopback policy, executes typed JSON-RPC calls
through Effect, and returns plain JSON DTOs to the browser.

## Security

- Only loopback targets are accepted (`127.0.0.1`, `localhost`, `[::1]`)
- Upstream redirects are rejected
- Request bodies are limited to 256 KiB
- Response bodies are limited to 4 MiB
- The server binds to `127.0.0.1` by default

## Smoke Test

With the Python server running, verify in the browser:

1. The initial page makes no upstream request
2. Connect succeeds against `http://127.0.0.1:8765/rpc`
3. Source rows appear after connection
4. Raw health and source-list exchanges are selectable in the evidence drawer
5. Equivalent CLI text is visible
6. `http://example.com:8765/rpc` is rejected without upstream fetch
7. Stopping the Python server produces the unreachable state while preserving
   the entered URL
