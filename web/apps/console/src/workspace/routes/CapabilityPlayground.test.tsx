import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { initialState, type EvidenceRecord } from "../../app/state.js";
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
const target = "http://workflow.example/rpc";

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

const capabilityEvidence = (
  id: string,
  qualifiedName: string,
  durationMs: number,
  evidenceTarget = target,
): EvidenceRecord => ({
  id,
  target: evidenceTarget,
  operation: "workflow.capabilities.call",
  label: "Call capability",
  equivalentCli: "wf capability call",
  request: { qualified_name: qualifiedName, payload: {} },
  response: {},
  durationMs,
});

const workspaceWithEvidence = (
  evidence: ReadonlyArray<EvidenceRecord>,
  connectedTarget: string | null = target,
  executor: ConsoleWriteExecutor | null = writeExecutor,
) => ({
  connection: { ...initialState(), evidence },
  connectedTarget,
  recordEvidence: vi.fn(),
  readExecutor: null,
  writeExecutor: executor,
});

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
      target={target}
    />,
  );

const submitNodeCall = async (query = "README.md"): Promise<void> => {
  const user = userEvent.setup();
  await user.click(screen.getByRole("tab", { name: "Try capability" }));
  await user.type(screen.getByRole("textbox", { name: "Query" }), query);
  await user.click(screen.getByRole("button", { name: "Call capability" }));
};

