#!/usr/bin/env python3
"""Bounded sequential proposal-agent runner for the V0.8 programme.

Reads ``experiments/v08-programme.json`` and runs up to N sequential
cycles. Each cycle:

1. verifies the frozen source hashes (engine, evaluator, policies,
   tests, board geometry, active rules);
2. builds one prompt from the programme text, the incumbent rules,
   prior cycle evidence, public turn examples, and a strict proposal
   schema;
3. requests exactly one proposal from a tool-free agent
   (``claude -p``, or a clearly labeled scripted smoke agent);
4. validates the proposal against the finite change space and applies
   it to a copied candidate rules file;
5. runs paired screening suites and fresh holdout suites for the
   incumbent and the candidate through ``tools/succession_experiments``;
6. applies the configured promotion checks and either promotes the
   candidate or keeps the incumbent, recording every rejection.

The runner never mutates the active rules file, never deploys, never
commits, and never replaces a failed model call with a scripted
proposal. Every stop carries an explicit reason in ``stop.json``.

Promotion-check interpretation (recorded in every decision):
``maximum_draw_increase``, ``maximum_median_round_increase``,
``minimum_claims_challenged_fraction``, and
``minimum_winning_profiles`` always bind on both suites.
``minimum_draw_improvement`` binds while the incumbent draws at least
5% of finished games. ``minimum_cancellation_reduction`` binds while
the incumbent averages more than one canceled claim per finished
game, and measures the reduction on that per-game volume — the
denial-loop size — not on the share of claims canceled. A high
cancel share with a high challenged fraction means challenges still
trade; a large per-game volume means the loop repeats. A candidate is
promoted only when every binding check passes on screening AND
holdout.

Interpretation note: the first draft measured the cancellation
reduction on the canceled-share ratio. The contest-cost screening
comparison (results/v08-contestcost-001) showed that reading
contradicts the paired counterplay floor: a candidate can keep 99%
of claims challenged, cut cancellations per game by three quarters,
and still fail. The revision to per-game volume was made before any
model proposal cycle ran, and this note records the change.

Counterplay veto (added 2026-11-08 after the AR1 review): the
mechanical checks above promoted the known-bad fee-2 variant twice,
because bots keep healthy metrics while no responder can legally
afford a contest. Every cycle now also runs the replay-verified
contest audit (tools/contest_audit.py) on each suite and applies the
frozen availability floors in DEFAULT_COUNTERPLAY_VETO before a
candidate may be promoted. See results/autoresearch-ar1-001.
"""

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import engine
from tools import contest_audit
from tools import succession_experiments

CLAUDE = Path(os.environ.get("CLAUDE_BIN", "/home/agent/.local/bin/claude"))
PROGRAMME_MD = REPO / "programme.md"

# Frozen for the whole comparison run: gameplay code, the evaluator,
# the policies the bots use, the checks that gate them, and the two
# rules files that define the comparison space.
FROZEN_SOURCES = (
    "succession.py", "engine.py", "board.py", "policies.py",
    "candidate_actions.py", "decisions_policy.py", "ai_driver.py",
    "tools/succession_experiments.py",
    "tests/test_succession.py", "tests/test_succession_decisions.py",
    "web/succession-engine.js", "web/succession-bots.js",
    "rules_v073_sixblocks_cardo.json", "rules_v08_succession.json",
)

DRAW_IMPROVEMENT_REGIME = 0.05   # incumbent draw fraction that binds the improvement check
CANCELLATION_REGIME = 1.0        # incumbent canceled claims per finished game that binds the reduction check
HOLDOUT_STRIDE = 1000            # fresh holdout seeds per cycle never overlap

SCRIPTED_PROPOSALS = (
    {"rule_path": "succession.contest_cost", "value": 1,
     "hypothesis": "Scripted smoke proposal, not model output. Free opposition lets any "
                   "rival cancel any claim, so claims never survive three responses.",
     "prediction": "A mandatory fee of one Prestige should cut draws and cancellations "
                   "sharply while keeping challenges affordable.",
     "refutation_evidence": "Draws or cancellations stay near the incumbent level, or "
                            "challenged-claim fraction falls below the counterplay floor."},
    {"rule_path": "glory.cap", "value": 4,
     "hypothesis": "Scripted smoke proposal, not model output. A cap of three may force "
                   "wasted rewards and idle guard turns before a claim.",
     "prediction": "Cap four should reduce wasted Prestige without changing win profiles "
                   "much.",
     "refutation_evidence": "Median rounds rise past the guard, or one profile takes "
                            "nearly every win."},
    {"rule_path": "succession.challenge_bonus", "value": 1,
     "hypothesis": "Scripted smoke proposal, not model output. A +2 boost for one Prestige "
                   "may dominate the unboosted challenge.",
     "prediction": "Reducing the boost to +1 should make boosted and plain challenges "
                   "closer substitutes.",
     "refutation_evidence": "Challenged-claim fraction falls below the counterplay floor, "
                            "or draws increase."},
)


