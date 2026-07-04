import { discussionBranches, findScene, type MainSceneId } from "./storyboard.js";

type DiscussionIndexProps = {
  readonly onSelect: (branchId: string) => void;
};

type BranchGroup = {
  readonly parentSceneId: MainSceneId;
  readonly sceneTitle: string;
  readonly branches: typeof discussionBranches[number][];
};

const groupByParentScene = (): readonly BranchGroup[] => {
  const groups = new Map<string, BranchGroup>();
  for (const branch of discussionBranches) {
    let group = groups.get(branch.parentSceneId);
    if (!group) {
      const scene = findScene(branch.parentSceneId);
      group = {
        parentSceneId: branch.parentSceneId,
        sceneTitle: scene?.title ?? branch.parentSceneId,
        branches: [],
      };
      groups.set(branch.parentSceneId, group);
    }
    group.branches.push(branch);
  }
  return Array.from(groups.values());
};

export const DiscussionIndex = ({ onSelect }: DiscussionIndexProps) => {
  const groups = groupByParentScene();
  return (
    <div className="discussion-index" role="dialog" aria-label="discussion topics">
      <h2>Discussion Topics</h2>
      {groups.map((group) => (
        <section key={group.parentSceneId}>
          <h3>{group.sceneTitle}</h3>
          <ul>
            {group.branches.map((branch) => (
              <li key={branch.id}>
                <button type="button" onClick={() => onSelect(branch.id)}>
                  {branch.title}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
};
