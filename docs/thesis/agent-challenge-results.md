## Audited Agent Challenge Campaign

The primary campaign contains 36 audited trials: 27 passes, 8 invalid samples, and 1 failure.

The campaign crosses two challenges, two hosted models, three instruction profiles (`none`, `skills`, and `all`), and three repetitions per cell. The checked cohort snapshot records report hashes, prompt hashes, the repository commit, automatic metrics, and manual-audit outcomes; local raw report files are verified against those hashes when present.

Because repository snapshots and one prompt rule changed between waves, this is longitudinal engineering evidence, not a controlled model comparison.

Selection rule: The latest three completed, manually audited trials per challenge, model, and instruction profile as of 2026-06-30.

| Challenge / model / profile | Pass | Invalid | Fail |
| --- | ---: | ---: | ---: |
| browser / deepseek / none | 2 | 1 | 0 |
| browser / deepseek / skills | 3 | 0 | 0 |
| browser / deepseek / all | 2 | 1 | 0 |
| browser / mimo / none | 2 | 0 | 1 |
| browser / mimo / skills | 2 | 1 | 0 |
| browser / mimo / all | 3 | 0 | 0 |
| report / deepseek / none | 3 | 0 | 0 |
| report / deepseek / skills | 2 | 1 | 0 |
| report / deepseek / all | 1 | 2 | 0 |
| report / mimo / none | 1 | 2 | 0 |
| report / mimo / skills | 3 | 0 | 0 |
| report / mimo / all | 3 | 0 | 0 |

: Audited outcomes by challenge, model, and instruction profile. {#tbl:agent-challenge-outcomes}

A manual `pass` requires both successful product-path evidence and an acceptable audit trail. `Invalid` means the sample cannot support the clean benchmark claim, commonly because the agent read repository or example material outside its supplied workspace. `Fail` means the challenge contract itself was not established.

![Audited outcomes by evaluation cell.](figures/agent-challenge-audited-outcomes-by-cell.svg){#fig:agent-challenge-audited-outcomes-by-cell width=95%}

[@fig:agent-challenge-audited-outcomes-by-cell] reports all three repetitions rather than hiding invalid samples. The profile labels are descriptive; this campaign does not isolate instruction-profile effects.

![Automatic task outcomes compared with manual outcomes.](figures/agent-challenge-automatic-vs-manual-outcomes.svg){#fig:agent-challenge-automatic-vs-manual-outcomes width=75%}

[@fig:agent-challenge-automatic-vs-manual-outcomes] shows why the manual layer matters. Seven automatically successful trials were invalid as clean evidence, while three automatically failed reports were accepted after their saved run evidence and report artifacts were manually audited.

![Audited outcomes across the three longitudinal waves.](figures/agent-challenge-longitudinal-outcomes.svg){#fig:agent-challenge-longitudinal-outcomes width=75%}

The waves in [@fig:agent-challenge-longitudinal-outcomes] are not an improvement curve: product commits, prompt wording, and enforcement changed. They preserve the chronology needed to study those changes.

![Duration and recorded token totals grouped by challenge, instruction profile, model, and wave.](figures/agent-challenge-duration-and-tokens.svg){#fig:agent-challenge-duration-and-tokens width=95%}

[@fig:agent-challenge-duration-and-tokens] separates each challenge and metric into its own panel. Circle and square markers redundantly identify the models without relying on color. Wall-clock duration includes hosted-service latency, and OpenCode token totals include cache-read accounting, so neither axis is a normalized model-efficiency metric.

### Campaign Limitations

- The three waves span repository snapshots; they are longitudinal engineering evidence, not a controlled model comparison.
- The base prompt changed before wave 3 to require the challenge report inline.
- The models were free hosted OpenCode endpoints, so service load and latency were not controlled.
