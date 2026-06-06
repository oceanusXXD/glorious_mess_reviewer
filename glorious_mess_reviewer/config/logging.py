"""Structured logging setup for service and CLI flows."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from glorious_mess_reviewer.config.settings import Settings


class JsonLogFormatter(logging.Formatter):
    """Render log records as searchable JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "event"):
            payload["event"] = record.event
        if hasattr(record, "run_id"):
            payload["run_id"] = record.run_id
        if hasattr(record, "agent_name"):
            payload["agent_name"] = record.agent_name
        if hasattr(record, "prompt_version"):
            payload["prompt_version"] = record.prompt_version
        if hasattr(record, "status"):
            payload["status"] = record.status
        if hasattr(record, "details"):
            payload["details"] = record.details
        return json.dumps(payload, ensure_ascii=True)


def setup_logging(settings: Settings) -> None:
    """Configure root logging with a JSON formatter."""

    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    # 先清空 root handlers，避免 API/CLI 在同一进程里重复初始化时把同一条日志输出多次。
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
