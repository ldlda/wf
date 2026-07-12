export type RunInputFileBrowserProps = {
  readonly selectedDocuments: ReadonlyArray<string>;
  readonly boardPath: string;
};

export const RunInputFileBrowser = ({
  selectedDocuments,
  boardPath,
}: RunInputFileBrowserProps) => (
  <section className="run-input-file-browser" role="region" aria-label="workflow input files">
    <header className="run-input-file-browser__header">
      <h3>docs/</h3>
      <span>included in prepared run</span>
    </header>
    <ul className="run-input-file-browser__list" aria-label="included in prepared run">
      {selectedDocuments.map((path) => (
        <li className="run-input-file-browser__file" data-file-path={path} key={path}>
          <span className="run-input-file-browser__icon" aria-hidden="true">file</span>
          <code>{path}</code>
          <span className="run-input-file-browser__marker">included in prepared run</span>
        </li>
      ))}
    </ul>
    <div className="run-input-file-browser__destination" role="group" aria-label="workflow output">
      <span>workflow output</span>
      <code>{boardPath}</code>
    </div>
  </section>
);
