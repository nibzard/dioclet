# Succession experiment

Date: 2026-11-12.

Provider: `live-decisions`. Split: `holdout`.

Each result is a simulation. Human clarity, tension, and enjoyment require human playtests.

| Variant | Finished | Incomplete | Draws | Median rounds | Choice-rich turns | Avoidable treasure walks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 3 | 0 | 3 | 43 | 280 | 2 |

## Assessment

Inspect the strategy and gate tables in `summary.json`. A strategy disappearing, repeated claim cancellation, or excessive farming needs a causal explanation and a new opponent probe.

Alternative-play estimates are in `alternatives.jsonl`. They use sampled compatible hidden worlds and paired future random streams. Small differences are not evidence of a better rule.

Screening and holdout seeds are separate. Do not tune a rule after reading its holdout result and then reuse that result as independent validation.

Live requests: 852. Estimated cost: $0.309556.
