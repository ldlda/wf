import { join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  checkWorkflowContract,
  writeWorkflowContract,
} from "./workflow-contract-generator.js";

const packageRoot = fileURLToPath(new URL("..", import.meta.url));
const repositoryRoot = fileURLToPath(new URL("../../../..", import.meta.url));
const manifestPath = join(repositoryRoot, "contracts", "workflow-api.manifest.json");
const outputPath = join(packageRoot, "src", "generated", "workflow-contract.ts");

const mode = process.argv[2];
if (mode === "write") {
  await writeWorkflowContract(manifestPath, outputPath);
} else if (mode === "check") {
  await checkWorkflowContract(manifestPath, outputPath);
} else {
  throw new Error("usage: workflow-contract <write|check>");
}
