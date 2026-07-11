import type { ReactNode } from "react";

export type ConceptIconName =
  | "planner"
  | "tool"
  | "platform"
  | "think"
  | "toolCall"
  | "observe"
  | "done"
  | "design"
  | "save"
  | "connect"
  | "run"
  | "inspect";

type ConceptIconProps = {
  readonly name: ConceptIconName;
  readonly label: string;
};

const iconPathFor = (name: ConceptIconName): string => {
  if (name === "planner") return "M7 11c0-3 2-5 5-5s5 2 5 5-2 5-5 5-5-2-5-5Zm5-8v3m0 10v5M4 11H1m22 0h-3M6 4l2 2m10-2-2 2M6 18l2-2m10 2-2-2";
  if (name === "tool") return "M5 19h14M7 17V7l5-3 5 3v10M9 10h6M9 14h6";
  if (name === "platform") return "M4 7h16v10H4zM8 17v3m8-3v3M7 20h10M8 10h8m-8 3h5";
  if (name === "think") return "M8 15h8a4 4 0 0 0 0-8H9a5 5 0 0 0-1 10v3l3-3";
  if (name === "toolCall") return "M6 7h12M6 12h8M6 17h12M18 12l3 3-3 3";
  if (name === "observe") return "M2 12s4-6 10-6 10 6 10 6-4 6-10 6S2 12 2 12Zm10 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z";
  if (name === "done") return "M4 12l5 5L20 6";
  if (name === "design") return "M4 20l4-1 11-11-3-3L5 16l-1 4Zm10-14 3 3";
  if (name === "save") return "M5 4h12l2 2v14H5zM8 4v6h8V4M8 20v-6h8v6";
  if (name === "connect") return "M7 7h4v4H7zM13 13h4v4h-4zM11 9h3a3 3 0 0 1 3 3v1";
  if (name === "run") return "M7 5v14l12-7z";
  return "M3 11h18M5 5h14v14H5zM9 15h6";
};

export const ConceptIcon = ({ name, label }: ConceptIconProps) => (
  <svg className="concept-icon" role="img" aria-label={label} viewBox="0 0 24 24">
    <path d={iconPathFor(name)} />
  </svg>
);

type ConceptNodeProps = {
  readonly title: string;
  readonly subtitle?: string;
  readonly icon: ConceptIconName;
  readonly emphasis?: "normal" | "primary" | "muted";
  readonly children?: ReactNode;
};

export const ConceptNode = ({
  title,
  subtitle,
  icon,
  emphasis = "normal",
  children,
}: ConceptNodeProps) => (
  <article className="concept-node" role="group" aria-label={title} data-concept-emphasis={emphasis}>
    <ConceptIcon name={icon} label={`${title} icon`} />
    <div className="concept-node__copy">
      <strong>{title}</strong>
      {subtitle && <span>{subtitle}</span>}
      {children && <div className="concept-node__meta">{children}</div>}
    </div>
  </article>
);

type ConceptRailProps = {
  readonly label: string;
  readonly children: ReactNode;
  readonly className?: string | undefined;
};

export const ConceptRail = ({ label, children, className }: ConceptRailProps) => (
  <div className={["concept-rail", className].filter(Boolean).join(" ")} role="group" aria-label={label}>
    {children}
  </div>
);
