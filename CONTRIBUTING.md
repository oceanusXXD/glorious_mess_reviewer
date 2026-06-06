# Contributing

Thanks for improving glorious_mess_reviewer. This project is a Python package,
CLI, FastAPI service, and workflow runtime, so useful contributions usually touch
code, tests, and docs together.

## Local Setup

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m pytest -q
```

Use `glorious_mess_reviewer doctor` to check local database and provider readiness.
`review --dry-run` does not need an API key.

## Contribution Areas

- Screening workflows and runtime persistence
- S.H.I.T / 构石 venue profiles, presets, and rubric logic
- Prompt templates and structured-output contracts
- CLI and FastAPI usability
- Documentation, examples, and operator onboarding
- Test fixtures and golden regression coverage

## Change Expectations

- Keep public Pydantic contracts stable unless the change explicitly requires a contract update.
- Add or update tests for behavior changes.
- Update docs when changing API routes, CLI arguments, settings, presets, workflow IDs, or output fields.
- Do not commit local SQLite databases, `.env` files, API keys, private manuscripts, or generated credentials.
- Use sanitized examples in fixtures and docs.

## Pull Request Checklist

- [ ] The change has a clear user or maintainer scenario.
- [ ] Tests cover the changed behavior.
- [ ] `python -m pytest -q` passes locally.
- [ ] Docs and examples are updated when public behavior changes.
- [ ] New safety/risk logic is conservative and covered by tests.
- [ ] No sensitive manuscript content or secrets are committed.

## Design Notes

The main control boundaries are:

- `schemas/`: public contracts
- `workflows/`: node order and workflow IDs
- `orchestrator/`: business logic, precheck, agent fallback, projection
- `scoring/`: recommendation and rule caps
- `runtime/`: workflow execution and persistence trace
- `storage/`: SQLite schema and query APIs

When in doubt, keep the change small and make the contract impact explicit.
