import type { ReactNode } from "react";

type StageCaptionProps = {
  readonly eyebrow: string;
  readonly title: string;
  readonly children: ReactNode;
};

export const StageCaption = ({ eyebrow, title, children }: StageCaptionProps) => (
  <section className="stage-caption" aria-label={title}>
    <p className="stage-caption__eyebrow">{eyebrow}</p>
    <h1>{title}</h1>
    <div>{children}</div>
  </section>
);