beforeEach(() => {
  mockedUseConsoleWorkspace.mockReturnValue({
    connection: {
      ...initialState(),
      evidence: [
        capabilityEvidence("call-1", "local.documents.other", 18),
      ],
    },
    connectedTarget: target,
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

  it("implements a roving keyboard tab pattern with activation and stable panel names", async () => {
    const user = userEvent.setup();
    renderPlayground();

    const contractTab = screen.getByRole("tab", { name: "Contract" });
    const tryTab = screen.getByRole("tab", { name: "Try capability" });
    contractTab.focus();

    expect(contractTab).toHaveAttribute("tabindex", "0");
    expect(tryTab).toHaveAttribute("tabindex", "-1");
    await user.keyboard("{ArrowRight}");

    expect(tryTab).toHaveFocus();
    expect(tryTab).toHaveAttribute("aria-selected", "true");
    expect(contractTab).toHaveAttribute("tabindex", "-1");
    expect(screen.getByRole("tabpanel", { name: "Try capability" })).toHaveAttribute(
      "aria-labelledby",
      tryTab.id,
    );

    await user.keyboard("{End}");
    expect(tryTab).toHaveFocus();
    await user.keyboard("{Home}");
    expect(contractTab).toHaveFocus();
    await user.keyboard("{ArrowLeft}");
    expect(tryTab).toHaveFocus();
    await user.keyboard("{ArrowRight}");
    expect(contractTab).toHaveFocus();
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

  it("keeps the submitted payload and deployment immutable when the form changes", async () => {
    const user = userEvent.setup();
    const call = vi.fn();
    let activeController = controller({
      acknowledged: true,
      call,
      deploymentId: "docs.default",
    });
    mockedUseCapabilityPlayground.mockImplementation(() => activeController);
    const view = renderPlayground(wrapperCapability);

    await user.click(screen.getByRole("tab", { name: "Try capability" }));
    await user.type(screen.getByRole("textbox", { name: "Query" }), "README.md");
    await user.click(screen.getByRole("button", { name: "Call capability" }));
    await user.clear(screen.getByRole("textbox", { name: "Query" }));
    await user.type(screen.getByRole("textbox", { name: "Query" }), "changed.md");
    await user.clear(screen.getByRole("textbox", { name: "Wrapper deployment ID" }));
    await user.type(screen.getByRole("textbox", { name: "Wrapper deployment ID" }), "changed.default");
    activeController = controller({
      acknowledged: true,
      call,
      deploymentId: "changed.default",
    });
    view.rerender(
      <CapabilityPlayground
        capability={wrapperCapability}
        executor={writeExecutor}
        target={target}
      />,
    );

    activeController = controller({
      phase: "result",
      acknowledged: true,
      result: callResult({
        qualifiedName: wrapperCapability.name,
        sourceId: wrapperCapability.sourceId,
        kind: wrapperCapability.kind,
        deploymentId: "docs.default",
      }),
    });
    mockedUseCapabilityPlayground.mockReturnValue(activeController);
    mockedUseConsoleWorkspace.mockReturnValue(
      workspaceWithEvidence([
        capabilityEvidence("call-submitted", wrapperCapability.name, 18),
      ]),
    );
    view.rerender(
      <CapabilityPlayground
        capability={wrapperCapability}
        executor={writeExecutor}
        target={target}
      />,
    );

    expect(screen.getByLabelText("Submitted payload")).toHaveTextContent("README.md");
    expect(screen.getByLabelText("Submitted payload")).not.toHaveTextContent("changed.md");
    expect(screen.getByLabelText("Submitted deployment")).toHaveTextContent("docs.default");
    expect(screen.getByLabelText("Submitted deployment")).not.toHaveTextContent("changed.default");
  });

  it("rejects serialization issues before calling and shows an inline alert", async () => {
    const user = userEvent.setup();
    const call = vi.fn();
    mockedUseCapabilityPlayground.mockReturnValue(
      controller({ acknowledged: true, call }),
    );
    renderPlayground();

    await user.click(screen.getByRole("tab", { name: "Try capability" }));
    await user.click(screen.getByRole("button", { name: "Call capability" }));

    expect(call).not.toHaveBeenCalled();
    expect(screen.getAllByRole("alert").at(-1)).toHaveTextContent(
      "Required field is incomplete.",
    );
  });

  it("bounds long output in the result receipt", async () => {
    const user = userEvent.setup();
    let activeController = controller({ acknowledged: true });
    mockedUseCapabilityPlayground.mockImplementation(() => activeController);
    const view = renderPlayground();

    await user.click(screen.getByRole("tab", { name: "Try capability" }));
    await user.type(screen.getByRole("textbox", { name: "Query" }), "README.md");
    await user.click(screen.getByRole("button", { name: "Call capability" }));

    activeController = controller({
      phase: "result",
      acknowledged: true,
      result: callResult({ output: { content: "x".repeat(14_000) } }),
    });
    mockedUseCapabilityPlayground.mockReturnValue(activeController);
    mockedUseConsoleWorkspace.mockReturnValue(
      workspaceWithEvidence([capabilityEvidence("call-output", nodeCapability.name, 18)]),
    );
    view.rerender(
      <CapabilityPlayground
        capability={nodeCapability}
        executor={writeExecutor}
        target={target}
      />,
    );

    const output = screen.getByLabelText("Capability output");
    expect(output).toHaveTextContent("... truncated ...");
    expect(output.textContent?.length).toBeLessThanOrEqual(12_000);
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
    let activeController = controller({ acknowledged: true });
    mockedUseCapabilityPlayground.mockImplementation(() => activeController);
    const view = renderPlayground();
    await submitNodeCall();
    activeController = controller({
      phase: "result",
      acknowledged: true,
      result: callResult(),
    });
    mockedUseCapabilityPlayground.mockReturnValue(activeController);
    mockedUseConsoleWorkspace.mockReturnValue(
      workspaceWithEvidence([
        capabilityEvidence("call-1", "local.documents.other", 18),
        capabilityEvidence("call-2", nodeCapability.name, 24),
      ]),
    );
    view.rerender(
      <CapabilityPlayground
        capability={nodeCapability}
        executor={writeExecutor}
        target={target}
      />,
    );

    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("24 ms")).toBeInTheDocument();
    expect(screen.getByText("workflow.capabilities.call")).toBeInTheDocument();
    expect(screen.getByText("Document source was checked.")).toBeInTheDocument();
    expect(screen.getByText("A direct capability call creates no workflow run or trace.")).toBeInTheDocument();
    expect(screen.getByLabelText("Capability output")).toHaveTextContent("README.md");
  });

  it("labels runtime_error as completed without claiming a workflow run or trace", async () => {
    let activeController = controller({ acknowledged: true });
    mockedUseCapabilityPlayground.mockImplementation(() => activeController);
    const view = renderPlayground();
    await submitNodeCall();
    activeController = controller({
      phase: "result",
      acknowledged: true,
      result: callResult({ outcome: "runtime_error", output: null, diagnostics: [] }),
    });
    mockedUseCapabilityPlayground.mockReturnValue(activeController);
    mockedUseConsoleWorkspace.mockReturnValue(
      workspaceWithEvidence([
        capabilityEvidence("call-1", "local.documents.other", 18),
        capabilityEvidence("call-runtime", nodeCapability.name, 31),
      ]),
    );
    view.rerender(
      <CapabilityPlayground
        capability={nodeCapability}
        executor={writeExecutor}
        target={target}
      />,
    );

    expect(screen.getByText("Completed with runtime error")).toBeInTheDocument();
    expect(screen.getByText("A direct capability call creates no workflow run or trace.")).toBeInTheDocument();
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
    let firstState = controller({ acknowledged: true });
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
    await userEvent.type(screen.getByRole("textbox", { name: "Query" }), "README.md");
    await userEvent.click(screen.getByRole("button", { name: "Call capability" }));
    firstState = controller({
      phase: "result",
      acknowledged: true,
      result: callResult(),
    });
    mockedUseConsoleWorkspace.mockReturnValue(
      workspaceWithEvidence([
        capabilityEvidence("call-1", "local.documents.other", 18),
        capabilityEvidence("call-clear", nodeCapability.name, 22),
      ]),
    );
    rerender(
      <CapabilityPlayground
        capability={nodeCapability}
        executor={writeExecutor}
        target="http://workflow.example/rpc"
      />,
    );
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

  it("matches the submitted capability and ignores an interleaved call", async () => {
    let activeController = controller({ acknowledged: true });
    mockedUseCapabilityPlayground.mockImplementation(() => activeController);
    const view = renderPlayground();
    await submitNodeCall();

    activeController = controller({
      phase: "result",
      acknowledged: true,
      result: callResult(),
    });
    mockedUseCapabilityPlayground.mockReturnValue(activeController);
    mockedUseConsoleWorkspace.mockReturnValue(
      workspaceWithEvidence([
        capabilityEvidence("call-submitted", nodeCapability.name, 24),
        capabilityEvidence("call-interleaved", "local.documents.other", 99),
      ]),
    );
    view.rerender(
      <CapabilityPlayground
        capability={nodeCapability}
        executor={writeExecutor}
        target={target}
      />,
    );

    expect(screen.getByText("24 ms")).toBeInTheDocument();
    expect(screen.queryByText("99 ms")).not.toBeInTheDocument();
  });

  it("matches only evidence added after the current repeated call", async () => {
    let activeController = controller({ acknowledged: true });
    mockedUseCapabilityPlayground.mockImplementation(() => activeController);
    mockedUseConsoleWorkspace.mockReturnValue(
      workspaceWithEvidence([capabilityEvidence("call-first", nodeCapability.name, 11)]),
    );
    const view = renderPlayground();
    await submitNodeCall("first.md");

    mockedUseCapabilityPlayground.mockReturnValue(
      controller({
        phase: "result",
        acknowledged: true,
        result: callResult(),
      }),
    );
    mockedUseConsoleWorkspace.mockReturnValue(
      workspaceWithEvidence([capabilityEvidence("call-first", nodeCapability.name, 11)]),
    );
    view.rerender(
      <CapabilityPlayground
        capability={nodeCapability}
        executor={writeExecutor}
        target={target}
      />,
    );
    expect(screen.queryByText("11 ms")).not.toBeInTheDocument();

    activeController = controller({ acknowledged: true });
    mockedUseCapabilityPlayground.mockReturnValue(activeController);
    const user = userEvent.setup();
    await user.clear(screen.getByRole("textbox", { name: "Query" }));
    await user.type(screen.getByRole("textbox", { name: "Query" }), "second.md");
    await user.click(screen.getByRole("button", { name: "Call capability" }));

    activeController = controller({
      phase: "result",
      acknowledged: true,
      result: callResult(),
    });
    mockedUseCapabilityPlayground.mockReturnValue(activeController);
    mockedUseConsoleWorkspace.mockReturnValue(
      workspaceWithEvidence([
        capabilityEvidence("call-first", nodeCapability.name, 11),
        capabilityEvidence("call-second", nodeCapability.name, 22),
      ]),
    );
    view.rerender(
      <CapabilityPlayground
        capability={nodeCapability}
        executor={writeExecutor}
        target={target}
      />,
    );
    expect(screen.getByText("22 ms")).toBeInTheDocument();
  });

  it("does not attach evidence from an arbitrary target when the target is null", async () => {
    mockedUseConsoleWorkspace.mockReturnValue(
      workspaceWithEvidence(
        [capabilityEvidence("call-other-target", nodeCapability.name, 18, target)],
        null,
        null,
      ),
    );
    mockedUseCapabilityPlayground.mockReturnValue(
      controller({
        phase: "result",
        acknowledged: true,
        result: callResult(),
      }),
    );
    render(
      <CapabilityPlayground capability={nodeCapability} executor={null} target={null} />,
    );

    await userEvent.click(screen.getByRole("tab", { name: "Try capability" }));

    expect(screen.queryByText("18 ms")).not.toBeInTheDocument();
    expect(screen.getByText(/Result receipt unavailable/)).toBeInTheDocument();
  });

  it("invalidates a receipt through disconnect and reconnect", async () => {
    let activeController = controller({ acknowledged: true });
    mockedUseCapabilityPlayground.mockImplementation(() => activeController);
    const view = renderPlayground();
    await submitNodeCall();

    activeController = controller({
      phase: "result",
      acknowledged: true,
      result: callResult(),
    });
    mockedUseCapabilityPlayground.mockReturnValue(activeController);
    mockedUseConsoleWorkspace.mockReturnValue(
      workspaceWithEvidence([capabilityEvidence("call-connected", nodeCapability.name, 24)]),
    );
    view.rerender(
      <CapabilityPlayground
        capability={nodeCapability}
        executor={writeExecutor}
        target={target}
      />,
    );
    expect(screen.getByText("Completed")).toBeInTheDocument();

    const reconnectedExecutor = {} as ConsoleWriteExecutor;
    mockedUseConsoleWorkspace.mockReturnValue(
      workspaceWithEvidence([], "http://workflow-reconnected.example/rpc", reconnectedExecutor),
    );
    view.rerender(
      <CapabilityPlayground
        capability={nodeCapability}
        executor={reconnectedExecutor}
        target="http://workflow-reconnected.example/rpc"
      />,
    );
    expect(screen.queryByText("Completed")).not.toBeInTheDocument();
    expect(screen.getByText(/Result receipt unavailable/)).toBeInTheDocument();
  });
});
