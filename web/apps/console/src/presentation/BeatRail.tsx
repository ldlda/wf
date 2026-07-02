import { presentationBeats, type BeatId } from "./beats.js";

type BeatRailProps = {
  readonly activeBeat: BeatId;
  readonly jump: (beat: BeatId) => void;
};

export const BeatRail = ({ activeBeat, jump }: BeatRailProps) => (
  <nav className="beat-rail" aria-label="presentation beat rail">
    {presentationBeats.map((beat) => (
      <button
        key={beat.id}
        type="button"
        data-active={beat.id === activeBeat}
        onClick={() => jump(beat.id)}
      >
        <span>{beat.lifecycleStep}</span>
        <small>{beat.title}</small>
      </button>
    ))}
  </nav>
);
