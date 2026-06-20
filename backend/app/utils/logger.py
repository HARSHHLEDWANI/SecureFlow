"""Centralised application logging.

Provides :func:`get_logger` returning a module-scoped logger configured once
with a consistent format and the level from application settings.
"""
from __future__ import annotations

import logging
import sys

from app.config import get_settings

_CONFIGURED = False


def _configure_root() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )

    root = logging.getLogger("secureflow")
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)
    root.propagate = False

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger under the ``secureflow`` root."""
    _configure_root()
    return logging.getLogger(f"secureflow.{name}")
