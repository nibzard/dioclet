# ABOUTME: One public evidence object per turn, shared by every remote adapter.
# ABOUTME: Adapters change only the envelope; the game data stays identical.
"""The single evidence object that every Arena decision model receives.

The projection carries the rule summary, so no rule text is repeated at
the top level. Each candidate keeps exactly the four public keys the
model chooses between. This module adds nothing beyond the public
observation and the rules that the projection and the shortlist hold.
"""

from arena.providers import TurnView

EVIDENCE_SCHEMA = "arena-evidence-1"

CANDIDATE_KEYS = ("action_id", "kind", "description", "features")


def build_evidence(view: TurnView) -> dict:
    """Build the one evidence object for this turn from the view."""
    return {
        "schema": EVIDENCE_SCHEMA,
        "projection": view.projection,
        "candidates": [
            {key: candidate[key] for key in CANDIDATE_KEYS}
            for candidate in view.candidates
        ],
    }
