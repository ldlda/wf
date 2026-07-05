import type { FigureBreadcrumb } from "./focus.js";

type FigureBreadcrumbsProps = {
  readonly breadcrumbs: readonly FigureBreadcrumb[];
  readonly onNavigate: (path: readonly string[]) => void;
};

export const FigureBreadcrumbs = ({
  breadcrumbs,
  onNavigate,
}: FigureBreadcrumbsProps) => (
  <nav className="figure-breadcrumbs" aria-label="Figure navigation">
    {breadcrumbs.map((crumb, index) => {
      const isLast = index === breadcrumbs.length - 1;
      return (
        <button
          key={`${crumb.path.join("/")}-${index}`}
          type="button"
          className="figure-breadcrumbs__crumb"
          aria-current={isLast ? "page" : undefined}
          onClick={() => onNavigate(crumb.path)}
        >
          {crumb.label}
        </button>
      );
    })}
  </nav>
);
