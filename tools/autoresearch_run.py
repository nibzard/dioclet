#!/usr/bin/env python3
"""Offline autoresearch driver for the V0.8 fee-1 programme.

``tools/run_programme.py`` is the trusted runner, but its only proposal
sources are paid ``claude -p`` agents or fixed scripted constants. This
run has no authorized proposal budget, so the research agent formulates
each hypothesis itself. This driver executes the same frozen loop with
proposal files instead of model calls, reusing the runner's own
functions unchanged: ``run_suite`` (suite parameters), ``validate_proposal``,
``apply_change``, ``promotion_checks`` (mechanical guards), and the
frozen-source hash check.

It adds the preregistered validation layer the release review found
missing: the legal contest-availability veto computed by
``tools/contest_audit.py`` from each suite's re-verified games. Veto
thresholds live in the experiment configuration and are frozen before
the first candidate cycle.

Commands: init (baseline suites), diagnostic (known-bad probe), cycle
(one proposal through screen + fresh holdout + veto), confirm (large
fresh confirmation suites). Every command stops on any frozen-hash
change, replay divergence, or incomplete suite.
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import engine
from tools import contest_audit
from tools.run_programme import (FROZEN_SOURCES, apply_change, change_key,
                                 get_path, promotion_checks, run_suite,
                                 source_hashes, suite_metrics, validate_proposal)
from tools.succession_experiments import PROFILES

EXTRA_FROZEN = ("tools/contest_audit.py", "tools/autoresearch_run.py",
                "programme.md")

TSV_COLUMNS = ("cycle\tparent_hash\tcandidate_hash\tchanged_key\told_value\tnew_value\t"
               "screen_games\tholdout_games\tdraws\tmedian_rounds\tlegal_contest_rate\t"
               "cancellations_per_game\twinning_profiles\tcomplexity_delta\tstatus\twhy")


def now_utc():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    return __import__("hashlib").sha256(Path(path).read_bytes()).hexdigest()


def all_hashes():
    hashes = source_hashes()
    for name in EXTRA_FROZEN:
        hashes[name] = sha256_file(REPO / name)
    return hashes


def load_state(out_dir):
    return json.loads((Path(out_dir) / "run-state.json").read_text(encoding="utf-8"))


def save_state(out_dir, state):
    engine._atomic_write_json(str(Path(out_dir) / "run-state.json"), state)


def log(out_dir, event):
    event = {"time": now_utc(), **event}
    with (Path(out_dir) / "run-log.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")


def check_frozen(out_dir, state):
    current = all_hashes()
    if current != state["frozen_hashes"]:
        raise SystemExit("STOP source_hashes_changed: frozen engine, evaluator, "
                         "policy, test, programme, or audit files changed mid-run")


def audit(suite_record):
    """Attach the contest-availability audit to one suite record."""
    summary = contest_audit.audit_suite(Path(suite_record["out"]) / "base")
    suite_record["contest_audit"] = summary
    return summary


def veto_checks(candidate_audit, baseline_audit, veto, fee):
    """Preregistered counterplay-availability veto; every check must pass."""
    checks = []

    def add(name, ok, detail):
        checks.append({"check": name, "passed": bool(ok), "detail": detail})

    offered = candidate_audit.get("contest_offered_rate")
    add("contest_offered_floor", offered is not None and offered >= veto["minimum_contest_offered_rate"],
        f"offered rate {offered} vs floor {veto['minimum_contest_offered_rate']}")
    claims_option = candidate_audit.get("claims_with_contest_option")
    add("claims_with_contest_option_floor", claims_option is not None and
        claims_option >= veto["minimum_claims_with_contest_option"],
        f"claims with a legal contest {claims_option} vs floor {veto['minimum_claims_with_contest_option']}")
    afford = candidate_audit.get("can_afford_fee_rate")
    add("responder_afford_floor", afford is not None and afford >= veto["minimum_can_afford_rate"],
        f"responders able to pay the fee {afford} vs floor {veto['minimum_can_afford_rate']}")
    crowned = candidate_audit.get("claims_crowned_without_legal_contest")
    add("no_poverty_coronation", crowned is not None and
        crowned <= veto["maximum_claims_crowned_without_legal_contest"],
        f"claims crowned with no legal contest {crowned} vs ceiling "
        f"{veto['maximum_claims_crowned_without_legal_contest']}")
    if baseline_audit:
        base_afford = baseline_audit.get("afford_at_fee", {}).get(str(fee))
        add("baseline_purse_affords_candidate_fee", base_afford is not None and
            base_afford >= veto["minimum_baseline_afford_at_candidate_fee"],
            f"share of baseline response purses able to pay fee {fee} is {base_afford} "
            f"vs floor {veto['minimum_baseline_afford_at_candidate_fee']}")
    return checks


def verify_suite(suite, games):
    if suite["exit_code"] != 0:
        raise SystemExit(f"STOP incomplete_suite: {suite['label']} exit {suite['exit_code']}")
    metrics = suite["metrics"]
    if metrics["finished_games"] != games or metrics["incomplete_games"] != 0:
        raise SystemExit(f"STOP insufficient_evidence: {suite['label']} finished "
                         f"{metrics['finished_games']} of {games}")
    audit_summary = suite.get("contest_audit") or audit(suite)
    if audit_summary.get("games_replay_verified") != audit_summary.get("games_total"):
        raise SystemExit(f"STOP replay_divergence: {suite['label']}")
    return metrics, audit_summary


def cmd_init(args, cfg):
    out = Path(args.out)
    if out.exists() and any(out.iterdir()):
        raise SystemExit("output directory is not empty")
    out.mkdir(parents=True)
    incumbent_path = REPO / cfg["rules"]
    rules = engine.load_rules(str(incumbent_path))
    state = {"created": now_utc(), "config": str(args.config),
             "config_hash": __import__("hashlib").sha256(Path(args.config).read_bytes()).hexdigest(),
             "frozen_hashes": all_hashes(), "policy_version": "succession-probes-0.8.0",
             "incumbent": {"path": str(incumbent_path), "hash": engine.rules_hash(rules),
                           "screen_suite": None, "origin": "configured-incumbent"},
             "baseline": None, "cycles": [], "tested_changes": []}
    save_state(out, state)
    log(out, {"event": "init", "incumbent": state["incumbent"]["hash"],
              "seeds": {"screen": cfg["screen_seed_base"], "holdout": cfg["holdout_seed_base"]}})
    screen = run_suite("baseline-screen", str(incumbent_path), out / "baseline-screen",
                       cfg["games_per_suite"], cfg["screen_seed_base"], "screen", cfg["profiles"])
    holdout = run_suite("baseline-holdout", str(incumbent_path), out / "baseline-holdout",
                        cfg["games_per_suite"], cfg["holdout_seed_base"], "holdout", cfg["profiles"])
    for suite in (screen, holdout):
        audit(suite)
        verify_suite(suite, cfg["games_per_suite"])
    state = load_state(out)
    state["baseline"] = {"hash": state["incumbent"]["hash"], "screen": screen, "holdout": holdout}
    state["incumbent"]["screen_suite"] = screen
    save_state(out, state)
    log(out, {"event": "baseline_done", "screen_draws": screen["metrics"]["draw_fraction"],
              "holdout_draws": holdout["metrics"]["draw_fraction"]})
    print(json.dumps({"baseline": state["incumbent"]["hash"],
                      "screen": screen["metrics"], "holdout": holdout["metrics"],
                      "screen_audit": screen["contest_audit"], "holdout_audit": holdout["contest_audit"]},
                     sort_keys=True, default=str))


def cmd_diagnostic(args, cfg):
    out = Path(args.out)
    state = load_state(out)
    check_frozen(out, state)
    if state.get("baseline") is None:
        raise SystemExit("run init first")
    rules = engine.load_rules(state["incumbent"]["path"])
    diag_dir = out / "diagnostic"
    if diag_dir.exists() and any(diag_dir.iterdir()):
        raise SystemExit("diagnostic already exists; never rewrite it")
    diag_dir.mkdir()
    candidate = apply_change(rules, args.key, json.loads(args.value))
    engine.validate_rules(candidate)
    candidate_path = diag_dir / "candidate-rules.json"
    engine._atomic_write_json(str(candidate_path), candidate)
    screen = run_suite("diagnostic-screen", str(candidate_path), diag_dir / "screen",
                       cfg["games_per_suite"], cfg["screen_seed_base"], "screen", cfg["profiles"])
    holdout = run_suite("diagnostic-holdout", str(candidate_path), diag_dir / "holdout",
                        cfg["games_per_suite"], cfg["holdout_seed_base"], "holdout", cfg["profiles"])
    for suite in (screen, holdout):
        audit(suite)
        verify_suite(suite, cfg["games_per_suite"])
    baseline = state["baseline"]
    mechanical = {}
    for split, suite in (("screen", screen), ("holdout", holdout)):
        checks = promotion_checks(baseline[split]["metrics"], suite["metrics"], cfg["promotion"])
        mechanical[split] = {"checks": checks,
                             "mechanical_promotion": all(c["passed"] for c in checks)}
    veto = cfg.get("counterplay_veto")
    fee = candidate["succession"]["contest_cost"]
    guard = {}
    if veto:
        for split, suite in (("screen", screen), ("holdout", holdout)):
            guard[split] = veto_checks(suite["contest_audit"], baseline["screen"]["contest_audit"],
                                       veto, fee)
    report = {"key": args.key, "value": json.loads(args.value),
              "candidate_hash": engine.rules_hash(candidate), "mechanical": mechanical,
              "counterplay_veto": guard,
              "conclusion": ("existing mechanical checks alone would promote this known-bad "
                             "variant" if all(m["mechanical_promotion"] for m in mechanical.values())
                             else "mechanical checks reject it"),
              "suites": {"screen": screen, "holdout": holdout}}
    engine._atomic_write_json(str(diag_dir / "diagnostic.json"), report)
    log(out, {"event": "diagnostic", "key": args.key, "value": args.value,
              "mechanical_promotion": [mechanical[s]["mechanical_promotion"] for s in ("screen", "holdout")]})
    print(json.dumps({"mechanical_promotion": {s: mechanical[s]["mechanical_promotion"] for s in mechanical},
                      "veto": {s: [c["check"] for c in guard.get(s, []) if not c["passed"]] for s in guard},
                      "audit_screen": screen["contest_audit"], "audit_holdout": holdout["contest_audit"]},
                     sort_keys=True, default=str))


def cmd_cycle(args, cfg):
    out = Path(args.out)
    state = load_state(out)
    check_frozen(out, state)
    if state.get("baseline") is None:
        raise SystemExit("run init first")
    if len(state["cycles"]) >= cfg["cycles"]:
        raise SystemExit("cycle budget reached; do not extend it to chase a result")
    proposal = json.loads(Path(args.proposal).read_text(encoding="utf-8"))
    incumbent_rules = engine.load_rules(state["incumbent"]["path"])
    problem = validate_proposal(proposal, incumbent_rules, cfg["allowed_changes"])
    if problem:
        raise SystemExit(f"STOP {problem}")
    key = change_key(incumbent_rules, proposal)
    if key in state["tested_changes"]:
        raise SystemExit("STOP duplicate_proposal: already tested against this incumbent")
    cycle_no = len(state["cycles"]) + 1
    cycle_dir = out / "cycles" / f"{cycle_no:02d}"
    cycle_dir.mkdir(parents=True)
    engine._atomic_write_json(str(cycle_dir / "proposal.json"), proposal)
    old_value = get_path(incumbent_rules, proposal["rule_path"])
    candidate_rules = apply_change(incumbent_rules, proposal["rule_path"], proposal["value"])
    engine.validate_rules(candidate_rules)
    candidate_path = cycle_dir / "candidate-rules.json"
    engine._atomic_write_json(str(candidate_path), candidate_rules)
    candidate_hash = engine.rules_hash(candidate_rules)
    log(out, {"event": "cycle_start", "cycle": cycle_no, "proposal": proposal["rule_path"],
              "value": proposal["value"], "parent": state["incumbent"]["hash"],
              "candidate": candidate_hash})

    # Paired screening: same seeds for incumbent and candidate; reuse a
    # matching earlier suite for the incumbent instead of recomputing.
    incumbent_screen = state["incumbent"]["screen_suite"]
    if incumbent_screen is None:
        incumbent_screen = run_suite("screen-incumbent", state["incumbent"]["path"],
                                     cycle_dir / "screen-incumbent", cfg["games_per_suite"],
                                     cfg["screen_seed_base"], "screen", cfg["profiles"])
        audit(incumbent_screen)
    screen_candidate = run_suite("screen-candidate", str(candidate_path),
                                 cycle_dir / "screen-candidate", cfg["games_per_suite"],
                                 cfg["screen_seed_base"], "screen", cfg["profiles"])
    audit(screen_candidate)
    holdout_seed = cfg["holdout_seed_base"] + cycle_no * 1000
    holdout_incumbent = run_suite("holdout-incumbent", state["incumbent"]["path"],
                                  cycle_dir / "holdout-incumbent", cfg["games_per_suite"],
                                  holdout_seed, "holdout", cfg["profiles"])
    audit(holdout_incumbent)
    holdout_candidate = run_suite("holdout-candidate", str(candidate_path),
                                  cycle_dir / "holdout-candidate", cfg["games_per_suite"],
                                  holdout_seed, "holdout", cfg["profiles"])
    audit(holdout_candidate)
    suites = (("screen", incumbent_screen, screen_candidate),
              ("holdout", holdout_incumbent, holdout_candidate))
    metrics = {}
    for split, inc_suite, cand_suite in suites:
        inc_metrics, _ = verify_suite(inc_suite, cfg["games_per_suite"])
        cand_metrics, _ = verify_suite(cand_suite, cfg["games_per_suite"])
        metrics[split] = {"incumbent": inc_metrics, "candidate": cand_metrics}
    check_frozen(out, state)

    promo = cfg["promotion"]
    veto = cfg["counterplay_veto"]
    fee = candidate_rules["succession"]["contest_cost"]
    baseline_audit = state["baseline"]["screen"]["contest_audit"]
    checks = {}
    for split, inc_suite, cand_suite in suites:
        mechanical = promotion_checks(metrics[split]["incumbent"], metrics[split]["candidate"], promo)
        guard = veto_checks(cand_suite["contest_audit"], baseline_audit, veto, fee)
        checks[split] = {"mechanical": mechanical, "counterplay_veto": guard,
                         "veto_failed": [c["check"] for c in guard if not c["passed"]],
                         "mechanical_failed": [c["check"] for c in mechanical if not c["passed"]]}
    gates_ok = all(not checks[s]["veto_failed"] and not checks[s]["mechanical_failed"] for s in checks)
    decision = {"cycle": cycle_no, "proposal": proposal,
                "rule_path": proposal["rule_path"], "old_value": old_value,
                "new_value": proposal["value"],
                "parent_hash": state["incumbent"]["hash"], "candidate_hash": candidate_hash,
                "holdout_seed_base": holdout_seed,
                "automated_gates_passed": gates_ok, "checks": checks,
                "metrics": {s: {"incumbent": metrics[s]["incumbent"],
                                "candidate": metrics[s]["candidate"]} for s in metrics},
                "audits": {s: {"incumbent": dict(inc["contest_audit"]),
                               "candidate": dict(cand["contest_audit"])}
                           for s, inc, cand in suites}}
    engine._atomic_write_json(str(cycle_dir / "decision.json"), decision)
    state["tested_changes"].append(key)
    state["cycles"].append({"cycle": cycle_no, "proposal": proposal,
                            "automated_gates_passed": gates_ok,
                            "candidate_hash": candidate_hash,
                            "kept": False, "status": "pending-researcher-review"})
    if gates_ok:
        # Automated gates passed; the researcher records the final keep or
        # discard with the hypothesis-specific judgment in verdict.md.
        state["staged"] = {"path": str(candidate_path), "hash": candidate_hash,
                           "screen_suite": screen_candidate, "cycle": cycle_no}
    save_state(out, state)
    log(out, {"event": "cycle_suites_done", "cycle": cycle_no, "gates_passed": gates_ok,
              "failed": {s: checks[s]["mechanical_failed"] + checks[s]["veto_failed"] for s in checks}})
    print(json.dumps({"cycle": cycle_no, "automated_gates_passed": gates_ok,
                      "failed": {s: checks[s]["mechanical_failed"] + checks[s]["veto_failed"]
                                 for s in checks}}, sort_keys=True))


def cmd_decide(args, cfg):
    """Record the researcher's final keep/discard for the last cycle."""
    out = Path(args.out)
    state = load_state(out)
    cycle = state["cycles"][-1]
    if cycle["status"] != "pending-researcher-review":
        raise SystemExit("last cycle is not awaiting a decision")
    verdict = json.loads(Path(args.verdict).read_text(encoding="utf-8"))
    cycle_dir = out / "cycles" / f"{cycle['cycle']:02d}"
    engine._atomic_write_json(str(cycle_dir / "verdict.json"), verdict)
    cycle["status"] = verdict["status"]
    cycle["kept"] = verdict["status"] == "keep"
    if verdict["status"] not in ("keep", "discard", "needs-human-review"):
        raise SystemExit("status must be keep, discard, or needs-human-review")
    if verdict["status"] == "keep":
        if not cycle["automated_gates_passed"]:
            raise SystemExit("cannot keep a candidate that failed automated gates")
        state["incumbent"] = {"path": state["staged"]["path"], "hash": state["staged"]["hash"],
                              "screen_suite": state["staged"]["screen_suite"],
                              "origin": f"promoted in cycle {cycle['cycle']}"}
    state.pop("staged", None)
    save_state(out, state)
    log(out, {"event": "decision", "cycle": cycle["cycle"], "status": verdict["status"]})
    print(json.dumps({"cycle": cycle["cycle"], "status": verdict["status"],
                      "incumbent": state["incumbent"]["hash"]}))


