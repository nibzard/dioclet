# Succession experiment

Date: 2026-11-13.

Provider: `live-decisions`. Split: `screen`.

Each result is a simulation. Human clarity, tension, and enjoyment require human playtests.

| Variant | Finished | Incomplete | Draws | Median rounds | Choice-rich turns | Avoidable treasure walks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 4 | 0 | 0 | 29.0 | 375 | 0 |

## Assessment

Inspect the strategy and gate tables in `summary.json`. A strategy disappearing, repeated claim cancellation, or excessive farming needs a causal explanation and a new opponent probe.

Alternative-play estimates are in `alternatives.jsonl`. They use sampled compatible hidden worlds and paired future random streams. Small differences are not evidence of a better rule.

Screening and holdout seeds are separate. Do not tune a rule after reading its holdout result and then reuse that result as independent validation.

Live requests: 1652. Estimated cost: $0.601559.
