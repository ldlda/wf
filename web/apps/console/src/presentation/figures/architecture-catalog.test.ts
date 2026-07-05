import { describe, expect, it } from "vitest";
import { resolveFigureFocus } from "./focus.js";
import { architectureCatalog } from "./architecture-catalog.js";

describe("architectureCatalog", () => {
  it("contains the conceptual architecture overview", () => {
    const root = resolveFigureFocus(architectureCatalog, []).figure;
    expect(root.nodes.map((node) => node.label)).toEqual([
      "Client operations",
      "Application lifecycle",
      "Runtime & providers",
      "NodeUse",
    ]);
  });

  it("supports recursive runtime and provider expansion", () => {
    expect(resolveFigureFocus(architectureCatalog, ["runtime-providers"]).figure.id)
      .toBe("runtime-provider-detail");
    expect(resolveFigureFocus(
      architectureCatalog,
      ["runtime-providers", "configured-providers"],
    ).figure.id).toBe("configured-provider-detail");
  });

  it("gives every factual node an evidence pointer", () => {
    for (const figure of architectureCatalog.figures) {
      for (const node of figure.nodes) {
        if (node.kind === "boundary") continue;
        expect(node.evidencePointer, `${figure.id}/${node.id}`).toBeTruthy();
      }
    }
  });
});