def cmd_confirm(args, cfg):
    out = Path(args.out)
    state = load_state(out)
    check_frozen(out, state)
    confirm_dir = out / "confirmation"
    if confirm_dir.exists() and any(confirm_dir.iterdir()):
        raise SystemExit("confirmation already exists; never rewrite it")
    confirm_dir.mkdir()
    seeds = cfg["confirmation_seed_base"]
    suites = {}
    for label, rules_path in (("incumbent", state["incumbent"]["path"]),
                              ("challenger", args.rules)):
        suite = run_suite(f"confirm-{label}", rules_path, confirm_dir / label,
                          args.games, seeds, "holdout", cfg["profiles"])
        audit(suite)
        verify_suite(suite, args.games)
        suites[label] = suite
    engine._atomic_write_json(str(confirm_dir / "summary.json"),
                              {k: {"metrics": v["metrics"], "contest_audit": v["contest_audit"]}
                               for k, v in suites.items()})
    log(out, {"event": "confirmation", "games": args.games, "seeds": seeds})
    print(json.dumps({k: {"metrics": v["metrics"], "audit": v["contest_audit"]}
                      for k, v in suites.items()}, sort_keys=True, default=str))


def cmd_tsv(args, cfg):
    state = load_state(args.out)
    rows = [TSV_COLUMNS]
    base = state.get("baseline")
    if base:
        m, a = base["holdout"]["metrics"], base["holdout"]["contest_audit"]
        rows.append("\t".join(map(str, ("0", "-", base["hash"], "-", "-", "-",
                                        base["screen"]["games"], base["holdout"]["games"],
                                        m["draw_fraction"], m["median_rounds"],
                                        a["contest_offered_rate"], m["cancellations_per_game"],
                                        len(m["wins_by_strategy"]), "baseline", "baseline",
                                        "fee-1 incumbent, first benchmark"))))
    for cycle in state["cycles"]:
        cycle_dir = Path(args.out) / "cycles" / f"{cycle['cycle']:02d}"
        decision = json.loads((cycle_dir / "decision.json").read_text())
        m = decision["metrics"]["holdout"]["candidate"]
        a = decision["audits"]["holdout"]["candidate"]
        rows.append("\t".join(map(str, (cycle["cycle"], decision["parent_hash"][:12],
                                        decision["candidate_hash"][:12], decision["rule_path"],
                                        json.dumps(decision["old_value"]), json.dumps(decision["new_value"]),
                                        decision["metrics"]["screen"]["candidate"]["finished_games"],
                                        m["finished_games"], m["draw_fraction"], m["median_rounds"],
                                        a["contest_offered_rate"], m["cancellations_per_game"],
                                        len(m["wins_by_strategy"]), cycle.get("complexity_delta", "NA"),
                                        cycle["status"], cycle.get("why", "see verdict.json")))))
    (Path(args.out) / "experiments.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"wrote {Path(args.out) / 'experiments.tsv'}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--config", default=str(REPO / "experiments" / "autoresearch-ar1.json"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    diag = sub.add_parser("diagnostic")
    diag.add_argument("--key", required=True)
    diag.add_argument("--value", required=True)
    cyc = sub.add_parser("cycle")
    cyc.add_argument("--proposal", required=True)
    dec = sub.add_parser("decide")
    dec.add_argument("--verdict", required=True)
    conf = sub.add_parser("confirm")
    conf.add_argument("--rules", required=True)
    conf.add_argument("--games", type=int, default=384)
    sub.add_parser("tsv")
    args = parser.parse_args(argv)
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    {"init": cmd_init, "diagnostic": cmd_diagnostic, "cycle": cmd_cycle,
     "decide": cmd_decide, "confirm": cmd_confirm, "tsv": cmd_tsv}[args.command](args, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
