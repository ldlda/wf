export type FigureNodeKind =
  | "actor"
  | "operation"
  | "artifact"
  | "runtime"
  | "boundary"
  | "evidence"
  | "decision"
  | "terminal"
  | "provider"
  | "lane"
  | "loop";

export type FigureNodeShape =
  | "card"
  | "diamond"
  | "terminal"
  | "boundary"
  | "receipt"
  | "sequence"
  | "loop"
  | "merge";

export type FigureNodeIcon =
  | "users"
  | "terminal"
  | "network"
  | "server"
  | "workflow"
  | "database"
  | "layers"
  | "branch"
  | "repeat"
  | "pause"
  | "stop"
  | "plug"
  | "trace"
  | "code"
  | "lane";

export type FigureNodeDetail = {
  readonly label: string;
  readonly value: string;
};

export type FigureNodeEvidence = {
  readonly label: string;
  readonly title: string;
  readonly body: string;
  readonly facts?: readonly FigureNodeDetail[];
  readonly codePointer?: string;
};

export type FigureLayoutKind =
  | "layered"
  | "flow"
  | "spine"
  | "fan-in"
  | "hub"
  | "loop"
  | "lanes"
  | "explicit";

export type FigureLayout =
  | { readonly kind: Exclude<FigureLayoutKind, "explicit"> }
  | {
      readonly kind: "explicit";
      readonly positions: Readonly<Record<string, { readonly x: number; readonly y: number }>>;
    };

export type FigureNodeDefinition = {
  readonly id: string;
  readonly label: string;
  readonly summary: string;
  readonly kind: FigureNodeKind;
  readonly shape?: FigureNodeShape;
  readonly icon?: FigureNodeIcon;
  readonly details?: readonly FigureNodeDetail[];
  readonly evidence?: FigureNodeEvidence;
  readonly evidencePointer?: string;
  readonly childFigureId?: string;
};

export type FigureEdgeDefinition = {
  readonly id: string;
  readonly from: string;
  readonly to: string;
  readonly label?: string;
};

export type FigureDefinition = {
  readonly id: string;
  readonly title: string;
  readonly layout: FigureLayout;
  readonly nodes: readonly FigureNodeDefinition[];
  readonly edges: readonly FigureEdgeDefinition[];
};

export type FigureCatalogDefinition = {
  readonly rootFigureId: string;
  readonly figures: readonly FigureDefinition[];
};
