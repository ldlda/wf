export type FigureNodeKind =
  | "actor"
  | "operation"
  | "artifact"
  | "runtime"
  | "boundary"
  | "evidence";

export type FigureLayout =
  | { readonly kind: "layered" }
  | { readonly kind: "flow" }
  | {
      readonly kind: "explicit";
      readonly positions: Readonly<Record<string, { readonly x: number; readonly y: number }>>;
    };

export type FigureNodeDefinition = {
  readonly id: string;
  readonly label: string;
  readonly summary: string;
  readonly kind: FigureNodeKind;
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
