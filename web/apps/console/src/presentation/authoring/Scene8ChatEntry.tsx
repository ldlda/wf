import { Button } from "../../components/ui/button.js";
import { Textarea } from "../../components/ui/textarea.js";
import { AuthoringConversation } from "./AuthoringConversation.js";
import {
  canSubmitScene8Entry,
  type Scene8EntryAction,
  type Scene8EntryState,
} from "./scene8-entry-state.js";
import { PREPARED_COMPOSER_HELP, usePreparedComposerSubmit } from "./usePreparedComposerSubmit.js";

type Scene8ChatEntryProps = {
  readonly state: Scene8EntryState;
  readonly dispatch: (action: Scene8EntryAction) => void;
};

/** Deterministic agent-request surface; submission reveals prepared data locally. */
export const Scene8ChatEntry = ({ state, dispatch }: Scene8ChatEntryProps) => {
  const submitted = state.phase === "submitted";
  const canSubmit = canSubmitScene8Entry(state);
  const { submit, handleKeyDown } = usePreparedComposerSubmit(
    canSubmit,
    () => dispatch({ type: "submit" }),
  );

  return (
    <section
      className="agent-handoff-scene__entry"
      aria-label="authoring chat entry"
      data-entry-phase={state.phase}
    >
      <div className="agent-handoff-scene__intro">
        <span>Agent handoff</span>
        <h1>What should the workflow author prepare?</h1>
        <p>Ask the external agent to inspect the available sources and capabilities before it authors the workflow.</p>
      </div>
      <form className="agent-handoff-scene__composer" onSubmit={submit}>
        <label className="agent-handoff-scene__composer-label" htmlFor="scene8-authoring-request">
          Authoring request
        </label>
        <Textarea
          id="scene8-authoring-request"
          value={state.draft}
          disabled={submitted}
          onChange={(event) => dispatch({ type: "draft_changed", draft: event.target.value })}
          onKeyDown={handleKeyDown}
          aria-describedby="scene8-authoring-request-help"
        />
        <div className="agent-handoff-scene__composer-actions">
          <Button type="submit" disabled={!canSubmit}>
            Send
          </Button>
        </div>
        <p id="scene8-authoring-request-help" className="agent-handoff-scene__composer-help">
          {PREPARED_COMPOSER_HELP}
        </p>
      </form>
      {submitted ? (
        <div className="agent-handoff-scene__entry-thread">
          <AuthoringConversation
            throughPhase="discover"
            activePhase="discover"
            surface="stage"
            scrollMode="start"
            requestOverride={state.request}
          />
        </div>
      ) : null}
    </section>
  );
};