def now_utc():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    return {name: sha256_file(REPO / name) for name in FROZEN_SOURCES}


def value_allowed(value, allowed):
    """Type-strict membership: JSON true must not match 1, null only null."""
    return any(candidate == value and isinstance(candidate, bool) == isinstance(value, bool)
               for candidate in allowed)


def apply_change(rules, path, value):
    """Return a copied rules dict with one dotted path set to a value."""
    updated = copy.deepcopy(rules)
    node = updated
    keys = path.split(".")
    for key in keys[:-1]:
        if not isinstance(node, dict) or key not in node:
            raise KeyError(path)
        node = node[key]
    if keys[-1] not in node:
        raise KeyError(path)
    node[keys[-1]] = copy.deepcopy(value)
    return updated


def get_path(rules, path):
    node = rules
    for key in path.split("."):
        if not isinstance(node, dict) or key not in node:
            raise KeyError(path)
        node = node[key]
    return node


def suite_metrics(summary):
    base = summary["variants"]["base"]
    totals = base["resource_and_claim_totals"]
    claims = totals.get("claims_made", 0)
    cancelled = totals.get("claims_cancelled", 0)
    finished = base["finished_games"] or 1
    return {"finished_games": base["finished_games"],
            "incomplete_games": base["incomplete_games"],
            "draw_fraction": base["draw_fraction"],
            "median_rounds": base["median_rounds"],
            "wins_by_strategy": base["wins_by_strategy"],
            "claims_made": claims, "claims_cancelled": cancelled,
            "challenged_claim_fraction": base["challenged_claim_fraction"],
            "cancellation_rate": (cancelled / claims) if claims else 0.0,
            "cancellations_per_game": cancelled / finished}


def promotion_checks(incumbent, candidate, promo):
    """Every binding check must pass; the caller applies them per suite."""
    checks = []

    def add(name, ok, detail):
        checks.append({"check": name, "passed": bool(ok), "detail": detail})

    draw_i = incumbent["draw_fraction"] or 0.0
    draw_c = candidate["draw_fraction"] or 0.0
    add("draws_not_materially_worse",
        draw_c <= draw_i + promo["maximum_draw_increase"],
        f"candidate {draw_c:.3f} vs incumbent {draw_i:.3f}, allowed increase {promo['maximum_draw_increase']}")
    rounds_i, rounds_c = incumbent["median_rounds"], candidate["median_rounds"]
    add("rounds_not_longer",
        rounds_i is not None and rounds_c is not None and
        rounds_c <= rounds_i + promo["maximum_median_round_increase"],
        f"candidate {rounds_c} vs incumbent {rounds_i} median rounds, allowed increase {promo['maximum_median_round_increase']}")
    challenged = candidate["challenged_claim_fraction"] or 0.0
    add("counterplay_exists",
        challenged >= promo["minimum_claims_challenged_fraction"],
        f"candidate challenged {challenged:.3f} of claims, floor {promo['minimum_claims_challenged_fraction']}")
    winners = sorted(name for name, wins in candidate["wins_by_strategy"].items() if wins)
    add("profile_diversity", len(winners) >= promo["minimum_winning_profiles"],
        f"winning profiles {winners}, minimum {promo['minimum_winning_profiles']}")
    if draw_i >= DRAW_IMPROVEMENT_REGIME:
        add("draw_improvement",
            draw_c <= draw_i - promo["minimum_draw_improvement"],
            f"incumbent draws {draw_i:.3f} at or above {DRAW_IMPROVEMENT_REGIME}; candidate {draw_c:.3f} must improve by {promo['minimum_draw_improvement']}")
    if incumbent["cancellations_per_game"] > CANCELLATION_REGIME:
        target = incumbent["cancellations_per_game"] * (1 - promo["minimum_cancellation_reduction"])
        add("cancellation_reduction",
            candidate["cancellations_per_game"] <= target,
            f"incumbent cancels {incumbent['cancellations_per_game']:.1f} claims per game; "
            f"candidate {candidate['cancellations_per_game']:.1f} must reach {target:.1f}")
    return checks


