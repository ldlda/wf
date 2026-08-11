import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { initialState } from "../../app/state.js";
import { useConsoleWorkspace } from "../context.js";
import type { CapabilityCallResult, CapabilityDetail } from "../domain/capability-models.js";
import type { ConsoleWriteExecutor } from "../domain/write-executor.js";
import type {
  CapabilityPlaygroundController,
} from "./useCapabilityPlayground.js";
import { useCapabilityPlayground } from "./useCapabilityPlayground.js";
import { CapabilityPlayground } from "./CapabilityPlayground.js";

vi.mock("./useCapabilityPlayground.js", () => ({
  useCapabilityPlayground: vi.fn(),
}));

vi.mock("../context.js", () => ({
  useConsoleWorkspace: vi.fn(),
}));

const mockedUseCapabilityPlayground = vi.mocked(useCapabilityPlayground);
const mockedUseConsoleWorkspace = vi.mocked(useConsoleWorkspace);

const writeExecutor = {} as ConsoleWriteExecutor;

const nodeCapability: CapabilityDetail = {
  kind: "node_spec",
  name: "local.documents.read",
  sourceId: "local.documents",
  description: "Read project documents.",
  isAsync: false,
  outcomes: ["ok", "error"],
  inputSchema: {
    type: "object",
    properties: {
      query: { type: "string", title: "Query" },
    },
    required: ["query"],
  },
  outputSchema: { type: "object", properties: { documents: { type: "array" } } },
  wrapperHints: { input: "query", output: "documents" },
  acceptsContext: false,
};

const wrapperCapability: CapabilityDetail = {
  kind: "wrapper_artifact",
  name: "local.documents.wrapper",
  sourceId: "local.documents",
  description: "Call the document wrapper.",
  isAsync: false,
  outcomes: ["ok", "runtime_error"],
  inputSchema: nodeCapability.inputSchema,
  outputSchema: nodeCapability.outputSchema,
  wrapperHints: { input: "query", output: "documents" },
  artifactId: "documents-wrapper",
  title: "Documents wrapper",
  version: 1,
  requiredCapabilities: {},
};

const callResult = (overrides: Partial<CapabilityCallResult> = {}): CapabilityCallResult => ({
  qualifiedName: nodeCapability.name,
  sourceId: nodeCapability.sourceId,
  kind: nodeCapability.kind,
  deploymentId: null,
  outcome: "ok",
  output: { documents: ["README.md"] },
  diagnostics: [
    {
      boundSource: "local.documents",
      code: "dependency_checked",
      logicalRef: "documents",
      message: "Document source was checked.",
      repairHint: null,
      severity: "info",
    },
  ],
  ...overrides,
});

const controller = (
  overrides: Partial<CapabilityPlaygroundController> = {},
): CapabilityPlaygroundController => ({
  phase: "idle",
  result: null,
  message: null,
  acknowledged: false,
  deploymentId: "",
  setAcknowledged: vi.fn(),
  setDeploymentId: vi.fn(),
  call: vi.fn(),
  reset: vi.fn(),
  ...overrides,
});

const renderPlayground = (capability: CapabilityDetail = nodeCapability) =>
  render(
    <CapabilityPlayground
      capability={capability}
      executor={writeExecutor}
      target="http://workflow.example/rpc"
    />,
  );

beforeEach(() => {
  mockedUseConsoleWorkspace.mockReturnValue({
    connection: {
      ...initialState(),
      evidence: [
        {
          id: "call-1",
          target: "http://workflow.example/rpc",
          operation: "workflow.capabilities.call",
          label: "Call capability",
          equivalentCli: "wf capability call",
          request: {},
          response: {},
          durationMs: 18,
        },
      ],
    },
    connectedTarget: "http://workflow.example/rpc",
    recordEvidence: vi.fn(),
    readExecutor: null,
    writeExecutor,
  });
  mockedUseCapabilityPlayground.mockReturnValue(controller());
});

afterEach(() => cleanup());

