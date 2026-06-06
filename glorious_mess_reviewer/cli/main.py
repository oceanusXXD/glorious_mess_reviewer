"""Command line entrypoint for the glorious mess reviewer."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Sequence, TextIO

import uvicorn
from pydantic import ValidationError

from glorious_mess_reviewer.benchmark import (
    BenchmarkRunOptions,
    render_benchmark_markdown,
    run_benchmark_suite,
)
from glorious_mess_reviewer.config import Settings, get_settings, setup_logging
from glorious_mess_reviewer.display import (
    FERMENTATION_QUEUE_LANES,
    FERMENTATION_QUEUE_SORT_KEYS,
    build_fermentation_queue_overview,
    build_fermentation_queue_summaries,
    build_review_display,
)
from glorious_mess_reviewer.providers import ProviderError
from glorious_mess_reviewer.report import render_review_markdown
from glorious_mess_reviewer.runtime import build_provider, build_review_service, build_store
from glorious_mess_reviewer.schemas import ManuscriptInput, VenuePresetName, VenueProfile, WorkflowSessionStatus


def _build_petri_dish_starter_payload(manuscript_id: str) -> dict[str, object]:
    """Return a reviewable starter payload for first-time CLI/API users."""

    petri_dish_seed = {
        "manuscript_id": manuscript_id,
        "title": "On the Queueing Theory of Shared Microwave Diplomacy",
        "abstract": (
            "This sample studies a ridiculous workplace ritual as if it were a serious coordination problem. "
            "It argues that microwave queues expose informal governance, invisible labor, and the social cost "
            "of pretending a shared resource has no owner."
        ),
        "body": (
            "Introduction\n"
            "Shared office microwaves look too trivial to deserve a paper, which is precisely why they are useful. "
            "When lunch traffic peaks, people invent norms, punishments, and folklore around a device that nobody "
            "formally governs. This manuscript treats that small absurdity as a proxy for larger coordination failures.\n\n"
            "Method\n"
            "Observe one shared kitchen over five workdays. Record queue length, abandoned containers, apology notes, "
            "passive-aggressive sticky notes, and the number of times someone says they are just reheating soup. "
            "Separate direct observations from interpretation, and keep a small log of ambiguous cases so the argument "
            "does not pretend to be more precise than the evidence allows.\n\n"
            "Results\n"
            "The busiest window is not simply the period with the most people. It is the moment when ownership becomes "
            "unclear: one person leaves food inside, another person waits, and a third person decides the queue has become "
            "a moral philosophy seminar. Sticky-note escalation correlates with containers that remain unattended for more "
            "than three minutes. The strongest pattern is not culinary preference but the absence of an agreed recovery rule.\n\n"
            "Discussion\n"
            "The joke works only because the problem is recognizable. A microwave is not important, but the governance "
            "vacuum around it is. The paper should make readers laugh and then notice that many institutional systems are "
            "maintained by informal patience, embarrassment, and tiny rituals nobody wrote down.\n\n"
            "Conclusion\n"
            "Microwave diplomacy is a comic lens for resource governance. The premise is intentionally unserious, but the "
            "claim is concrete: unmanaged shared infrastructure turns etiquette into hidden labor.\n\n"
            "Limitations\n"
            "The sample is local, short, and manually observed. The study cannot prove causality, and it may overread a "
            "single workplace culture. A stronger version would compare multiple kitchens and include a clearer annotation "
            "rubric for ambiguous social cues."
        ),
        "authors": ["Example Operator"],
        "references": [
            "Kitchen Systems Quarterly 2026",
            "Proceedings of Informal Infrastructure Studies 2025",
        ],
        "metadata": {
            "source": "glorious_mess_reviewer new-manuscript",
            "intended_first_command": "glorious_mess_reviewer review --dry-run",
            "submission_track": "rigorous_argument",
            "routing_stage": "petri_dish",
            "ai_use_statement": "No generated text was used beyond this starter template.",
            "safety_notice": "No operational harm instructions, personal data, or targeted harassment are included.",
        },
    }
    return ManuscriptInput.model_validate(petri_dish_seed).model_dump(mode="json")


def _build_latrine_readiness_payload(settings: Settings) -> dict[str, object]:
    """Build a local readiness report without sending any provider request."""

    inspection_stalls: list[dict[str, str]] = []
    next_actions: list[str] = []

    try:
        store = build_store(settings)
        database_ok = store.healthcheck()
        inspection_stalls.append(
            {
                "name": "database",
                "status": "pass" if database_ok else "fail",
                "message": (
                    f"SQLite store is reachable at {settings.database_path}."
                    if database_ok
                    else f"SQLite store could not answer a health check at {settings.database_path}."
                ),
            }
        )
    except Exception as exc:
        database_ok = False
        inspection_stalls.append(
            {
                "name": "database",
                "status": "fail",
                "message": f"SQLite store could not be initialized: {exc}",
            }
        )

    try:
        provider = build_provider(settings, log_degraded=False)
        provider_configured = provider is not None
        if provider_configured:
            provider_message = f"{settings.provider_backend} provider is configured for model {settings.default_model}."
            provider_status = "pass"
        elif settings.provider_backend == "mock":
            provider_message = "Mock backend is test-only unless a fixture-backed MockLLMProvider is injected by tests."
            provider_status = "warn"
            next_actions.append("Use dry-run locally, or set GLORIOUS_MESS_PROVIDER_BACKEND=openai for real reviews.")
        else:
            provider_message = (
                "OpenAI provider is not configured. Set OPENAI_API_KEY or GLORIOUS_MESS_OPENAI_API_KEY "
                "before running full review, risk-audit, or venue-fit-audit."
            )
            provider_status = "warn"
            next_actions.append("Set OPENAI_API_KEY or GLORIOUS_MESS_OPENAI_API_KEY for provider-backed workflows.")
    except Exception as exc:
        provider_configured = False
        provider_message = f"Provider diagnostic failed before any model request was sent: {exc}"
        provider_status = "fail"
        next_actions.append("Fix provider configuration before running provider-backed workflows.")
    inspection_stalls.append({"name": "provider", "status": provider_status, "message": provider_message})

    dry_run_ready = database_ok
    full_review_ready = database_ok and provider_configured
    if not database_ok:
        next_actions.append("Fix GLORIOUS_MESS_DATABASE_PATH or filesystem permissions before running any workflow.")
    if dry_run_ready and not full_review_ready:
        next_actions.append("Run `glorious_mess_reviewer review --dry-run` to validate manuscripts without a provider.")
    if full_review_ready:
        next_actions.append("Run a provider-backed `review`, `risk-audit`, or `venue-fit-audit` command.")

    status = "ok" if full_review_ready else "degraded" if dry_run_ready else "error"
    return {
        "status": status,
        "app_name": settings.app_name,
        "environment": settings.environment,
        "provider_backend": settings.provider_backend,
        "default_model": settings.default_model,
        "database_path": str(settings.database_path),
        "database_ok": database_ok,
        "provider_configured": provider_configured,
        "dry_run_ready": dry_run_ready,
        "full_review_ready": full_review_ready,
        "checks": inspection_stalls,
        "next_actions": next_actions,
    }


def _fermentation_queue_limit_arg(value: str) -> int:
    """Parse a public list limit consistently with the API query bounds."""

    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("limit must be an integer between 1 and 100") from exc
    if parsed < 1 or parsed > 100:
        raise argparse.ArgumentTypeError("limit must be between 1 and 100")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""

    parser = argparse.ArgumentParser(description="Run the glorious mess reviewer locally.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    review_parser = subparsers.add_parser("review", help="Review a manuscript JSON file.")
    review_parser.add_argument("--input", required=True, help="Path to a manuscript JSON file.")
    review_parser.add_argument("--dry-run", action="store_true", help="Run only deterministic precheck.")
    review_parser.add_argument(
        "--output",
        help="Optional path for saving the JSON result.",
    )
    review_parser.add_argument(
        "--report-output",
        help="Optional path for saving a Markdown intake report from a full review.",
    )
    review_parser.add_argument(
        "--preset",
        choices=[preset.value for preset in VenuePresetName],
        help="Optional built-in screening preset to apply on top of the manuscript.",
    )
    risk_audit_parser = subparsers.add_parser("risk-audit", help="Run the lightweight intake risk-audit workflow.")
    risk_audit_parser.add_argument("--input", required=True, help="Path to a manuscript JSON file.")
    risk_audit_parser.add_argument(
        "--output",
        help="Optional path for saving the JSON result.",
    )
    risk_audit_parser.add_argument(
        "--preset",
        choices=[preset.value for preset in VenuePresetName],
        help="Optional built-in screening preset to apply on top of the manuscript.",
    )
    venue_fit_audit_parser = subparsers.add_parser(
        "venue-fit-audit",
        help="Run the lightweight venue-fit audit workflow.",
    )
    venue_fit_audit_parser.add_argument("--input", required=True, help="Path to a manuscript JSON file.")
    venue_fit_audit_parser.add_argument(
        "--output",
        help="Optional path for saving the JSON result.",
    )
    venue_fit_audit_parser.add_argument(
        "--preset",
        choices=[preset.value for preset in VenuePresetName],
        help="Optional built-in screening preset to apply on top of the manuscript.",
    )
    show_venue_parser = subparsers.add_parser("show-default-venue", help="Print a built-in venue profile as JSON.")
    show_venue_parser.add_argument(
        "--preset",
        choices=[preset.value for preset in VenuePresetName],
        help="Optional built-in screening preset name.",
    )
    show_review_parser = subparsers.add_parser("show-review", help="Print one persisted review record as JSON.")
    show_review_parser.add_argument("--run-id", required=True, help="Persisted run identifier.")
    show_review_display_parser = subparsers.add_parser(
        "show-review-display",
        help="Print one persisted review as a dashboard-friendly JSON projection.",
    )
    show_review_display_parser.add_argument("--run-id", required=True, help="Persisted run identifier.")
    show_workflow_parser = subparsers.add_parser("show-workflow", help="Print one persisted workflow session as JSON.")
    show_workflow_parser.add_argument("--session-id", required=True, help="Persisted workflow session identifier.")
    list_reviews_parser = subparsers.add_parser("list-reviews", help="List persisted review summaries as JSON.")
    list_reviews_parser.add_argument("--manuscript-id", help="Optional manuscript identifier filter.")
    list_reviews_parser.add_argument(
        "--limit", type=_fermentation_queue_limit_arg, default=20, help="Maximum number of rows to return."
    )
    list_review_displays_parser = subparsers.add_parser(
        "list-review-displays",
        help="List persisted reviews as dashboard queue summaries.",
    )
    list_review_displays_parser.add_argument("--manuscript-id", help="Optional manuscript identifier filter.")
    list_review_displays_parser.add_argument(
        "--lane",
        choices=FERMENTATION_QUEUE_LANES,
        help="Optional triage lane filter.",
    )
    list_review_displays_parser.add_argument(
        "--sort",
        choices=FERMENTATION_QUEUE_SORT_KEYS,
        default="created_at",
        help="Queue summary ordering.",
    )
    list_review_displays_parser.add_argument(
        "--limit", type=_fermentation_queue_limit_arg, default=20, help="Maximum number of rows to return."
    )
    review_display_overview_parser = subparsers.add_parser(
        "review-display-overview",
        help="Summarize recent dashboard queue pressure as JSON.",
    )
    review_display_overview_parser.add_argument("--manuscript-id", help="Optional manuscript identifier filter.")
    review_display_overview_parser.add_argument(
        "--limit", type=_fermentation_queue_limit_arg, default=100, help="Maximum number of recent rows to summarize."
    )
    subparsers.add_parser(
        "list-workflows",
        help="List registered workflow metadata as JSON.",
        description="List registered workflow metadata as JSON.",
    )
    list_workflow_sessions_parser = subparsers.add_parser(
        "list-workflow-sessions",
        help="List persisted workflow session summaries as JSON.",
    )
    list_workflow_sessions_parser.add_argument("--workflow-id", help="Optional workflow identifier filter.")
    list_workflow_sessions_parser.add_argument("--manuscript-id", help="Optional manuscript identifier filter.")
    list_workflow_sessions_parser.add_argument(
        "--status",
        choices=[status.value for status in WorkflowSessionStatus],
        help="Optional workflow session status filter.",
    )
    list_workflow_sessions_parser.add_argument(
        "--limit", type=_fermentation_queue_limit_arg, default=20, help="Maximum number of rows to return."
    )
    doctor_parser = subparsers.add_parser("doctor", help="Check local setup readiness as JSON.")
    doctor_parser.add_argument(
        "--require-provider",
        action="store_true",
        help="Exit non-zero unless provider-backed workflows are ready.",
    )
    new_manuscript_parser = subparsers.add_parser(
        "new-manuscript",
        help="Print a reviewable starter ManuscriptInput JSON payload.",
    )
    new_manuscript_parser.add_argument(
        "--manuscript-id",
        default="sample-microwave-diplomacy-001",
        help="Manuscript identifier to place in the generated payload.",
    )
    new_manuscript_parser.add_argument(
        "--output",
        help="Optional path for saving the generated JSON payload.",
    )
    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Run the benchmark suite and print a JSON report.",
    )
    benchmark_parser.add_argument(
        "--suite",
        default="docs/examples/benchmark-suite.json",
        help="Path to a benchmark suite JSON descriptor.",
    )
    benchmark_parser.add_argument(
        "--mode",
        choices=["dry-run", "review"],
        default="dry-run",
        help="Run deterministic dry-run checks or provider-backed full review.",
    )
    benchmark_parser.add_argument(
        "--limit",
        type=_fermentation_queue_limit_arg,
        help="Maximum number of benchmark cases to run.",
    )
    benchmark_parser.add_argument(
        "--output",
        help="Optional path for saving the JSON benchmark report.",
    )
    benchmark_parser.add_argument(
        "--markdown-output",
        help="Optional path for saving a Markdown benchmark report.",
    )
    serve_parser = subparsers.add_parser("serve", help="Run the HTTP API locally.")
    serve_parser.add_argument("--host", default=None)
    serve_parser.add_argument("--port", type=int, default=None)
    return parser


def _print_json(payload: object, *, stream: TextIO) -> None:
    """Render a JSON payload to the requested output stream."""

    print(json.dumps(payload, ensure_ascii=False, indent=2), file=stream)


def _print_cli_error(
    *,
    error_code: str,
    message: str,
    stream: TextIO,
    details: dict[str, object] | None = None,
) -> None:
    """Render a stable CLI error envelope to stderr."""

    payload: dict[str, object] = {"error_code": error_code, "message": message}
    if details is not None:
        payload["details"] = details
    print(json.dumps(payload, ensure_ascii=False), file=stream)


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Parse CLI arguments, execute the requested command, and return an exit code."""

    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    resolved_settings = settings or get_settings()
    setup_logging(resolved_settings)
    out = stdout or sys.stdout
    err = stderr or sys.stderr

    if args.command in {"review", "risk-audit", "venue-fit-audit"}:
        if args.command == "review" and getattr(args, "dry_run", False) and getattr(args, "report_output", None):
            _print_cli_error(
                error_code="report_requires_full_review",
                message="--report-output is only available for provider-backed full review, not review --dry-run.",
                stream=err,
                details={"path": args.report_output},
            )
            return 1
        try:
            manuscript_path = Path(args.input)
            manuscript = ManuscriptInput.model_validate_json(manuscript_path.read_text(encoding="utf-8"))
            if args.preset:
                manuscript.venue_profile = VenueProfile.from_builtin_preset(args.preset)
            store = build_store(resolved_settings)
            is_dry_run = getattr(args, "dry_run", False)
            provider = None if is_dry_run else build_provider(resolved_settings, log_degraded=False)
            reviewer = build_review_service(
                resolved_settings,
                provider=provider,
                store=store,
            )
            result = asyncio.run(
                reviewer.dry_run(manuscript)
                if is_dry_run
                else reviewer.review(manuscript)
                if args.command == "review"
                else reviewer.risk_audit(manuscript)
                if args.command == "risk-audit"
                else reviewer.venue_fit_audit(manuscript)
            )
        except FileNotFoundError as exc:
            _print_cli_error(
                error_code="input_not_found",
                message=f"Input manuscript file was not found: {args.input}",
                stream=err,
                details={"path": str(exc.filename or args.input)},
            )
            return 1
        except OSError as exc:
            _print_cli_error(
                error_code="input_read_failed",
                message=f"Could not read input manuscript file: {exc}",
                stream=err,
                details={"path": args.input},
            )
            return 1
        except ValidationError as exc:
            _print_cli_error(
                error_code="invalid_input",
                message="Input manuscript JSON failed schema validation.",
                stream=err,
                details={"errors": exc.errors()},
            )
            return 1
        except ProviderError as exc:
            _print_cli_error(error_code="provider_failure", message=str(exc), stream=err)
            return 2

        rendered = json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2)
        if args.output:
            try:
                Path(args.output).write_text(rendered, encoding="utf-8")
            except OSError as exc:
                _print_cli_error(
                    error_code="output_write_failed",
                    message=f"Could not write review result: {exc}",
                    stream=err,
                    details={"path": args.output},
                )
                return 1
        if args.command == "review" and getattr(args, "report_output", None):
            try:
                Path(args.report_output).write_text(
                    render_review_markdown(result, manuscript=manuscript),
                    encoding="utf-8",
                )
            except OSError as exc:
                _print_cli_error(
                    error_code="output_write_failed",
                    message=f"Could not write Markdown review report: {exc}",
                    stream=err,
                    details={"path": args.report_output},
                )
                return 1
        print(rendered, file=out)
        return 0

    if args.command == "show-default-venue":
        _print_json(
            VenueProfile.from_builtin_preset(
                args.preset,
                default_minimum_reviewable_characters=resolved_settings.minimum_reviewable_characters,
            ).model_dump(mode="json"),
            stream=out,
        )
        return 0

    if args.command == "show-review":
        record = build_store(resolved_settings).get_review(args.run_id)
        if record is None:
            _print_cli_error(
                error_code="review_not_found",
                message=f"No persisted review found for run_id '{args.run_id}'.",
                stream=err,
            )
            return 1
        _print_json(record.model_dump(mode="json"), stream=out)
        return 0

    if args.command == "show-review-display":
        record = build_store(resolved_settings).get_review(args.run_id)
        if record is None:
            _print_cli_error(
                error_code="review_not_found",
                message=f"No persisted review found for run_id '{args.run_id}'.",
                stream=err,
            )
            return 1
        _print_json(build_review_display(record).model_dump(mode="json"), stream=out)
        return 0

    if args.command == "show-workflow":
        record = build_store(resolved_settings).get_workflow_session(args.session_id)
        if record is None:
            _print_cli_error(
                error_code="workflow_not_found",
                message=f"No persisted workflow session found for session_id '{args.session_id}'.",
                stream=err,
            )
            return 1
        _print_json(record.model_dump(mode="json"), stream=out)
        return 0

    if args.command == "list-reviews":
        summaries = build_store(resolved_settings).list_reviews(
            manuscript_id=args.manuscript_id,
            limit=args.limit,
        )
        _print_json([item.model_dump(mode="json") for item in summaries], stream=out)
        return 0

    if args.command == "list-review-displays":
        store = build_store(resolved_settings)
        summaries = store.list_reviews(
            manuscript_id=args.manuscript_id,
            limit=100,
        )
        records = [store.get_review(summary.run_id) for summary in summaries]
        _print_json(
            [
                item.model_dump(mode="json")
                for item in build_fermentation_queue_summaries(
                    [record for record in records if record is not None],
                    lane=args.lane,
                    sort=args.sort,
                    limit=args.limit,
                )
            ],
            stream=out,
        )
        return 0

    if args.command == "review-display-overview":
        store = build_store(resolved_settings)
        summaries = store.list_reviews(
            manuscript_id=args.manuscript_id,
            limit=args.limit,
        )
        records = [store.get_review(summary.run_id) for summary in summaries]
        overview = build_fermentation_queue_overview([record for record in records if record is not None])
        _print_json(overview.model_dump(mode="json"), stream=out)
        return 0

    if args.command == "list-workflows":
        reviewer = build_review_service(resolved_settings, provider=None)
        _print_json([item.model_dump(mode="json") for item in reviewer.list_workflows()], stream=out)
        return 0

    if args.command == "list-workflow-sessions":
        reviewer = build_review_service(resolved_settings, provider=None)
        summaries = reviewer.list_workflow_sessions(
            workflow_id=args.workflow_id,
            manuscript_id=args.manuscript_id,
            status=WorkflowSessionStatus(args.status) if args.status else None,
            limit=args.limit,
        )
        _print_json([item.model_dump(mode="json") for item in summaries], stream=out)
        return 0

    if args.command == "doctor":
        payload = _build_latrine_readiness_payload(resolved_settings)
        _print_json(payload, stream=out)
        if payload["status"] == "error":
            return 1
        if args.require_provider and not payload["full_review_ready"]:
            return 1
        return 0

    if args.command == "new-manuscript":
        try:
            payload = _build_petri_dish_starter_payload(args.manuscript_id)
        except ValidationError as exc:
            _print_cli_error(
                error_code="invalid_manuscript_id",
                message="Generated manuscript payload failed validation. Provide a non-blank --manuscript-id.",
                stream=err,
                details={"errors": exc.errors()},
            )
            return 1
        rendered = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.output:
            try:
                Path(args.output).write_text(rendered, encoding="utf-8")
            except OSError as exc:
                _print_cli_error(
                    error_code="output_write_failed",
                    message=f"Could not write generated manuscript payload: {exc}",
                    stream=err,
                    details={"path": args.output},
                )
                return 1
        print(rendered, file=out)
        return 0

    if args.command == "benchmark":
        try:
            report = run_benchmark_suite(
                settings=resolved_settings,
                suite_path=Path(args.suite),
                options=BenchmarkRunOptions(mode=args.mode, limit=args.limit),
            )
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            _print_cli_error(
                error_code="invalid_benchmark_suite",
                message=f"Could not load benchmark suite: {exc}",
                stream=err,
                details={"path": args.suite},
            )
            return 1
        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        if args.output:
            try:
                Path(args.output).write_text(rendered, encoding="utf-8")
            except OSError as exc:
                _print_cli_error(
                    error_code="output_write_failed",
                    message=f"Could not write benchmark JSON report: {exc}",
                    stream=err,
                    details={"path": args.output},
                )
                return 1
        if args.markdown_output:
            try:
                Path(args.markdown_output).write_text(render_benchmark_markdown(report), encoding="utf-8")
            except OSError as exc:
                _print_cli_error(
                    error_code="output_write_failed",
                    message=f"Could not write benchmark Markdown report: {exc}",
                    stream=err,
                    details={"path": args.markdown_output},
                )
                return 1
        print(rendered, file=out)
        if args.mode == "review" and report["summary"]["ok_cases"] == 0:
            return 2
        return 0

    if args.command == "serve":
        uvicorn.run(
            "glorious_mess_reviewer.api.app:create_app",
            factory=True,
            host=args.host or resolved_settings.host,
            port=args.port or resolved_settings.port,
        )
        return 0

    return 0


def main() -> None:
    """Parse CLI arguments and execute the requested command."""

    exit_code = run_cli()
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