# Counterplay-availability veto, added after the AR1 review on
# 2026-11-08. The mechanical checks above promoted the known-bad
# fee-2 variant in results/v08-programme-001 cycle 2 and again in the
# AR1 fee-2 diagnostic (results/autoresearch-ar1-001/diagnostic):
# bot metrics stay healthy while no responder can legally afford a
# contest. These floors were preregistered and frozen in the AR1 run
# before any candidate cycle; a programme config may override them
# through a "counterplay_veto" object with the same keys, but it
# cannot remove the veto itself.
DEFAULT_COUNTERPLAY_VETO = {
    "minimum_contest_offered_rate": 0.50,
    "minimum_claims_with_contest_option": 0.70,
    "minimum_can_afford_rate": 0.60,
    "maximum_claims_crowned_without_legal_contest": 0.25,
    "minimum_baseline_afford_at_candidate_fee": 0.60,
}


def counterplay_veto(candidate_audit, baseline_audit, veto=None, contest_fee=None):
    """Legal contest-availability veto; every check must pass.

    ``candidate_audit`` is a contest-audit summary produced by
    tools/contest_audit.py (offline suites, replay-verified) or
    tools/live_contest_audit.py (live suites). ``baseline_audit`` is
    the incumbent reference audit; its afford_at_fee table answers
    which fee levels the incumbent's actual response purses could
    pay, which is what caught fee 2.
    """
    floors = {**DEFAULT_COUNTERPLAY_VETO, **(veto or {})}
    fee = contest_fee if contest_fee is not None else candidate_audit.get("contest_fee")
    checks = []

    def add(name, ok, detail):
        checks.append({"check": name, "passed": bool(ok), "detail": detail})

    offered = candidate_audit.get("contest_offered_rate")
    add("contest_offered_floor",
        offered is not None and offered >= floors["minimum_contest_offered_rate"],
        f"contests offered on {offered} of response turns, floor {floors['minimum_contest_offered_rate']}")
    claims_option = candidate_audit.get("claims_with_contest_option")
    add("claims_with_contest_option_floor",
        claims_option is not None and claims_option >= floors["minimum_claims_with_contest_option"],
        f"{claims_option} of claims ever had a legal contest, floor {floors['minimum_claims_with_contest_option']}")
    afford = candidate_audit.get("can_afford_fee_rate")
    add("responder_afford_floor",
        afford is not None and afford >= floors["minimum_can_afford_rate"],
        f"responders able to pay the fee on {afford} of response turns, floor {floors['minimum_can_afford_rate']}")
    crowned = candidate_audit.get("claims_crowned_without_legal_contest")
    add("no_poverty_coronation",
        crowned is not None and crowned <= floors["maximum_claims_crowned_without_legal_contest"],
        f"{crowned} of claims crowned with no legal contest ever offered, ceiling "
        f"{floors['maximum_claims_crowned_without_legal_contest']}")
    if baseline_audit and fee is not None:
        base_afford = baseline_audit.get("afford_at_fee", {}).get(str(fee))
        add("baseline_purse_affords_candidate_fee",
            base_afford is not None and base_afford >= floors["minimum_baseline_afford_at_candidate_fee"],
            f"{base_afford} of incumbent response purses could pay fee {fee}, "
            f"floor {floors['minimum_baseline_afford_at_candidate_fee']}")
    return checks


def audit_suite(suite):
    """Attach a replay-verified contest audit to one suite record."""
    suite["contest_audit"] = contest_audit.audit_suite(Path(suite["out"]) / "base")
    return suite


def turn_examples(choices_path, limit=10):
    """A small public-evidence sample: rich choices and claim responses."""
    if not Path(choices_path).exists():
        return []
    lines = []
    with open(choices_path, encoding="utf-8") as handle:
        for line in handle:
            turn = json.loads(line)
            interesting = turn.get("choice_rich") or turn.get("chosen_counterclaim") or turn.get("pending_claim")
            if interesting:
                lines.append(turn)
            if len(lines) >= limit:
                break
    return lines


