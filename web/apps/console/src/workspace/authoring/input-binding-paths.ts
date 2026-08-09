import type { InputPath, LocalInputPath } from "../domain/draft-workspace-models.js";
import { formatTOMLPath } from "../schema-form/schema-paths.js";

/** Display a local target without exposing its transport-only root marker. */
export const displayLocalInputPath = (value: LocalInputPath): string =>
  typeof value === "string" ? value : formatTOMLPath(value.parts);

/** Display a graph source path while retaining its input/state/context root. */
export const displayGraphInputPath = (value: InputPath): string =>
  typeof value === "string" ? value : formatTOMLPath([value.root, ...value.parts]);
