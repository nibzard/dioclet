#!/usr/bin/env python3
"""Compare batch summaries as a markdown table.

Usage:
    python3 compare.py results/v01_baseline results/v02_tie_attacker ...

Reads each directory's summary.json and prints one row per batch for
the metrics that matter for rule-tuning decisions (SPEC §12–13).
"""

import argparse
import json
import os
import sys


def load(path):
    with open(os.path.join(path, "summary.json"), "r", encoding="utf-8") as fh:
        return json.load(fh)


def fmt(value, digits=1):
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def metric_row(label, getter, digits=1):
    def row(sums):
        return [fmt(getter(s), digits) for s in sums]
    return label, row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="batch result directories")
    args = parser.parse_args(argv)

    sums = [load(path) for path in args.inputs]
    headers = [os.path.basename(os.path.normpath(p)) for p in args.inputs]

    rows = [
        metric_row("games", lambda s: s["games"], 0),
        metric_row("win rate", lambda s: s["win_rate"]["rate"], 3),
        metric_row("draws", lambda s: s["draws"], 0),
        metric_row("median rounds", lambda s: s["durations"]["total_rounds"]["median"]),
        metric_row("mean rounds", lambda s: s["durations"]["total_rounds"]["mean"]),
        metric_row("p95 rounds", lambda s: s["durations"]["total_rounds"]["p95"]),
        metric_row("median turns", lambda s: s["durations"]["total_turns"]["median"]),
        metric_row("rounds L1 (med)", lambda s: s["durations"]["rounds_level1"]["median"]),
        metric_row("duels/game", lambda s: s["duels"]["per_game_mean"], 2),
        metric_row("attacker win %", lambda s: 100 * s["duels"]["attacker_win_rate"], 0),
        metric_row("aggressive win %", lambda s: 100 * s["win_rate_by_policy"]["aggressive"]["rate"], 0),
        metric_row("greedy win %", lambda s: 100 * s["win_rate_by_policy"]["greedy"]["rate"], 0),
        metric_row("balanced win %", lambda s: 100 * s["win_rate_by_policy"]["balanced"]["rate"], 0),
        metric_row("random win %", lambda s: 100 * s["win_rate_by_policy"]["random"]["rate"], 0),
        metric_row("pos1 win %", lambda s: 100 * s["win_rate_by_turn_position"]["pos1"]["rate"], 0),
        metric_row("pos4 win %", lambda s: 100 * s["win_rate_by_turn_position"]["pos4"]["rate"], 0),
        metric_row("1st challenger win %", lambda s: 100 * s["first_challenger"]["challenger_win_rate"], 0),
        metric_row("comeback share %", lambda s: 100 * s["first_challenger"]["comeback_share_of_wins"], 0),
        metric_row("collected/player", lambda s: s["equipment"]["collected_per_player"]["mean"], 2),
        metric_row("auto-granted/player", lambda s: s["equipment"]["auto_granted_per_player"]["mean"], 2),
        metric_row("emperor hit %", lambda s: 100 * s["emperor"]["hit_rate"], 0),
        metric_row("peristyle buys", lambda s: s["seals"]["peristyle_glory_purchases"], 0),
        metric_row("glory wasted/player", lambda s: s["glory"]["wasted_at_cap_per_player"]["mean"], 2),
    ]

    width = max(len(h) for h in headers + [r[0] for r in rows]) + 2
    out = ["| metric" + "".join(f" | {h}" for h in headers) + " |",
           "|" + "---|" * (len(headers) + 1)]
    for label, row in rows:
        out.append(f"| {label}" + "".join(f" | {v}" for v in row(sums)) + " |")
    table = "\n".join(out)
    print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main())
