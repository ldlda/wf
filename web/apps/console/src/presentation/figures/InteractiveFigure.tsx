import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { ReactFlow, ReactFlowProvider, Handle, Position, useReactFlow, type Node, type Edge, type NodeTypes } from "@xyflow/react";
import {
  Boxes,
  Cable,
  CircleStop,
  Database,
  FileSearch,
  GitBranch,
  Layers3,
  Network,
  PauseCircle,
  Plug,
  Repeat,
  Server,
  Terminal,
  Users,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import "@xyflow/react/dist/style.css";
import type {
  FigureCatalogDefinition,
  FigureLayoutKind,
  FigureNodeDefinition,
  FigureNodeIcon,
  FigureNodeKind,
  FigureNodeShape,
} from "./model.js";
import { layoutFigure, type FigureLayoutSize } from "./layout.js";
import { nextFigureNodeId, type FigureDirection } from "./navigation.js";
import {
  popFigureFocus,
  pushFigureFocus,
  resolveFigureFocus,
} from "./focus.js";
import { FigureBreadcrumbs } from "./FigureBreadcrumbs.js";
import { FigureNodeView } from "./FigureNodeView.js";
import "./interactive-figure.css";

type InteractiveFigureProps = {
  readonly catalog: FigureCatalogDefinition;
  readonly focusPath: readonly string[];
  readonly activeNodeId: string | null;
  readonly onFocusPathChange: (path: readonly string[]) => void;
  readonly motionDisabled: boolean;
  readonly size?: "standard" | "wide" | "stage";
};

type FigureNodeData = {
  readonly nodeId: string;
  readonly label: string;
  readonly summary: string;
  readonly kind: FigureNodeKind;
  readonly shape: FigureNodeShape;
  readonly icon: FigureNodeIcon | null;
  readonly details: FigureNodeDefinition["details"];
  readonly evidence: FigureNodeDefinition["evidence"];
  readonly orientation: "horizontal" | "vertical";
  readonly isActive: boolean;
  readonly isFocused: boolean;
  readonly isSelected: boolean;
  readonly isExpandable: boolean;
  readonly onActivate: (nodeId: string) => void;
  readonly onExpand: (nodeId: string) => void;
};

const iconByName: Record<FigureNodeIcon, LucideIcon> = {
  users: Users,
  terminal: Terminal,
  network: Network,
  server: Server,
  workflow: Workflow,
  database: Database,
  layers: Layers3,
  branch: GitBranch,
  repeat: Repeat,
  pause: PauseCircle,
  stop: CircleStop,
  plug: Plug,
  trace: FileSearch,
  code: FileSearch,
  lane: Cable,
};

const iconByKind: Record<FigureNodeKind, FigureNodeIcon> = {
  actor: "users",
  operation: "workflow",
  artifact: "database",
  runtime: "server",
  boundary: "network",
  evidence: "trace",
  decision: "branch",
  terminal: "stop",
  provider: "plug",
  lane: "lane",
  loop: "repeat",
};

const shapeByKind: Record<FigureNodeKind, FigureNodeShape> = {
  actor: "card",
  operation: "card",
  artifact: "receipt",
  runtime: "card",
  boundary: "boundary",
  evidence: "receipt",
  decision: "diamond",
  terminal: "terminal",
  provider: "boundary",
  lane: "sequence",
  loop: "loop",
};

const horizontalLayouts = new Set<FigureLayoutKind>(["flow", "fan-in", "lanes", "explicit"]);

const FigureFlowNode = ({ data }: { data: FigureNodeData }) => {
  const expandable = data.isExpandable;
  const hasEvidence = data.evidence !== undefined || data.details !== undefined;
  const accessibleName = expandable
    ? `${data.label}, expand`
    : hasEvidence
      ? `${data.label}, inspect details`
      : data.label;
  const targetPosition = data.orientation === "horizontal" ? Position.Left : Position.Top;
  const sourcePosition = data.orientation === "horizontal" ? Position.Right : Position.Bottom;
  const Icon = iconByName[data.icon ?? iconByKind[data.kind]];

  return (
    <>
      <Handle type="target" position={targetPosition} id="target" />
      <button
        type="button"
        className="figure-node"
        data-figure-node-kind={data.kind}
        data-figure-shape={data.shape}
        data-active={data.isActive}
        data-selected={data.isSelected}
        data-expandable={expandable}
        data-testid={`figure-node-${data.nodeId}`}
        aria-label={accessibleName}
        tabIndex={data.isFocused ? 0 : -1}
        onClick={() => {
          data.onActivate(data.nodeId);
          if (expandable) data.onExpand(data.nodeId);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && expandable) {
            event.preventDefault();
            data.onExpand(data.nodeId);
          }
        }}
      >
        <span className="figure-node__header">
          <span className="figure-node__kind">{data.kind}</span>
          <Icon className="figure-node__icon" size={18} strokeWidth={1.8} aria-hidden="true" />
        </span>
        <strong className="figure-node__label">{data.label}</strong>
        <span className="figure-node__summary">{data.summary}</span>
        {data.details && data.details.length > 0 && (
          <dl className="figure-node__details">
            {data.details.slice(0, 2).map((detail) => (
              <div key={`${detail.label}-${detail.value}`}>
                <dt>{detail.label}</dt>
                <dd><code>{detail.value}</code></dd>
              </div>
            ))}
          </dl>
        )}
        {expandable && <span className="figure-node__expand-affordance" aria-hidden="true">&#9656;</span>}
        {data.isActive && <span className="figure-node__current-marker">Current</span>}
      </button>
      <Handle type="source" position={sourcePosition} id="source" />
    </>
  );
};

const nodeTypes: NodeTypes = {
  figure: FigureFlowNode,
};

const FitViewOnLayoutChange = ({ layoutKey }: { layoutKey: string }) => {
  const { fitView } = useReactFlow();
  useEffect(() => {
    void fitView({ padding: 0.15, duration: 0 });
    // React Flow can measure before the breadcrumb row and stage grid settle.
    // Fit again on the next frame to align edges with the final node boxes.
    const frame = window.requestAnimationFrame(() => {
      void fitView({ padding: 0.15, duration: 0 });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [fitView, layoutKey]);
  return null;
};

const InteractiveFigureInner = ({
  catalog,
  focusPath,
  activeNodeId,
  onFocusPathChange,
  motionDisabled,
  size = "standard",
}: InteractiveFigureProps) => {
  const focus = useMemo(
    () => resolveFigureFocus(catalog, focusPath),
    [catalog, focusPath],
  );
  const layoutSize = size === "stage" && focus.path.length === 0 ? "wide" : size;
  const layout = useMemo(() => layoutFigure(focus.figure, layoutSize), [focus.figure, layoutSize]);
  const containerRef = useRef<HTMLDivElement>(null);
  const initialFocusedNodeId = activeNodeId ?? focus.figure.nodes[0]?.id ?? "";
  const [focusedNodeId, setFocusedNodeId] = useState(initialFocusedNodeId);
  const focusedNodeIdRef = useRef(initialFocusedNodeId);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const graphInspectionEnabled = size === "stage";

  const fallbackFocusedNodeId = activeNodeId ?? focus.figure.nodes[0]?.id ?? "";
  useEffect(() => {
    if (!fallbackFocusedNodeId) return;
    if (activeNodeId || !layout.nodes.some((node) => node.id === focusedNodeIdRef.current)) {
      focusedNodeIdRef.current = fallbackFocusedNodeId;
      setFocusedNodeId(fallbackFocusedNodeId);
    }
  }, [activeNodeId, fallbackFocusedNodeId, layout.nodes]);

  const handleExpand = useCallback(
    (nodeId: string) => {
      const next = pushFigureFocus(catalog, focus, nodeId);
      if (next.path.length > focus.path.length) {
        setSelectedNodeId(null);
        onFocusPathChange(next.path);
      }
    },
    [catalog, focus, onFocusPathChange],
  );

  const handleBreadcrumbNavigate = useCallback(
    (path: readonly string[]) => {
      setSelectedNodeId(null);
      onFocusPathChange(path);
    },
    [onFocusPathChange],
  );

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      const key = event.key;
      if (key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        if (selectedNodeId !== null) {
          setSelectedNodeId(null);
          return;
        }
        const popped = popFigureFocus(catalog, focus);
        if (popped.path.length < focus.path.length) {
          onFocusPathChange(popped.path);
        }
        return;
      }

      const directionMap: Record<string, FigureDirection> = {
        ArrowUp: "ArrowUp",
        ArrowDown: "ArrowDown",
        ArrowLeft: "ArrowLeft",
        ArrowRight: "ArrowRight",
      };

      const direction = directionMap[key];
      if (direction) {
        event.preventDefault();
        event.stopPropagation();
        const nextId = nextFigureNodeId(layout, focusedNodeIdRef.current, direction);
        focusedNodeIdRef.current = nextId;
        setFocusedNodeId(nextId);
        const nextNode = containerRef.current?.querySelector(
          `[data-testid="figure-node-${nextId}"]`,
        );
        if (nextNode instanceof HTMLElement) nextNode.focus();
      }
    },
    [catalog, focus, layout, onFocusPathChange, selectedNodeId],
  );

  const handleActivateNode = useCallback((nodeId: string) => {
    focusedNodeIdRef.current = nodeId;
    setFocusedNodeId(nodeId);
    const node = layout.nodes.find((candidate) => candidate.id === nodeId);
    setSelectedNodeId(node?.evidence || node?.details ? nodeId : null);
  }, [layout.nodes]);

  const selectedNode = selectedNodeId === null
    ? undefined
    : layout.nodes.find((node) => node.id === selectedNodeId);

  const rfNodes: Node[] = useMemo(
    () =>
      layout.nodes.map((node) => ({
        id: node.id,
        type: "figure",
        position: node.position,
        data: {
          nodeId: node.id,
          label: node.label,
          summary: node.summary,
          kind: node.kind,
          shape: node.shape ?? shapeByKind[node.kind],
          icon: node.icon ?? null,
          details: node.details,
          evidence: node.evidence,
          orientation: horizontalLayouts.has(layout.definition.layout.kind) ? "horizontal" : "vertical",
          isActive: node.id === activeNodeId,
          isFocused: node.id === focusedNodeId,
          isSelected: node.id === selectedNodeId,
          isExpandable: node.childFigureId !== undefined,
          onActivate: handleActivateNode,
          onExpand: handleExpand,
        },
      })),
    [layout.definition.layout.kind, layout.nodes, activeNodeId, focusedNodeId, selectedNodeId, handleActivateNode, handleExpand],
  );

  const rfEdges: Edge[] = useMemo(
    () =>
      layout.edges.map((edge) => ({
        id: edge.id,
        source: edge.from,
        target: edge.to,
        label: edge.label,
        // Authored maps use orthogonal routing so their deliberate rows and
        // branches stay readable; Dagre layouts retain softer default curves.
        type: layout.definition.layout.kind === "explicit" ? "smoothstep" : "default",
      })),
    [layout.definition.layout.kind, layout.edges],
  );

  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      const data = node.data as FigureNodeData;
      focusedNodeIdRef.current = data.nodeId;
      if (data.isExpandable) handleExpand(data.nodeId);
    },
    [handleExpand],
  );

  return (
    <div
      className="interactive-figure"
      role="group"
      aria-label={focus.figure.title}
      data-motion={motionDisabled ? "disabled" : "enabled"}
      data-figure-id={focus.figure.id}
      data-figure-size={size}
      data-figure-layout={focus.figure.layout.kind}
      data-figure-focus-level={focus.path.length}
      data-pan-zoom={graphInspectionEnabled ? "enabled" : "disabled"}
      data-selected-node={selectedNode?.id ?? ""}
      onKeyDown={handleKeyDown}
    >
      <FigureBreadcrumbs
        breadcrumbs={focus.breadcrumbs}
        onNavigate={handleBreadcrumbNavigate}
      />
      <div className="interactive-figure__workspace">
        {/* React Flow must measure nodes in its unscaled coordinate space. Keep
            this canvas responsive instead of reintroducing a CSS scale wrapper. */}
        <div className="interactive-figure__canvas" ref={containerRef}>
          <ReactFlow
            nodes={rfNodes}
            edges={rfEdges}
            nodeTypes={nodeTypes}
            fitView
            proOptions={{ hideAttribution: true }}
            nodesDraggable={false}
            nodesConnectable={false}
            nodesFocusable={false}
            edgesFocusable={false}
            elementsSelectable={false}
            minZoom={0.55}
            maxZoom={2.2}
            panOnDrag={graphInspectionEnabled}
            zoomOnScroll={graphInspectionEnabled}
            zoomOnPinch={graphInspectionEnabled}
            zoomOnDoubleClick={graphInspectionEnabled}
            preventScrolling={graphInspectionEnabled}
            onNodeClick={handleNodeClick}
          >
            <FitViewOnLayoutChange layoutKey={focus.figure.id} />
          </ReactFlow>
        </div>
        {selectedNode?.evidence && (
          <aside className="figure-evidence" role="region" aria-label={`${selectedNode.label} evidence`}>
            <div className="figure-evidence__header">
              <span className="figure-evidence__label">{selectedNode.evidence.label}</span>
              <button
                type="button"
                className="figure-evidence__close"
                onClick={() => setSelectedNodeId(null)}
                aria-label="Close figure evidence"
              >
                Close
              </button>
            </div>
            <h3>{selectedNode.evidence.title}</h3>
            <p>{selectedNode.evidence.body}</p>
            {selectedNode.evidence.facts && selectedNode.evidence.facts.length > 0 && (
              <dl className="figure-evidence__facts">
                {selectedNode.evidence.facts.map((fact) => (
                  <div key={`${fact.label}-${fact.value}`}>
                    <dt>{fact.label}</dt>
                    <dd>{fact.value}</dd>
                  </div>
                ))}
              </dl>
            )}
            {selectedNode.evidence.codePointer && (
              <code className="figure-evidence__pointer">{selectedNode.evidence.codePointer}</code>
            )}
          </aside>
        )}
      </div>
    </div>
  );
};

export const InteractiveFigure = (props: InteractiveFigureProps) => (
  <ReactFlowProvider>
    <InteractiveFigureInner {...props} />
  </ReactFlowProvider>
);
