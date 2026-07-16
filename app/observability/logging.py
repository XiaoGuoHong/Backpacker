import json
import logging
import sys
import time
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

logger = logging.getLogger("smartvoyage")
_configured = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": round(time.time(), 3),
            "level": record.levelname,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "task_id": getattr(record, "task_id", None),
            "agent_type": getattr(record, "agent_type", None),
            "tool_type": getattr(record, "tool_type", None),
            "status": getattr(record, "status", None),
            "duration_ms": getattr(record, "duration_ms", None),
            "error_code": getattr(record, "error_code", None),
        }
        return json.dumps({k: v for k, v in payload.items() if v is not None}, ensure_ascii=False)


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    _configured = True


def log_event(msg: str, **fields) -> None:
    extra = {k: fields.get(k) for k in (
        "request_id", "task_id", "agent_type", "tool_type", "status", "duration_ms", "error_code"
    )}
    extra["request_id"] = extra["request_id"] or request_id_var.get()
    logger.info(msg, extra=extra)