def build_prompt(cfg, cycle, total_cycles, incumbent_rules, incumbent_path,
                 metrics_history, examples):
    allowed = cfg["allowed_changes"]
    changes = {path: {"allowed": values, "incumbent_value": get_path(incumbent_rules, path)}
               for path, values in sorted(allowed.items())}
    evidence = ""
    for record in metrics_history:
        evidence += (f"\n### Cycle {record['cycle']} ({record['agent']} agent, "
                     f"{'promoted' if record['promoted'] else 'kept incumbent'})\n"
                     f"Proposal: {record['proposal']['rule_path']} = {json.dumps(record['proposal']['value'])}.\n"
                     f"Hypothesis: {record['proposal']['hypothesis']}\n"
                     f"Decision: {record['reason']}\n")
        for label in ("screen", "holdout"):
            suite = record["metrics"].get(label)
            if suite:
                evidence += (f"- {label}: draws {suite['draw_fraction']:.3f}, median rounds "
                             f"{suite['median_rounds']}, claims {suite['claims_made']}, canceled "
                             f"{suite['claims_cancelled']}, challenged fraction "
                             f"{suite['challenged_claim_fraction']:.3f}, winners by profile "
                             f"{json.dumps(suite['wins_by_strategy'], sort_keys=True)}.\n")
    latest = metrics_history[-1].get("incumbent_metrics") if metrics_history else None
    incumbent_line = ""
    for label in ("screen", "holdout"):
        suite = (latest or {}).get(label)
        if suite:
            incumbent_line += (f"- {label}: {suite['finished_games']} finished games, draws "
                               f"{suite['draw_fraction']:.3f}, median rounds {suite['median_rounds']}, "
                               f"claims {suite['claims_made']}, canceled {suite['claims_cancelled']}, "
                               f"challenged fraction {suite['challenged_claim_fraction']:.3f}, "
                               f"wins by profile {json.dumps(suite['wins_by_strategy'], sort_keys=True)}.\n")
    example_text = "".join(json.dumps(example, sort_keys=True) + "\n" for example in examples)
    programme_text = PROGRAMME_MD.read_text(encoding="utf-8")
    schema = {
        "type": "object", "additionalProperties": False,
        "required": ["rule_path", "value", "hypothesis", "prediction", "refutation_evidence"],
        "properties": {
            "rule_path": {"type": "string", "enum": sorted(allowed)},
            "value": {"description": "One of the allowed values for rule_path, and different from the incumbent value."},
            "hypothesis": {"type": "string", "minLength": 20, "maxLength": 900},
            "prediction": {"type": "string", "minLength": 20, "maxLength": 900},
            "refutation_evidence": {"type": "string", "minLength": 20, "maxLength": 900},
        },
    }
    return f"""# Proposal request: cycle {cycle} of {total_cycles}

You are one fresh agent in a sequential research programme. Your only
task is to propose ONE rule change as JSON. You have no tools. The
trusted runner applies your proposal, runs the fixed experiments, and
decides promotion with frozen checks. Output ONLY a JSON object that
matches the schema at the end. No prose before or after the JSON.

{programme_text}

## Permitted change space (exact)

{json.dumps(changes, indent=2, sort_keys=True)}

Propose one path and one allowed value only. The value must differ
from the incumbent value. Everything else in the rules stays fixed.

## Incumbent measured evidence

Incumbent rules file: `{incumbent_path}` (hash below in the run log).

{incumbent_line or "- No suite has run yet; this is the first cycle. The free-challenge baseline is known to draw heavily and cancel nearly every claim.\n"}
## Earlier cycles

{evidence or "- This is the first cycle.\n"}
## Public turn examples (no hidden information)

```json
{example_text or "- No recorded turns yet.\n"}
```

## Incumbent rules (the object your path edits)

```json
{json.dumps(incumbent_rules, indent=2, sort_keys=True)}
```

## Output contract

```json
{json.dumps(schema, indent=2)}
```

Fields: `rule_path` (one permitted path), `value` (one allowed value
for that path, different from the incumbent value), `hypothesis` (the
causal mechanism), `prediction` (the measurable effect you expect),
`refutation_evidence` (what result would count against you).
Output only the JSON object.
""", schema


