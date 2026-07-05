import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { ReactFlow, ReactFlowProvider, useReactFlow, type Node, type Edge, type NodeTypes } from "@xyflow/react";
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
};

type FigureNodeData = {
  readonly nodeId: string;
  readonly label: string;
  readonly summary: string;
  readonly kind: FigureNodeKind;
  readonly isActive: boolean;
  readonly isExpandable: boolean;
  readonly onActivate: (nodeId: string) => void;
  readonly onExpand: (nodeId: string) => void;
};

const FigureFlowNode = ({ data }: { data: FigureNodeData }) => {
  const expandable = data.isExpandable;
  const accessibleName = expandable ? `${data.label}, expand` : data.label;

  return (
    <button
      type="button"
      className="figure-node"
      data-figure-node-kind={data.kind}
      data-active={data.isActive}
      data-expandable={expandable}
      data-testid={`figure-node-${data.nodeId}`}
      aria-label={accessibleName}
      tabIndex={-1}
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
      {expandable && <span className="figure-node__expand-affance" aria-hidden="true">&#9656;</span>}
      {data.isActive && <span className="figure-node__current-marker">Current</span>}
    </button>
  );
};

const nodeTypes: NodeTypes = {
  figure: FigureFlowNode,
};

const FitViewOnLayoutChange = ({ layoutVersion }: { layoutVersion: number }) => {
  const { fitView } = useReactFlow();
  useEffect(() => {
    void fitView({ padding: 0.15, duration: 0 });
  }, [fitView, layoutVersion]);
  return null;
};

const InteractiveFigureInner = ({
  catalog,
  focusPath,
  activeNodeId,
  onFocusPathChange,
  motionDisabled,
}: InteractiveFigureProps) => {
  const focus = resolveFigureFocus(catalog, focusPath);
  const layout = layoutFigure(focus.figure);
  const [focusedNodeId, setFocusedNodeId] = useState<string>(
    activeNodeId ?? focus.figure.nodes[0]?.id ?? "",
  );
  const containerRef = useRef<HTMLDivElement>(null);
  const [layoutVersion, setLayoutVersion] = useState(0);

  useEffect(() => {
    if (activeNodeId) setFocusedNodeId(activeNodeId);
  }, [activeNodeId]);

  useEffect(() => {
    const firstNode = focus.figure.nodes[0];
    if (firstNode) setFocusedNodeId(firstNode.id);
    setLayoutVersion((v) => v + 1);
  }, [focus.figure.id]);

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
        const nextId = nextFigureNodeId(layout, focusedNodeId, direction);
        setFocusedNodeId(nextId);
        const nextNode = containerRef.current?.querySelector(
          `[data-testid="figure-node-${nextId}"]`,
        );
        if (nextNode instanceof HTMLElement) nextNode.focus();
      }
    },
    [catalog, focus, focusedNodeId, layout, onFocusPathChange],
  );

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
          isActive: node.id === activeNodeId,
          isExpandable: node.childFigureId !== undefined,
          onActivate: setFocusedNodeId,
          onExpand: handleExpand,
        },
      })),
    [layout.nodes, activeNodeId, handleExpand],
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
      setFocusedNodeId(data.nodeId);
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
          elementsSelectable={false}
          panOnDrag={false}
          zoomOnScroll={false}
          zoomOnPinch={false}
          zoomOnDoubleClick={false}
          preventScrolling={false}
          onNodeClick={handleNodeClick}
        >
          <FitViewOnLayoutChange layoutVersion={layoutVersion} />
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
