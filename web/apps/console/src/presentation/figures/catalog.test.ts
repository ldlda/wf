import { describe, expect, it } from "vitest";
import { defineFigureCatalog } from "./catalog.js";
import {
  cyclicCatalog,
  disconnectedCyclicCatalog,
  duplicateFigureCatalog,
  duplicateNodeCatalog,
  explicitFigureMissingPosition,
  unknownChildCatalog,
  unknownEdgeCatalog,
  unknownRootCatalog,
  validCatalog,
} from "./test-fixtures.js";

describe("defineFigureCatalog", () => {
  it("accepts a valid recursive catalog", () => {
    expect(() => defineFigureCatalog(validCatalog)).not.toThrow();
  });

  it.each([
    ["duplicate figure", duplicateFigureCatalog, "duplicate_figure"],
    ["duplicate node", duplicateNodeCatalog, "duplicate_node"],
    ["unknown root figure", unknownRootCatalog, "unknown_root_figure"],
    ["unknown edge endpoint", unknownEdgeCatalog, "unknown_edge_endpoint"],
    ["unknown child figure", unknownChildCatalog, "unknown_child_figure"],
    ["recursive child cycle", cyclicCatalog, "child_cycle"],
    ["disconnected child cycle", disconnectedCyclicCatalog, "child_cycle"],
  ])("rejects %s", (_label, catalog, code) => {
    expect(() => defineFigureCatalog(catalog)).toThrow(code);
  });

  it("rejects explicit layouts missing a node position", () => {
    expect(() => defineFigureCatalog({
      rootFigureId: explicitFigureMissingPosition.id,
      figures: [explicitFigureMissingPosition],
    })).toThrow("missing_explicit_position:explicit-missing:runtime");
  });
});
