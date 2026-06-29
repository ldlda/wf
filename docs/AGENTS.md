# docs management

its the age old problem. code changes, but i dont bother fixing docs. its been here before me, before chatgpt, and after chatgpt.

## lets improve this

check [README.md](README.md) as pointers. they point to live evolving docs.

a good docs pass, searching for kw, changing the documents that have them. cool. dedicated docs pass after a Thing done. great.

ACTIVE (planned, running) implementation plans and specs sit in their folders.
`superpowers/plans/` is only for executable handoff plans that are active or in
progress.

DONE docs go straight to [`historical/`](historical/). Prefer keeping the OG
path shape under `docs/historical/`, for example
`docs/superpowers/plans/foo.md` -> `docs/historical/superpowers/plans/foo.md`.
You can edit the top of the file to state that its historical, but just being
in the folder is enough.

superpowers skills say to tick those boxes; do tick those boxes.

stale docs, even at docs/, go to historical/ or git rm.

user facing docs need updates too. User facing docs include [/skills](../skills/)

## roadmap plans?

in superpowers plans there are now suddenly some big plans, like roadmaps, with multiple slices that turn into dedicated implementation plans.

Those need linking, active or done. Since any done plans go to `historical/**`,
live docs must point to `historical/**` when they cite old slice plans.

`current_roadmap.md` is the live roadmap. Roadmap-shaped plan files are
historical context unless they are actively being used to drive this exact next
slice.

## superpowers specs? (generalize to docs/)

Any specs files in that folder represent the current state of the code. Ok
anything at docs/ do. Hence, if a Thing replaces another, something has to go to
the historical/.

as i said before. readme points to LIVE, Evolving docs. cant have stale/superseded stuff in here.

Same stuff for skills!

If a spec is still a useful design contract, update it in place. If it is only
"how we got here", move it to `historical/**`. Do not leave two docs claiming
different current behavior.

## Important rules

When moving or retiring docs, search for the old filename and update live links:
`docs/README.md`, `docs/current_roadmap.md`, skills, and nearby architecture
docs are the usual places.

If code has a partial implementation and docs mention the limitation, add a
short comment or docstring at the code seam too. Future agents see code before
they see old plans.

# docs formatting

## (caution: unstable) markdown formatting

use `pnpx markdownlint-cli(2) --fix '(glob the md)'`
<!-- ill need to setup cli2 -->

Note that this will mess things up, if you dont already follow the strict rules of markdownlint

use `git restore docs/historical` afterwards

### pitfall

all about indenting.

````md
1. you have a list, ordered or not?

this line ends the list, because it has no indents.

```bash
## even this code block has to be indented
```

2. otherwise this will be "fixed" and renumbered to 1.

<!-- in case -->
9. we have come far
   - notice the indents
<!-- a blank line here is standard -->
10. after this point
    - the indent increases
    - since the list marker is longer
````

### why not prettier? it does much more

when prettier supports compact table i'll switch to it
