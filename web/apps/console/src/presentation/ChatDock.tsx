type ChatDockProps = {
  readonly openChat: () => void;
};

export const ChatDock = ({ openChat }: ChatDockProps) => (
  <button
    type="button"
    className="chat-dock"
    aria-label="open agent chat"
    onClick={openChat}
  >
    <span className="chat-dock__icon">💬</span>
    <span className="chat-dock__label">Chat</span>
  </button>
);
