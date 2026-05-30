import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from flask import g, request


def init_logging(app) -> None:
    log_level = getattr(logging, app.config["LOG_LEVEL"].upper(), logging.INFO)
    log_path = Path(app.config["LOG_FILE_PATH"])
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=app.config["LOG_MAX_BYTES"],
        backupCount=app.config["LOG_BACKUP_COUNT"],
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(log_level)

    app.logger.handlers.clear()
    app.logger.addHandler(file_handler)
    app.logger.addHandler(stream_handler)
    app.logger.setLevel(log_level)
    app.logger.propagate = False

    logging.getLogger("ai_calender").handlers.clear()
    logging.getLogger("ai_calender").addHandler(file_handler)
    logging.getLogger("ai_calender").addHandler(stream_handler)
    logging.getLogger("ai_calender").setLevel(log_level)
    logging.getLogger("ai_calender").propagate = False

    app.before_request(_start_request_log)
    app.after_request(_finish_request_log)
    app.teardown_request(_log_request_exception)


def get_logger(name: str):
    return logging.getLogger(f"ai_calender.{name}")


def _start_request_log() -> None:
    g.request_id = request.headers.get("X-Request-ID", str(uuid4()))
    g.request_started_at = perf_counter()
    get_logger("request").info(
        "request_started request_id=%s method=%s path=%s",
        g.request_id,
        request.method,
        request.path,
    )


def _finish_request_log(response):
    duration_ms = int((perf_counter() - g.get("request_started_at", perf_counter())) * 1000)
    get_logger("request").info(
        "request_finished request_id=%s method=%s path=%s status=%s duration_ms=%s",
        g.get("request_id"),
        request.method,
        request.path,
        response.status_code,
        duration_ms,
    )
    response.headers["X-Request-ID"] = g.get("request_id", "")

    return response


def _log_request_exception(error) -> None:
    if error is None:
        return

    get_logger("request").exception(
        "request_failed request_id=%s method=%s path=%s",
        g.get("request_id"),
        request.method,
        request.path,
    )
