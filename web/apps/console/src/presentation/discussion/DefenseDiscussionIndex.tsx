import type { FC } from "react";
import { BadgeHelp, Boxes, ChartNoAxesCombined, FileCode2, Map, PlaySquare, Rocket } from "lucide-react";
import { projectDefenseDiscussionGroups, type CanonicalDiscussionBranchDefinition, type DefenseDiscussionTopicId } from "./defense-discussion-index.js";

const topicIcons = {
  contribution: BadgeHelp,
  positioning: Map,
  runtime: Boxes,
  authoring: FileCode2,
  demo: PlaySquare,
  evaluation: ChartNoAxesCombined,
  production: Rocket,
} as const satisfies Record<DefenseDiscussionTopicId, typeof BadgeHelp>;

export const DefenseDiscussionIndex: FC<{
  readonly discussionBranches: readonly CanonicalDiscussionBranchDefinition[];
  readonly openDiscussion: (branchId: string) => void;
}> = ({
  discussionBranches,
  openDiscussion,
}) => {
  const groups = projectDefenseDiscussionGroups(discussionBranches);

  return (
    <nav className="defense-discussion-index" aria-label="defense discussion index">
      {groups.map((group) => {
      const Icon = topicIcons[group.id];
      return (
        <section className="defense-discussion-index__group" key={group.id}>
          <h2 className="defense-discussion-index__heading">
            <Icon aria-hidden="true" focusable="false" />
            <span>{group.label}</span>
          </h2>
          <ul className="defense-discussion-index__list">
            {group.branches.map((branch) => (
              <li key={branch.id}>
                <button type="button" onClick={() => openDiscussion(branch.id)}>
                  {branch.title}
                </button>
              </li>
            ))}
          </ul>
        </section>
      );
      })}
    </nav>
  );
};
