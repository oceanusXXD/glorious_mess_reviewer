"""Venue-native review guidance injected into prompt templates."""

from __future__ import annotations

from glorious_mess_reviewer.schemas import VenuePresetName, VenueProfile

_SHIT_SHARED_GUIDANCE = """
SHIT-native reviewing guidance:
- Reward academic camouflage: the best submissions look absurd on the surface but still behave like real papers.
- Reward thesis-bearing zhenghuo: a joke should sharpen the claim, not replace the claim.
- Reward social or emotional payload: a good SHIT paper often reveals a real frustration, observation, or collective feeling.
- Reward discussability: imagine whether anonymous community reviewers would quote it, argue about it, and remember it.
- Distinguish four buckets clearly:
  1. empty shock-joke
  2. absurd but insightful
  3. serious but venue-misaligned
  4. incoherent sludge
- Do not reward low-effort vulgarity, recycled internet jokes, or random profanity without analytical payoff.
- SHIT is not a license for illegality or abuse. Do not reward hate, stalking, doxxing, revenge porn, non-consensual humiliation, explicit sexual exploitation, or actionable crime instructions.
""".strip()

_DEFAULT_TRACK_GUIDANCE = """
Default SHIT desk emphasis:
- Look for a balance between formal paper structure, absurd framing, and a real kernel of thought.
- Community resonance matters, but empty virality should not beat payload.
- A manuscript can be silly, bitter, satirical, or emotionally raw, as long as it still does intellectual work.
""".strip()

_HARDCORE_TRACK_GUIDANCE = """
Hardcore SHIT screening emphasis:
- Be stricter about method, evidence, and explainability.
- A hilarious premise is not enough; the manuscript should leave behind something checkable or at least rigorously argued.
- Reward papers that feel like a genuine study disguised as a cursed artifact.
""".strip()

_ABSTRACT_TRACK_GUIDANCE = """
Abstract SHIT screening emphasis:
- Be more tolerant of lightweight methods if the manuscript is memorable, sharply framed, and socially legible.
- Reward clean conversion from meme to argument, not just energy.
- Strong readability and quote-worthiness help, but illegality, harassment, or exploitative content still fail the venue spirit.
""".strip()


def build_venue_guidance_text(venue_profile: VenueProfile) -> str:
    """Return the reviewer playbook text that should accompany the venue profile."""

    preset = venue_profile.preset_name
    if preset is VenuePresetName.SHIT_HARDCORE_SCREENING:
        track_guidance = _HARDCORE_TRACK_GUIDANCE
    elif preset is VenuePresetName.SHIT_ABSTRACT_SCREENING:
        track_guidance = _ABSTRACT_TRACK_GUIDANCE
    else:
        track_guidance = _DEFAULT_TRACK_GUIDANCE

    return "\n\n".join(
        [
            _SHIT_SHARED_GUIDANCE,
            track_guidance,
        ]
    )