def call_claude(prompt, schema, budget_usd, timeout_seconds):
    """Run one tool-free proposal agent; return (proposal|None, record)."""
    command = [str(CLAUDE), "-p", "--tools", "", "--output-format", "json",
               "--max-budget-usd", str(budget_usd),
               "--json-schema", json.dumps(schema)]
    record = {"command": command[:-1] + ["<schema>"], "timeout_seconds": timeout_seconds,
              "max_budget_usd": budget_usd}
    try:
        completed = subprocess.run(command, input=prompt, capture_output=True,
                                   text=True, timeout=timeout_seconds, cwd=str(REPO))
    except subprocess.TimeoutExpired:
        record["error"] = "agent_timeout"
        return None, record
    except FileNotFoundError:
        record["error"] = "claude_binary_missing"
        return None, record
    record["returncode"] = completed.returncode
    record["stderr"] = completed.stderr[-2000:]
    if completed.returncode != 0:
        lowered = (completed.stderr + completed.stdout).lower()
        if "auth" in lowered or "credential" in lowered or "login" in lowered or "api key" in lowered:
            record["error"] = "authentication_failure"
        else:
            record["error"] = f"agent_exit_{completed.returncode}"
        return None, record
    try:
        envelope = json.loads(completed.stdout)
    except json.JSONDecodeError:
        record["error"] = "invalid_envelope_json"
        record["stdout"] = completed.stdout[-4000:]
        return None, record
    record["envelope"] = {key: envelope.get(key) for key in
                          ("type", "subtype", "is_error", "model", "duration_ms")}
    if envelope.get("is_error"):
        record["error"] = "agent_reported_error"
        record["stdout"] = completed.stdout[-4000:]
        return None, record
    result = envelope.get("result")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            record["error"] = "invalid_result_json"
            record["stdout"] = completed.stdout[-4000:]
            return None, record
    if not isinstance(result, dict):
        record["error"] = "result_not_an_object"
        return None, record
    return result, record


def validate_proposal(proposal, incumbent_rules, allowed):
    """Return None when valid, else a stop reason string."""
    required = {"rule_path", "value", "hypothesis", "prediction", "refutation_evidence"}
    if not isinstance(proposal, dict) or set(proposal) != required:
        return "invalid_output"
    for field in ("hypothesis", "prediction", "refutation_evidence"):
        if not isinstance(proposal[field], str) or not 20 <= len(proposal[field]) <= 900:
            return "invalid_output"
    path, value = proposal["rule_path"], proposal["value"]
    if path not in allowed:
        return "path_outside_permitted_space"
    if not value_allowed(value, allowed[path]):
        return "value_outside_permitted_space"
    try:
        current = get_path(incumbent_rules, path)
    except KeyError:
        return "path_missing_from_rules"
    if value == current and isinstance(value, bool) == isinstance(current, bool):
        return "no_op_proposal"
    return None


def change_key(rules, proposal):
    return (proposal["rule_path"], json.dumps(proposal["value"]),
            engine.rules_hash(rules))


def run_suite(label, rules_path, out_dir, games, seed_base, split, profiles):
    print(f"[suite] {label}: games={games} seeds={seed_base}+ split={split}", flush=True)
    started = time.time()
    summary = succession_experiments.evaluate_rules(
        rules_path, out_dir, games=games, seed_base=seed_base, split=split,
        profiles=tuple(profiles), audit_positions=2, rollouts=4,
        audit_turns=200, economy_grid=False, provider="mock")
    return {"label": label, "out": str(out_dir), "seed_base": seed_base,
            "games": games, "seconds": round(time.time() - started, 1),
            "exit_code": summary["exit_code"], "metrics": suite_metrics(summary),
            "rules_hash": summary["rules_hash"]}


