# Security Policy

glorious_mess_reviewer can process draft manuscripts and store them in SQLite.
Treat inputs, prompt text, raw agent outputs, and workflow artifacts as potentially
sensitive.

## Reporting Security Issues

Do not open a public issue with:

- API keys, credentials, or `.env` contents
- private manuscripts or reviewer notes
- exploit details that would enable abuse
- personally identifying information from submissions

Use the repository host's private security advisory flow when available, or contact
the maintainers through a private channel before sharing details publicly.

## Supported Scope

Security reports are in scope when they affect:

- secret handling
- unsafe persistence or logging defaults
- API/CLI behavior that exposes sensitive payloads unexpectedly
- dependency or packaging risks
- workflow behavior that rewards illegal, abusive, or exploitative content

## Operator Guidance

- Keep `GLORIOUS_MESS_LOG_PROMPT_TEXT=false` unless prompt logging is explicitly needed.
- Set `GLORIOUS_MESS_STORE_RAW_AGENT_OUTPUTS=false` when raw panel payloads should not be retained.
- Store `GLORIOUS_MESS_DATABASE_PATH` in a controlled directory.
- Remove local SQLite files before sharing repro archives.
- Use sanitized fixtures in bug reports.
