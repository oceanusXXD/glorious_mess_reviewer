"""Deterministic mock payloads for golden samples and integration tests."""

from __future__ import annotations

from glorious_mess_reviewer.schemas import ReviewDimension


def _score(score: int, reason: str, *evidence: str) -> dict[str, object]:
    return {
        "score": score,
        "confidence": 0.86,
        "reason": reason,
        "supporting_evidence": list(evidence),
        "uncertainty_note": None,
    }


def build_mock_registry() -> dict[tuple[str, str], dict[str, object] | str]:
    registry: dict[tuple[str, str], dict[str, object] | str] = {}

    # 场景 1：高 payload 且高度 venue-aware，用作 happy path 与 golden 基准。
    registry[("absurd-rigorous-001", "HanCeGateAgent")] = {
        "decision": "pass",
        "minimum_reviewable": True,
        "hard_failures": [],
        "missing_sections": [],
        "risk_flags": [],
        "notes": ["All core sections are present and reviewable."],
    }
    registry[("absurd-rigorous-001", "EvidenceSludgeEngine")] = {
        "paper_summary": "A humorous but methodical study of office-chair drift as a proxy for coordination breakdown.",
        "extracted_core_claim": "Ambiguity of ownership drives chair drift, and the joke framing supports a real coordination argument.",
        "argument_status": "clear",
        "evidence_snippets": [
            "We tracked thirty-seven chairs with colored tape.",
            "The strongest predictor was ambiguity of ownership and local norms around borrowing."
        ],
        "major_strengths": ["The paper turns a ridiculous premise into a falsifiable systems claim."],
        "major_weaknesses": ["The sample size is small and manually observed."],
        "required_revisions": ["Clarify how observation bias affected the drift logs."],
        "optional_revisions": ["Add one more reproducibility detail for the logging sheet."],
        "risk_flags": [],
        "dimension_scores": {
            "core_claim_clarity": _score(5, "The manuscript states a clear claim and keeps returning to it.", "chair drift is a comedic proxy for neglected system boundaries"),
            "structural_integrity": _score(5, "All key sections are present, including conclusion and limitations.", "Conclusion", "Limitations"),
            "method_or_reasoning_legibility": _score(4, "The method is simple but traceable and reproducible enough.", "tracked thirty-seven chairs with colored tape"),
            "evidence_checkability": _score(4, "Evidence is modest but concrete and inspectable.", "movement logs", "manual observation sheets"),
            "result_payload": _score(5, "The paper contributes an actual argument rather than vibes alone.", "something falsifiable about social technology"),
            "limitation_honesty": _score(5, "The manuscript explicitly acknowledges sample and causality limits.", "does not establish causality and may overfit")
        }
    }
    registry[("absurd-rigorous-001", "AbsurdityButMakeItRigorous")] = {
        "zhenghuo_verdict": "High-grade absurd framing that still serves the claim.",
        "novelty_label": "fresh",
        "major_strengths": ["Humor amplifies, rather than replaces, the systems argument."],
        "major_weaknesses": ["The joke may initially hide the seriousness of the payload."],
        "required_revisions": ["Make the community takeaway explicit in the abstract."],
        "optional_revisions": ["Tighten one paragraph of scene-setting comedy."],
        "risk_flags": [],
        "dimension_scores": {
            "venue_fit": _score(5, "This is exactly the kind of absurd-but-rigorous manuscript the venue wants.", "The joke framing helps reveal a broader coordination pattern"),
            "zhenghuo_execution": _score(5, "The bit lands and remains disciplined.", "Chair drift is a comedic proxy"),
            "absurd_originality": _score(4, "The premise is fresh without feeling random.", "rolling office chairs are latent distributed systems"),
            "meme_to_argument_conversion": _score(5, "The meme premise successfully becomes a real argument.", "humor to attract attention, but the payload is a tractable argument"),
            "community_discussion_value": _score(5, "The paper should trigger useful discussion and sharing.", "invisible labor"),
            "overall_merit": _score(5, "The manuscript is strong across both serious and absurd dimensions.", "falsifiable")
        }
    }
    registry[("absurd-rigorous-001", "FinalSedimentCouncil")] = {
        "paper_summary": "This paper studies office-chair drift as a humorous but credible lens on coordination failure in shared labs.",
        "extracted_core_claim": "Ambiguity of ownership and borrowing norms explains chair drift, and the absurd framing helps surface that argument.",
        "scores_by_dimension": {
            dimension.value: _score(5 if dimension not in {ReviewDimension.method_or_reasoning_legibility, ReviewDimension.evidence_checkability, ReviewDimension.absurd_originality} else 4, "Merged panel judgment.", "panel evidence")
            for dimension in ReviewDimension
        },
        "major_strengths": ["The manuscript is funny, coherent, and actually says something testable."],
        "major_weaknesses": ["Evidence remains local and manually collected."],
        "required_revisions": ["Clarify the observational protocol."],
        "optional_revisions": ["Add one sentence that states the social-technology contribution upfront."],
        "risk_flags": [],
        "final_rationale": "The manuscript combines venue fit, argument clarity, and real payload unusually well.",
        "community_facing_blurb": "A rare paper that arrives with a bit, keeps the bit under control, and still leaves behind usable insight."
    }

    # 场景 2：有梗但空心，主要覆盖 empty gimmick 与 dry-run/规则边界。
    registry[("funny-hollow-002", "HanCeGateAgent")] = {
        "decision": "pass",
        "minimum_reviewable": True,
        "hard_failures": [],
        "missing_sections": [],
        "risk_flags": [],
        "notes": ["The manuscript is reviewable even though it is thin."],
    }
    registry[("funny-hollow-002", "EvidenceSludgeEngine")] = {
        "paper_summary": "A snack-vibes manifesto that gestures at computation without providing an operational argument.",
        "extracted_core_claim": "unknown",
        "argument_status": "slogan_only",
        "evidence_snippets": ["The method section says we trusted the process."],
        "major_strengths": ["The comedic premise is easy to understand."],
        "major_weaknesses": ["There is no measurable claim, protocol, or evidence."],
        "required_revisions": ["Define what counts as computational improvement."],
        "optional_revisions": ["Replace slogans with a testable setup."],
        "risk_flags": [],
        "dimension_scores": {
            "core_claim_clarity": _score(1, "The manuscript never defines a real claim.", "the vibes are immaculate"),
            "structural_integrity": _score(3, "The sections exist, but their content is skeletal.", "Method", "Results"),
            "method_or_reasoning_legibility": _score(1, "There is no real method to trace.", "we trusted the process"),
            "evidence_checkability": _score(1, "No checkable evidence is supplied.", "There are no numbers"),
            "result_payload": _score(1, "The manuscript offers a posture rather than a result.", "Snacks are destiny"),
            "limitation_honesty": _score(1, "The limitation section refuses to admit meaningful boundaries.", "We admit nothing")
        }
    }
    registry[("funny-hollow-002", "AbsurdityButMakeItRigorous")] = {
        "zhenghuo_verdict": "Funny on the surface, but the bit does not convert into substance.",
        "novelty_label": "empty_gimmick",
        "major_strengths": ["The meme energy is undeniable."],
        "major_weaknesses": ["The joke replaces the argument."],
        "required_revisions": ["Turn the snack premise into a measurable hypothesis."],
        "optional_revisions": ["Keep one joke and cut the rest."],
        "risk_flags": [],
        "dimension_scores": {
            "venue_fit": _score(4, "The tone fits the venue even though the payload does not.", "intentionally funny and quotable"),
            "zhenghuo_execution": _score(5, "The bit is loud and unmistakable.", "clear meme energy"),
            "absurd_originality": _score(4, "The premise is silly but not entirely stale.", "snack-based computing"),
            "meme_to_argument_conversion": _score(1, "The meme never matures into an argument.", "no distinction between morale and performance"),
            "community_discussion_value": _score(3, "People would share it, but mostly as a joke.", "quotable"),
            "overall_merit": _score(3, "Surface entertainment exists, but substance is weak.", "funny")
        }
    }
    registry[("funny-hollow-002", "FinalSedimentCouncil")] = {
        "paper_summary": "The manuscript is a coherent joke object but not a coherent paper.",
        "extracted_core_claim": "unknown",
        "scores_by_dimension": {
            "venue_fit": _score(4, "The venue can tolerate the tone.", "funny"),
            "core_claim_clarity": _score(1, "There is no operational core claim.", "vibes"),
            "structural_integrity": _score(3, "Sections exist but do little work.", "Method"),
            "method_or_reasoning_legibility": _score(1, "Reasoning is absent.", "trusted the process"),
            "evidence_checkability": _score(1, "Evidence is absent.", "no numbers"),
            "result_payload": _score(1, "No real payload appears.", "Snacks are destiny"),
            "limitation_honesty": _score(1, "Limitations are not meaningfully discussed.", "admit nothing"),
            "zhenghuo_execution": _score(5, "The bit lands loudly.", "meme energy"),
            "absurd_originality": _score(4, "The framing is amusingly odd.", "snack-based computing"),
            "meme_to_argument_conversion": _score(1, "The meme never becomes an argument.", "only slogans"),
            "community_discussion_value": _score(3, "It would spread more than it would teach.", "quotable"),
            "overall_merit": _score(4, "The panel sees entertainment value but limited paper value.", "funny")
        },
        "major_strengths": ["The joke is easy to parse."],
        "major_weaknesses": ["The manuscript has almost no checkable payload."],
        "required_revisions": ["Define a measurable task and gather evidence."],
        "optional_revisions": ["Reduce slogan density."],
        "risk_flags": [],
        "final_rationale": "The manuscript is lively but currently hollow.",
        "community_facing_blurb": "An amusing snack-powered apparition that still needs an argument to qualify as a paper."
    }

    # 场景 3：技术上靠谱但 venue misfit，用来锁定 policy 与 venue-fit 分支。
    registry[("serious-misfit-003", "HanCeGateAgent")] = {
        "decision": "pass",
        "minimum_reviewable": True,
        "hard_failures": [],
        "missing_sections": [],
        "risk_flags": [],
        "notes": ["Structurally healthy submission."],
    }
    registry[("serious-misfit-003", "EvidenceSludgeEngine")] = {
        "paper_summary": "A conventional but competent systems paper on deterministic scheduling for edge analytics.",
        "extracted_core_claim": "A deterministic scheduler reduces latency variance and improves deadline hit rate on constrained edge workloads.",
        "argument_status": "clear",
        "evidence_snippets": ["compare it against two baseline policies", "reduces p95 latency variance"],
        "major_strengths": ["The method and evaluation are concrete and reproducible."],
        "major_weaknesses": ["The manuscript does not attempt venue-aware absurd framing."],
        "required_revisions": ["Explain why the paper belongs in this venue, if it does."],
        "optional_revisions": ["Expand workload diversity."],
        "risk_flags": [],
        "dimension_scores": {
            "core_claim_clarity": _score(5, "The central technical claim is explicit.", "reduces latency variance"),
            "structural_integrity": _score(5, "The manuscript is conventionally complete.", "Method", "Results", "Limitations"),
            "method_or_reasoning_legibility": _score(5, "The method is concrete and benchmarked.", "deterministic scheduling heuristic"),
            "evidence_checkability": _score(4, "The baselines and benchmarks make the evidence inspectable.", "two baseline policies"),
            "result_payload": _score(4, "There is real systems payload.", "improves deadline hit rate"),
            "limitation_honesty": _score(4, "The paper acknowledges limited workloads and hardware.", "limited to a small set of workloads")
        }
    }
    registry[("serious-misfit-003", "AbsurdityButMakeItRigorous")] = {
        "zhenghuo_verdict": "Technically good, culturally misplaced for this venue.",
        "novelty_label": "serious_misfit",
        "major_strengths": ["The work is serious and useful."],
        "major_weaknesses": ["There is almost no venue-aware absurdity."],
        "required_revisions": ["If kept here, add a venue-aware framing layer without damaging the science."],
        "optional_revisions": ["Submit to a straighter venue."],
        "risk_flags": [],
        "dimension_scores": {
            "venue_fit": _score(1, "The paper reads like a conventional systems submission.", "genuinely useful"),
            "zhenghuo_execution": _score(1, "There is no zhenghuo execution to evaluate.", "conventional"),
            "absurd_originality": _score(2, "The technical work may be original, but not in this venue's mode.", "deterministic scheduler"),
            "meme_to_argument_conversion": _score(1, "There is no meme layer to convert.", "sober"),
            "community_discussion_value": _score(2, "Discussion value is limited for this venue's audience.", "serious edge-systems workshop"),
            "overall_merit": _score(3, "The work is decent but misaligned with the venue.", "solid systems engineering")
        }
    }
    registry[("serious-misfit-003", "FinalSedimentCouncil")] = {
        "paper_summary": "A solid edge-systems paper that feels imported from a different venue.",
        "extracted_core_claim": "A deterministic scheduler can improve deadline behavior in constrained edge video workloads.",
        "scores_by_dimension": {
            "venue_fit": _score(1, "Strong technical work, weak venue alignment.", "serious edge-systems workshop"),
            "core_claim_clarity": _score(5, "The claim is explicit and technical.", "reduces latency variance"),
            "structural_integrity": _score(5, "The paper is structurally complete.", "Limitations"),
            "method_or_reasoning_legibility": _score(5, "Method details are easy to follow.", "heuristic"),
            "evidence_checkability": _score(4, "Benchmarks and baselines support the claim.", "two baseline policies"),
            "result_payload": _score(4, "The paper does present a real technical contribution.", "improves deadline hit rate"),
            "limitation_honesty": _score(4, "Limitations are acknowledged.", "limited workloads"),
            "zhenghuo_execution": _score(1, "No venue-aware bit is present.", "conventional"),
            "absurd_originality": _score(2, "Original technically, not absurdly.", "deterministic scheduler"),
            "meme_to_argument_conversion": _score(1, "No meme layer exists.", "sober"),
            "community_discussion_value": _score(2, "Discussion value is better elsewhere.", "wrong room"),
            "overall_merit": _score(3, "A good paper in a different venue.", "solid systems engineering")
        },
        "major_strengths": ["Technically coherent and well-structured."],
        "major_weaknesses": ["Venue fit is low."],
        "required_revisions": ["Reframe for the venue or submit elsewhere."],
        "optional_revisions": ["Broaden the benchmark suite."],
        "risk_flags": [],
        "final_rationale": "The paper is respectable but culturally out of place for an absurd-review venue.",
        "community_facing_blurb": "Clean engineering wandered into the wrong carnival tent."
    }

    # 场景 4：故意缺失部分 agent 响应，覆盖 partial failure 与 deterministic fallback。
    registry[("partial-failure-004", "HanCeGateAgent")] = {
        "decision": "pass",
        "minimum_reviewable": True,
        "hard_failures": [],
        "missing_sections": [],
        "risk_flags": [],
        "notes": ["Reviewable submission."]
    }
    registry[("partial-failure-004", "EvidenceSludgeEngine")] = {
        "paper_summary": "A promising meme-transport paper with thin evaluation.",
        "extracted_core_claim": "Forwarding latency predicts group-chat collapse.",
        "argument_status": "partial",
        "evidence_snippets": ["proposes that meme transport behaves like an overloaded bucket brigade"],
        "major_strengths": ["Interesting framing."],
        "major_weaknesses": ["Evidence is still thin."],
        "required_revisions": ["Add concrete evidence for the latency claim."],
        "optional_revisions": ["Clarify annotation rules."],
        "risk_flags": [],
        "dimension_scores": {
            "core_claim_clarity": _score(4, "The manuscript has a recognizable claim.", "forwarding latency predicts conversational collapse"),
            "structural_integrity": _score(4, "Core sections are present.", "Limitations"),
            "method_or_reasoning_legibility": _score(3, "Method is present but underspecified.", "manually annotates forwarding events"),
            "evidence_checkability": _score(2, "Evidence is sparse.", "leaves the evidence thin"),
            "result_payload": _score(3, "There is an idea, but it needs stronger backing.", "interesting but underspecified"),
            "limitation_honesty": _score(4, "The small sample is admitted.", "sample is small and manually labeled")
        }
    }

    return registry