describe("CapabilityPlayground", () => {
  it("starts on an accessible Contract view with facts, schemas, and draft action", () => {
    renderPlayground();

    expect(screen.getByRole("tab", { name: "Contract" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "Try capability" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: nodeCapability.name })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Input schema" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Output schema" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Wrapper hints" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add to draft" })).toBeInTheDocument();
  });

  it("shows the literal-only form and immediate execution warning in Try", async () => {
    const user = userEvent.setup();
    renderPlayground();

    await user.click(screen.getByRole("tab", { name: "Try capability" }));

    expect(screen.getByText("This calls the capability immediately against the connected workflow server.")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Query" })).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Value source" })).not.toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /I understand/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Call capability" })).toBeDisabled();
  });

  it("gates the call behind acknowledgement and never calls for render, tab selection, or edits", async () => {
    const user = userEvent.setup();
    const call = vi.fn();
    mockedUseCapabilityPlayground.mockReturnValue(
      controller({ acknowledged: true, call }),
    );
    renderPlayground();

    expect(call).not.toHaveBeenCalled();
    await user.click(screen.getByRole("tab", { name: "Try capability" }));
    expect(call).not.toHaveBeenCalled();
    await user.type(screen.getByRole("textbox", { name: "Query" }), "README.md");
    expect(call).not.toHaveBeenCalled();
  });

  it("passes only literal object values to the controller after acknowledgement", async () => {
    const user = userEvent.setup();
    const call = vi.fn();
    const setAcknowledged = vi.fn();
    mockedUseCapabilityPlayground.mockReturnValue(
      controller({ acknowledged: true, call, setAcknowledged }),
    );
    renderPlayground();

    await user.click(screen.getByRole("tab", { name: "Try capability" }));
    await user.type(screen.getByRole("textbox", { name: "Query" }), "README.md");
    await user.click(screen.getByRole("button", { name: "Call capability" }));

    expect(call).toHaveBeenCalledWith({ query: "README.md" });
  });

  it("shows deployment input only for wrapper capabilities", async () => {
    const user = userEvent.setup();
    const { unmount } = renderPlayground();
    await user.click(screen.getByRole("tab", { name: "Try capability" }));
    expect(screen.queryByRole("textbox", { name: "Wrapper deployment ID" })).not.toBeInTheDocument();

    unmount();
    renderPlayground(wrapperCapability);
    await user.click(screen.getByRole("tab", { name: "Try capability" }));
    expect(screen.getByRole("textbox", { name: "Wrapper deployment ID" })).toBeInTheDocument();
  });

  it.each([
    ["calling", controller({ phase: "calling", acknowledged: true }), "Calling capability..."],
    ["rejected", controller({ phase: "error", message: "Operation rejected by policy" }), "Operation rejected by policy"],
  ] as const)("renders the %s state inline", async (_label, state, textContent) => {
    const user = userEvent.setup();
    mockedUseCapabilityPlayground.mockReturnValue(state);
    renderPlayground();
    await user.click(screen.getByRole("tab", { name: "Try capability" }));

    if (state.phase === "calling") {
      expect(screen.getByRole("button", { name: textContent })).toBeDisabled();
    } else {
      expect(screen.getByRole("alert")).toHaveTextContent(textContent);
    }
  });

  it("renders outcome, evidence provenance, diagnostics, and bounded output in the receipt", async () => {
    mockedUseCapabilityPlayground.mockReturnValue(
      controller({ phase: "result", acknowledged: true, result: callResult() }),
    );
    renderPlayground();

    await userEvent.click(screen.getByRole("tab", { name: "Try capability" }));

    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("18 ms")).toBeInTheDocument();
    expect(screen.getByText("workflow.capabilities.call")).toBeInTheDocument();
    expect(screen.getByText("Document source was checked.")).toBeInTheDocument();
    expect(screen.getByLabelText("Capability output")).toHaveTextContent("README.md");
  });

  it("labels runtime_error as completed without claiming a workflow run or trace", async () => {
    mockedUseCapabilityPlayground.mockReturnValue(
      controller({
        phase: "result",
        acknowledged: true,
        result: callResult({ outcome: "runtime_error", output: null, diagnostics: [] }),
      }),
    );
    renderPlayground();

    await userEvent.click(screen.getByRole("tab", { name: "Try capability" }));

    expect(screen.getByText("Completed with runtime error")).toBeInTheDocument();
    expect(screen.getByText("No workflow run or trace was created.")).toBeInTheDocument();
  });

  it("rejects a non-object serialized root locally", async () => {
    const user = userEvent.setup();
    const call = vi.fn();
    mockedUseCapabilityPlayground.mockReturnValue(
      controller({ acknowledged: true, call }),
    );
    renderPlayground({
      ...nodeCapability,
      name: "local.documents.invalid-root",
      inputSchema: { type: "array", items: { type: "string" } },
    });

    await user.click(screen.getByRole("tab", { name: "Try capability" }));
    await user.click(screen.getByRole("button", { name: "Call capability" }));

    expect(call).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Capability inputs must serialize to an object.",
    );
  });

  it("clears the receipt and acknowledgement when the capability changes", async () => {
    const firstState = controller({
      phase: "result",
      acknowledged: true,
      result: callResult(),
    });
    const secondState = controller();
    mockedUseCapabilityPlayground.mockImplementation((qualifiedName: string | null) =>
      qualifiedName === nodeCapability.name ? firstState : secondState,
    );
    const { rerender } = render(
      <CapabilityPlayground
        capability={nodeCapability}
        executor={writeExecutor}
        target="http://workflow.example/rpc"
      />,
    );

    await userEvent.click(screen.getByRole("tab", { name: "Try capability" }));
    expect(screen.getByText("Completed")).toBeInTheDocument();

    rerender(
      <CapabilityPlayground
        capability={{ ...nodeCapability, name: "local.documents.write" }}
        executor={writeExecutor}
        target="http://workflow.example/rpc"
      />,
    );

    expect(screen.queryByText("Completed")).not.toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /I understand/i })).not.toBeChecked();
  });
});
