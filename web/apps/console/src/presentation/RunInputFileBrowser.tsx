import { useState } from "react";
import { preparedInputFixture } from "./run-input-fixtures.js";

export type RunInputFileBrowserProps = {
  readonly selectedDocuments: ReadonlyArray<string>;
  readonly boardPath: string;
};

export const RunInputFileBrowser = ({
  selectedDocuments,
  boardPath,
}: RunInputFileBrowserProps) => {
  const [selectedPath, setSelectedPath] = useState(selectedDocuments[0] ?? "");
  const visibleSelectedPath = selectedDocuments.includes(selectedPath)
    ? selectedPath
    : selectedDocuments[0] ?? "";
  const fixture = preparedInputFixture(visibleSelectedPath);

  return (
    <section className="run-input-file-browser" aria-label="workflow input files">
      <header className="run-input-file-browser__header">
        <h3>docs/</h3>
        <span>{selectedDocuments.length} selected by run input</span>
      </header>
      <div className="run-input-file-browser__body">
        <ul className="run-input-file-browser__list" aria-label="included in prepared run">
          {selectedDocuments.map((path) => (
            <li className="run-input-file-browser__file" data-file-path={path} key={path}>
              <button
                type="button"
                data-selected={path === visibleSelectedPath}
                aria-pressed={path === visibleSelectedPath}
                onClick={() => setSelectedPath(path)}
              >
                <span className="run-input-file-browser__icon" aria-hidden="true">md</span>
                <code>{path}</code>
                {path === visibleSelectedPath ? (
                  <span className="run-input-file-browser__marker">selected</span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
        <article className="run-input-file-browser__preview" role="region" aria-label="prepared fixture preview">
          <header>
            <code>{fixture?.name ?? visibleSelectedPath}</code>
            <span>Fixture preview · not execution evidence</span>
          </header>
          {fixture ? <pre>{fixture.markdown}</pre> : <p>Preview unavailable for this selected input.</p>}
        </article>
      </div>
      <div className="run-input-file-browser__destination" role="group" aria-label="workflow output">
        <span>declared output destination</span>
        <code>{boardPath}</code>
      </div>
    </section>
  );
};
