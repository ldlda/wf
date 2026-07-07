import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { ReactFlow, ReactFlowProvider, Handle, Position, useReactFlow, type Node, type Edge, type NodeTypes } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { FigureCatalogDefinition, FigureNodeKind } from "./model.js";
import { layoutFigure, NODE_WIDTH, NODE_HEIGHT, type PositionedFigure } from "./layout.js";
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
  readonly size?: "standard" | "wide";
};

type FigureNodeData = {
  readonly nodeId: string;
  readonly label: string;
  readonly summary: string;
  readonly kind: FigureNodeKind;
  readonly orientation: "horizontal" | "vertical";
  readonly isActive: boolean;
  readonly isFocused: boolean;
  readonly isExpandable: boolean;
  readonly onActivate: (nodeId: string) => void;
  readonly onExpand: (nodeId: string) => void;
};

const FigureFlowNode = ({ data }: { data: FigureNodeData }) => {
  const expandable = data.isExpandable;
  const accessibleName = expandable ? `${data.label}, expand` : data.label;
  const targetPosition = data.orientation === "horizontal" ? Position.Left : Position.Top;
  const sourcePosition = data.orientation === "horizontal" ? Position.Right : Position.Bottom;

  return (
    <>
      <Handle type="target" position={targetPosition} id="target" />
      <button
        type="button"
        className="figure-node"
        data-figure-node-kind={data.kind}
        data-active={data.isActive}
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
        <span className="figure-node__kind">{data.kind}</span>
        <strong className="figure-node__label">{data.label}</strong>
        <span className="figure-node__summary">{data.summary}</span>
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
  const layout = useMemo(() => layoutFigure(focus.figure), [focus.figure]);
  const containerRef = useRef<HTMLDivElement>(null);
  const initialFocusedNodeId = activeNodeId ?? focus.figure.nodes[0]?.id ?? "";
  const [focusedNodeId, setFocusedNodeId] = useState(initialFocusedNodeId);
  const focusedNodeIdRef = useRef(initialFocusedNodeId);

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
        onFocusPathChange(next.path);
      }
    },
    [catalog, focus, onFocusPathChange],
  );

  const handleBreadcrumbNavigate = useCallback(
    (path: readonly string[]) => {
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
    [catalog, focus, layout, onFocusPathChange],
  );

  const handleActivateNode = useCallback((nodeId: string) => {
    focusedNodeIdRef.current = nodeId;
    setFocusedNodeId(nodeId);
  }, []);

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
          orientation: layout.definition.layout.kind === "flow" ? "horizontal" : "vertical",
          isActive: node.id === activeNodeId,
          isFocused: node.id === focusedNodeId,
          isExpandable: node.childFigureId !== undefined,
          onActivate: handleActivateNode,
          onExpand: handleExpand,
        },
      })),
    [layout.definition.layout.kind, layout.nodes, activeNodeId, focusedNodeId, handleActivateNode, handleExpand],
  );

  const rfEdges: Edge[] = useMemo(
    () =>
      layout.edges.map((edge) => ({
        id: edge.id,
        source: edge.from,
        target: edge.to,
        label: edge.label,
        type: "default",
      })),
    [layout.edges],
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
      onKeyDown={handleKeyDown}
    >
      <FigureBreadcrumbs
        breadcrumbs={focus.breadcrumbs}
        onNavigate={handleBreadcrumbNavigate}
      />
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
          panOnDrag={false}
          zoomOnScroll={false}
          zoomOnPinch={false}
          zoomOnDoubleClick={false}
          preventScrolling={false}
          onNodeClick={handleNodeClick}
        >
          <FitViewOnLayoutChange layoutKey={focus.figure.id} />
        </ReactFlow>
      </div>
    </div>
  );
};

export const InteractiveFigure = (props: InteractiveFigureProps) => (
  <ReactFlowProvider>
    <InteractiveFigureInner {...props} />
  </ReactFlowProvider>
);
