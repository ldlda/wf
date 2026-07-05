import { describe, expect, it } from "vitest";
import { popFigureFocus, pushFigureFocus, resolveFigureFocus } from "./focus.js";
import { validCatalog } from "./test-fixtures.js";

describe("figure focus", () => {
  it("resolves a two-level Focus Path with breadcrumbs", () => {
    const focus = resolveFigureFocus(validCatalog, ["runtime", "providers"]);
    expect(focus.figure.id).toBe("provider-detail");
    expect(focus.path).toEqual(["runtime", "providers"]);
    expect(focus.breadcrumbs.map((item) => item.label)).toEqual([
      "Architecture",
      "Runtime & providers",
      "Configured providers",
    ]);
  });

  it("fails closed to the root for an invalid Focus Path", () => {
    expect(resolveFigureFocus(validCatalog, ["missing"]).path).toEqual([]);
    expect(resolveFigureFocus(validCatalog, ["runtime", "missing"]).figure.id)
      .toBe("architecture-overview");
  });

  it("pushes only expandable nodes and pops one level", () => {
    const root = resolveFigureFocus(validCatalog, []);
    const runtime = pushFigureFocus(validCatalog, root, "runtime");
    expect(runtime.path).toEqual(["runtime"]);
    expect(pushFigureFocus(validCatalog, runtime, "leaf")).toEqual(runtime);
    expect(popFigureFocus(validCatalog, runtime).path).toEqual([]);
  });
});
