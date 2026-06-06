"""Few-shot calibration snippets for SHIT-native prompt rendering."""

from __future__ import annotations

from glorious_mess_reviewer.schemas import VenuePresetName, VenueProfile

_PRECHECK_EXAMPLES = """
Calibration examples:

1. Safe weirdness, should stay reviewable:
- A manuscript about office-chair drift as a proxy for boundary failure.
- Ridiculous premise, but no abusive instructions or exploitative content.
- Expected stance: weird is allowed; do not reject just because it is cursed.

2. Illegal / exploitative escalation, must be risk-flagged:
- A manuscript that turns stalking, doxxing, revenge porn, sexual blackmail, or fraud tutorials into its central “bit”.
- Expected stance: satire does not neutralize harm; flag risk and block or escalate.
""".strip()

_EVIDENCE_EXAMPLES = """
Calibration examples:

1. Absurd but substantive:
- “We tracked thirty-seven office chairs with colored tape and found ownership ambiguity predicts drift.”
- This is a ridiculous setup, but it still contains a claim, a method, and evidence.

2. Empty shock joke:
- “The vibes are immaculate, therefore the thesis is complete.”
- This is only slogan energy. Do not hallucinate payload that is not there.
""".strip()

_VALUE_EXAMPLES = """
Calibration examples:

1. High venue fit:
- A paper that looks academically overbuilt, has a cursed premise, and still reveals a real social truth.
- Reward academic cosplay, discussability, and meme-to-argument conversion.

2. Low venue fit:
- A competent but sober systems paper with no absurd framing, no community bite, and no SHIT-native zhenghuo.
- Respect the craft, but mark it as serious-and-misaligned rather than pretending it fits.
""".strip()

_META_EXAMPLES = """
Calibration examples:

1. If evidence says “real claim, modest evidence” and value says “excellent cursed framing”, synthesize toward absurd-but-substantive.
2. If evidence says “no claim” and value says “the bit is loud”, synthesize toward funny-but-empty rather than over-rewarding spectacle.
3. If any upstream signal includes exploitative sexual content, do not translate provocation into venue fit.
""".strip()


def build_venue_examples_text(template_name: str, venue_profile: VenueProfile) -> str:
    """Return a compact few-shot block for the given prompt template and venue."""

    preset = venue_profile.preset_name
    track_line = (
        "Track note: this venue is the abstract SHIT lane, so readability and community resonance matter slightly more."
        if preset is VenuePresetName.SHIT_ABSTRACT_SCREENING
        else "Track note: this venue is the hardcore SHIT lane, so rigor and checkability matter slightly more."
        if preset is VenuePresetName.SHIT_HARDCORE_SCREENING
        else "Track note: use the balanced default SHIT desk standard."
    )

    example_map = {
        "precheck_agent.j2": _PRECHECK_EXAMPLES,
        "evidence_agent.j2": _EVIDENCE_EXAMPLES,
        "value_agent.j2": _VALUE_EXAMPLES,
        "meta_agent.j2": _META_EXAMPLES,
    }
    body = example_map.get(template_name, "")
    return "\n\n".join(part for part in (track_line, body) if part).strip()
