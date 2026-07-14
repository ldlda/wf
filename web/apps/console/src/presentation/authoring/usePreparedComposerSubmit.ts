import type { FormEvent, KeyboardEvent } from "react";

type PreparedComposerSubmitHandlers = {
  readonly submit: (event?: FormEvent<HTMLFormElement>) => void;
  readonly handleKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
};

export const PREPARED_COMPOSER_HELP =
  "Shift+Enter adds a new line. Responses are prepared; the final run request may use the configured workflow target.";

/** Shares the prepared-replay composer keyboard and form submission contract. */
export const usePreparedComposerSubmit = (
  canSubmit: boolean,
  onSubmit: () => void,
): PreparedComposerSubmitHandlers => {
  const submit = (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    if (canSubmit) onSubmit();
  };
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return { submit, handleKeyDown };
};
