#!/usr/bin/env python3
"""Condensed player observation for narrative playtests."""
import json
import subprocess
import sys

run = sys.argv[1]
player = sys.argv[2]
out = subprocess.run(
    [sys.executable, "sim.py", "observe", "--run", run, "--player", player],
    capture_output=True, text=True, check=True,
).stdout
d = json.loads(out)
print("turn", d["turn_id"], "round", d["round"], "phase", d["phase"],
      "active", d["active_player"], "die", d["movement_die"], "status", d["status"])
print("progress", d.get("progress"))
print("revealed", d.get("revealed_districts"))
for p, v in sorted(d["players"].items()):
    print(p, "pos", v["position"], "eq", v["equipment_count"], v["equipment"],
          "glory", v["glory"], "seals", v["seals"], "hits", v["emperor_hits"])
for a in d["legal_actions"]:
    extra = " ".join(k + "=" + str(a[k]) for k in
                     ("target", "spend_glory", "seal_site", "item", "spend") if k in a)
    print(a["action_id"], a["kind"], a.get("destination"), extra)
