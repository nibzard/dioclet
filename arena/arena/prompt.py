# ABOUTME: The instruction text every remote provider receives, built from
# ABOUTME: the active rules; the adapters change only the request envelope.
"""Provider instruction text for Arena seats.

All wording that reaches a decision model lives here, so the System One
and OpenAI adapters send the same instructions. Rule values are read
from the active rules file, never copied into the text.
"""

from candidate_actions import claim_rule_text

INTRO = ("Select the best legal board-game move given this public "
         "state. Exact single-roll odds in the features are exact; "
         "any longer-horizon judgement is yours.")

# Legacy non-succession texts, kept for the classic projection mode.
CLASSIC_INSTRUCTIONS = (
    "You are one player in a four-player competitive board game. "
    "Pick the option most likely to improve your eventual chance to be "
    "first to defeat the Emperor. Prefer an immediate legal win over "
    "unrelated actions; consider progress, opponents, and resource tempo. "
    "Use only the supplied public information and action descriptions. "
    "Return one of the supplied option ids.")
PROJECTION_INSTRUCTIONS = (
    "You are one player in a four-player competitive board game. "
    "Pick the option most likely to improve your eventual chance to be "
    "first to defeat the Emperor. Prefer an immediate legal win over "
    "unrelated actions; consider progress, opponents, and resource tempo. "
    "Use only the supplied public information and action descriptions.")


def succession_instructions(rules):
    """Succession instruction built from the active rules.

    With a claim window the deadline sentence covers the response rule,
    so no response wording is added. With a zero window the response
    rule from candidate_actions warns that a final unanswered response
    crowns the claimant.
    """
    text = ("Choose the supplied action that maximizes your eventual "
            "chance of winning under the active rules. Compare immediate "
            "outcomes, resource costs, progress toward a claim, and "
            "rivals' opportunities to win or to cancel your claim. Use "
            "the explicit deadline when a claim is pending. Contest odds "
            "describe that contest only.")
    if not rules["succession"]["claim_window_rounds"]:
        text += (" " + claim_rule_text(rules)
                 + " Any action completes a response; a final response "
                 "that does not cancel the claim crowns the claimant.")
    return text
