## Instruction Profile: debug

Use the supplied skills under `.agent/skills/` plus public `wf` commands. This
profile is for product UX diagnosis, so keep working through public discovery
longer than you would in a normal benchmark run.

Do not read repository examples, tests, source, prior trials, or prior stores
unless you are genuinely blocked. "Genuinely blocked" means all of these are
true:

- You tried the relevant `wf --help` or subcommand `--help`.
- You tried `wf schema` or the specific `wf schema <name>` form when the issue
  is about document shape.
- You tried validation or inspection commands such as `wf draft validate`,
  `wf draft compile`, `wf deploy validate`, `wf cap inspect`, or bounded
  `wf run trace` when those commands apply.
- You recorded the exact failing command, error text, and what you expected.
- You cannot proceed with public commands, supplied skills, challenge files, and
  validation output alone.

If you escalate beyond public surfaces after being genuinely blocked, report it
honestly in the `read` flags and explain why. Never read or copy adjacent trial
answers, prior result files, prior stores, or complete ready-made solution plans
for the same challenge.

In the final `challenge_report`, include a `ux_issues_found` list. Use an empty
list if there were no issues. Each issue should be concrete and evidence-backed:

```yaml
ux_issues_found:
  - command: "wf draft add-step ..."
    issue: "Assumed --name existed; command requires --step."
    evidence: "CLI returned: No such option --name"
    workaround: "Used --step render"
    suggested_fix: "Mention --step in help/example"
```

Log command typos, wrong assumptions, missing aliases, confusing help text,
schema/document-shape confusion, validation errors that were hard to repair,
and any point where you considered reading implementation code because public
surfaces were insufficient. A successful final run should still report the
issues and failed attempts that happened along the way.
