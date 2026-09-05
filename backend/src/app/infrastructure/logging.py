"""Application logging, routed through uvicorn's handlers."""

import logging


def configure_logging() -> None:
    """Give the `app` logger tree uvicorn's handlers and level, so application
    logs share the server's format. A no-op outside uvicorn, where the root
    logger's own configuration applies instead."""
    uvicorn_logger = logging.getLogger("uvicorn.error")
    handlers = _inherited_handlers(uvicorn_logger)
    if not handlers:
        return

    app_logger = logging.getLogger("app")
    app_logger.handlers = handlers
    app_logger.setLevel(uvicorn_logger.getEffectiveLevel())
    app_logger.propagate = False


def _inherited_handlers(logger: logging.Logger) -> list[logging.Handler]:
    """The handlers a record logged here would actually reach. Uvicorn attaches
    none to `uvicorn.error` itself and lets it propagate to `uvicorn`."""
    current: logging.Logger | None = logger
    while current is not None:
        if current.handlers:
            return current.handlers
        current = current.parent if current.propagate else None
    return []