def write_report(run_dir, cfg, cycles, incumbent, stopped, total_cycles):
    lines = [f"# V0.8 programme run: {run_dir.name}", "",
             f"Finished: {now_utc()}. Agent: `{cycles[0]['agent'] if cycles else 'none'}`.",
             f"Cycles recorded: {len(cycles)} of {total_cycles}.", ""]
    if cycles and cycles[0]["agent"] == "scripted":
        lines += ["**Smoke run.** The proposals are scripted constants. They are not",
                  "evidence that a model played, proposed, or reviewed anything.", ""]
    lines += ["| Cycle | Agent | Proposal | Decision | Reason |", "| --- | --- | --- | --- | --- |"]
    for record in cycles:
        proposal = record["proposal"]
        lines.append(f"| {record['cycle']} | {record['agent']} | "
                     f"`{proposal['rule_path']} = {json.dumps(proposal['value'])}` | "
                     f"{'promoted' if record['promoted'] else 'kept incumbent'} | {record['reason']} |")
    lines += ["", f"Final incumbent: `{incumbent['path']}`",
              f"Rules hash: `{incumbent['hash']}`", "",
              "Promotion checks are mechanical guards, not a fun score. Simulation",
              "screens mechanics and strategies; human playtests decide clarity,",
              "tension, and replay value (`playtest/protocol-v08.md`)."]
    if stopped:
        lines += ["", f"Stopped early: `{stopped['reason']}` (cycle {stopped['cycle']})."]
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="New, empty run directory")
    parser.add_argument("--programme", default=str(REPO / "experiments/v08-programme.json"))
    parser.add_argument("--cycles", type=int, help="Override the configured cycle count")
    parser.add_argument("--games", type=int, help="Override the configured suite size")
    parser.add_argument("--agent", choices=("claude", "scripted"), default="claude",
                        help="claude: tool-free proposal agents (real run). "
                             "scripted: fixed proposals, no model calls (smoke run)")
    args = parser.parse_args(argv)

    cfg = json.loads(Path(args.programme).read_text(encoding="utf-8"))
    total_cycles = args.cycles if args.cycles is not None else cfg["cycles"]
    games = args.games if args.games is not None else cfg["games_per_suite"]
    if total_cycles < 1 or total_cycles > 10:
        parser.error("--cycles must be within 1..10")
    if games < 1 or games > 768:
        parser.error("--games must be within 1..768")

    run_dir = Path(args.out)
    if run_dir.exists() and any(run_dir.iterdir()):
        parser.error("output directory is not empty; use a new directory for each run")
    (run_dir / "cycles").mkdir(parents=True)

    log_path = run_dir / "run-log.jsonl"

    def log(event):
        event["time"] = now_utc()
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")

    hashes = source_hashes()
    (run_dir / "source-hashes.json").write_text(json.dumps(hashes, indent=2, sort_keys=True))
    log({"event": "run_start", "agent": args.agent, "cycles": total_cycles, "games": games,
         "config": cfg, "source_hashes": hashes})

    incumbent_path = REPO / cfg["rules"]
    incumbent_rules = engine.load_rules(str(incumbent_path))
    incumbent = {"path": str(incumbent_path), "hash": engine.rules_hash(incumbent_rules),
                 "screen_suite": None, "origin": "configured-incumbent"}

    stopped = None
    history = []
    tested_changes = set()
    baseline_audit = None   # configured incumbent's screen audit; the
    # cross-fee affordability guard compares every candidate fee against
    # the response purses actually observed under this baseline.

    def stop(cycle, reason, detail=None):
        nonlocal stopped
        stopped = {"cycle": cycle, "reason": reason, "detail": detail}
        engine._atomic_write_json(str(run_dir / "stop.json"), stopped)
        log({"event": "stop", **stopped})

    cycle_no = 0
    while cycle_no < total_cycles and stopped is None:
        cycle_no += 1
        if source_hashes() != hashes:
            stop(cycle_no, "source_hashes_changed",
                 "frozen engine, evaluator, policy, test, or rules files changed mid-run")
            break
        cycle_dir = run_dir / "cycles" / f"{cycle_no:02d}"
        cycle_dir.mkdir()
        log({"event": "cycle_start", "cycle": cycle_no,
             "incumbent": incumbent["path"], "incumbent_hash": incumbent["hash"]})

        # 1. Proposal.
        examples = turn_examples(Path(incumbent["screen_suite"]["out"]) / "base" / "choices.jsonl") \
            if incumbent["screen_suite"] else []
        prompt, schema = build_prompt(cfg, cycle_no, total_cycles, incumbent_rules,
                                      incumbent["path"], history, examples)
        (cycle_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        if args.agent == "scripted":
            proposal = copy.deepcopy(SCRIPTED_PROPOSALS[(cycle_no - 1) % len(SCRIPTED_PROPOSALS)])
            record = {"agent": "scripted",
                      "note": "Scripted smoke proposal; no model was called."}
        else:
            proposal, record = call_claude(prompt, schema,
                                           cfg["agent_budget_usd_per_cycle"],
                                           cfg["agent_timeout_seconds"])
            if proposal is None:
                (cycle_dir / "agent-failure.json").write_text(
                    json.dumps(record, indent=2, default=str), encoding="utf-8")
                stop(cycle_no, record.get("error", "agent_failure"))
                break
        # 2. Validate the strict proposal shape, then apply to a copied candidate.
        problem = validate_proposal(proposal, incumbent_rules, cfg["allowed_changes"])
        if problem:
            (cycle_dir / "rejected-proposal.json").write_text(
                json.dumps(proposal, indent=2, sort_keys=True), encoding="utf-8")
            stop(cycle_no, problem, json.dumps(proposal, sort_keys=True))
            break
        key = change_key(incumbent_rules, proposal)
        if key in tested_changes:
            # Same change against the same incumbent repeats a finished,
            # deterministic comparison. Spend the cycle on nothing else.
            stop(cycle_no, "duplicate_proposal",
                 f"{proposal['rule_path']} = {json.dumps(proposal['value'])} was already tested against this incumbent")
            break
        tested_changes.add(key)
        proposal = {**proposal, "agent": args.agent, "agent_record": record}
        (cycle_dir / "proposal.json").write_text(
            json.dumps(proposal, indent=2, sort_keys=True), encoding="utf-8")
        log({"event": "proposal", "cycle": cycle_no, **{k: proposal.get(k) for k in
                                                        ("rule_path", "value", "agent")}})
        try:
            candidate_rules = apply_change(incumbent_rules,
                                           proposal["rule_path"], proposal["value"])
            engine.validate_rules(candidate_rules)
        except (KeyError, engine.EngineError) as err:
            stop(cycle_no, "invalid_rules", str(err))
            break
        candidate_path = cycle_dir / "candidate-rules.json"
        engine._atomic_write_json(str(candidate_path), candidate_rules)
        candidate_hash = engine.rules_hash(candidate_rules)
        log({"event": "candidate", "cycle": cycle_no, "path": str(candidate_path),
             "rules_hash": candidate_hash})

        # 3. Paired screening suites (same seeds; reuse a matching
        #    earlier suite instead of recomputing identical output).
        screen_seed = cfg["screen_seed_base"]
        if incumbent["screen_suite"] is None:
            incumbent["screen_suite"] = run_suite(
                "screen-incumbent", incumbent["path"], cycle_dir / "screen-incumbent",
                games, screen_seed, "screen", cfg["profiles"])
        else:
            reused = incumbent["screen_suite"]
            reused = {**reused, "label": "screen-incumbent", "reused_from": reused["out"]}
            incumbent["screen_suite"] = reused
            log({"event": "suite_reused", "cycle": cycle_no, **{k: reused[k] for k in
                                                                ("label", "reused_from", "rules_hash", "games", "seed_base")}})
        screen_candidate = run_suite("screen-candidate", str(candidate_path),
                                     cycle_dir / "screen-candidate", games,
                                     screen_seed, "screen", cfg["profiles"])
        for suite in (incumbent["screen_suite"], screen_candidate):
            if suite["exit_code"] != 0:
                stop(cycle_no, "incomplete_screen_suite", suite["label"])
        if stopped:
            break
        for suite in (incumbent["screen_suite"], screen_candidate):
            audit_suite(suite)
        if baseline_audit is None:
            baseline_audit = incumbent["screen_suite"]["contest_audit"]

        # 4. Fresh holdout seeds for every cycle; never tune on a seen holdout.
        holdout_seed = cfg["holdout_seed_base"] + (cycle_no - 1) * HOLDOUT_STRIDE
        holdout_incumbent = run_suite("holdout-incumbent", incumbent["path"],
                                      cycle_dir / "holdout-incumbent", games,
                                      holdout_seed, "holdout", cfg["profiles"])
        holdout_candidate = run_suite("holdout-candidate", str(candidate_path),
                                      cycle_dir / "holdout-candidate", games,
                                      holdout_seed, "holdout", cfg["profiles"])
        for suite in (holdout_incumbent, holdout_candidate):
            if suite["exit_code"] != 0:
                stop(cycle_no, "incomplete_holdout_suite", suite["label"])
        if stopped:
            break
        for suite in (holdout_incumbent, holdout_candidate):
            audit_suite(suite)
        if source_hashes() != hashes:
            stop(cycle_no, "source_hashes_changed", "verified after the suites")
            break

        # 5. Promotion checks on both suites: mechanical guards plus
        #    the counterplay-availability veto on the candidate's
        #    replay-verified audits.
        promo = cfg["promotion"]
        veto_cfg = cfg.get("counterplay_veto")
        candidate_fee = candidate_rules["succession"].get("contest_cost")
        screen_checks = promotion_checks(incumbent["screen_suite"]["metrics"],
                                         screen_candidate["metrics"], promo)
        holdout_checks = promotion_checks(holdout_incumbent["metrics"],
                                          holdout_candidate["metrics"], promo)
        screen_veto = counterplay_veto(screen_candidate["contest_audit"],
                                       baseline_audit, veto_cfg, candidate_fee)
        holdout_veto = counterplay_veto(holdout_candidate["contest_audit"],
                                        baseline_audit, veto_cfg, candidate_fee)
        evidence_ok = all(
            suite["metrics"]["finished_games"] == games and
            suite["metrics"]["incomplete_games"] == 0
            for suite in (incumbent["screen_suite"], screen_candidate,
                          holdout_incumbent, holdout_candidate)) and all(
                suite["contest_audit"]["games_replay_verified"] ==
                suite["contest_audit"]["games_total"]
                for suite in (incumbent["screen_suite"], screen_candidate,
                              holdout_incumbent, holdout_candidate))
        promoted = (evidence_ok and
                    all(c["passed"] for c in screen_checks + holdout_checks +
                        screen_veto + holdout_veto))
        failed_screen = [c for c in screen_checks + screen_veto if not c["passed"]]
        failed_holdout = [c for c in holdout_checks + holdout_veto if not c["passed"]]
        if not evidence_ok:
            reason = "insufficient_evidence"
        elif promoted:
            reason = "all binding promotion and counterplay checks passed on screen and holdout"
        else:
            names = sorted({c["check"] for c in failed_screen + failed_holdout})
            reason = (f"failed {len(failed_screen)} screen and {len(failed_holdout)} "
                      f"holdout binding check(s): {', '.join(names)} "
                      "(details in checks below)")
        decision = {"cycle": cycle_no, "agent": proposal["agent"], "proposal": proposal,
                    "promoted": promoted, "reason": reason,
                    "checks": {"screen": screen_checks + screen_veto,
                               "holdout": holdout_checks + holdout_veto},
                    "metrics": {"screen": screen_candidate["metrics"],
                                "holdout": holdout_candidate["metrics"],
                                "incumbent_screen": incumbent["screen_suite"]["metrics"],
                                "incumbent_holdout": holdout_incumbent["metrics"]},
                    "suites": {"screen_candidate": screen_candidate,
                               "holdout_candidate": holdout_candidate,
                               "holdout_incumbent": holdout_incumbent},
                    "incumbent": {"path": incumbent["path"], "hash": incumbent["hash"]}}
        (cycle_dir / "decision.json").write_text(
            json.dumps(decision, indent=2, sort_keys=True), encoding="utf-8")
        log({"event": "decision", "cycle": cycle_no, "promoted": promoted, "reason": reason})

        if promoted:
            incumbent = {"path": str(candidate_path), "hash": candidate_hash,
                         "screen_suite": screen_candidate,
                         "origin": f"promoted in cycle {cycle_no}"}
            incumbent_rules = candidate_rules
        history.append({"cycle": cycle_no, "agent": proposal["agent"], "proposal": proposal,
                        "promoted": promoted, "reason": reason,
                        "metrics": {"screen": screen_candidate["metrics"],
                                    "holdout": holdout_candidate["metrics"]},
                        "incumbent_metrics": {"screen": incumbent["screen_suite"]["metrics"],
                                              "holdout": holdout_incumbent["metrics"]}})

    write_report(run_dir, cfg, history, incumbent, stopped, total_cycles)
    log({"event": "run_end", "cycles_completed": len(history),
         "final_incumbent": incumbent["path"], "stopped": stopped})
    print(json.dumps({"out": str(run_dir), "cycles": len(history),
                      "final_incumbent": incumbent["path"], "stopped": stopped}, sort_keys=True))
    return 0 if stopped is None else 3


if __name__ == "__main__":
    raise SystemExit(main())
