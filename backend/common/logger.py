"""
GridMind — Centralized Logging
================================
Provides a single, pre-configured logger for the entire application.
All modules use this instead of print() or their own logging setup.

Usage:
    from backend.common.logger import logger
    logger.info("Simulation started")
    logger.warning("Battery SOC below threshold")
    logger.error("Agent failed", extra={"agent": "risk_forecast"})
"""

import sys
import logging
from pathlib import Path


def _setup_logger() -> logging.Logger:
    """
    Creates and configures the GridMind application logger.
    Reads LOG_LEVEL and LOG_FILE from environment (via config),
    but does lazy import to avoid circular dependencies.
    """
    import os
    from dotenv import load_dotenv

    # Load env directly here to avoid circular import with config
    project_root = Path(__file__).resolve().parent.parent.parent
    load_dotenv(project_root / ".env")

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("LOG_FILE", str(project_root / "data_storage" / "gridmind.log"))

    # Ensure log directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Create logger
    _logger = logging.getLogger("gridmind")
    _logger.setLevel(getattr(logging, log_level, logging.INFO))
    _logger.propagate = False

    # Clear existing handlers to avoid duplicates on reload
    _logger.handlers.clear()

    # ── Format ────────────────────────────────────────────────────────
    # Use an ASCII-only separator so console output never crashes on
    # Windows consoles using legacy encodings (e.g. cp1252).
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Console Handler ──────────────────────────────────────────────
    console_handler = logging.StreamHandler(
        open(sys.stdout.fileno(), mode="w", encoding="utf-8", errors="replace", closefd=False)
    )
    console_handler.setLevel(getattr(logging, log_level, logging.INFO))
    console_handler.setFormatter(formatter)
    _logger.addHandler(console_handler)

    # ── File Handler ─────────────────────────────────────────────────
    try:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # File captures everything
        file_handler.setFormatter(formatter)
        _logger.addHandler(file_handler)
    except (OSError, PermissionError):
        _logger.warning(f"Could not create log file at {log_file}")

    return _logger


# ---------------------------------------------------------------------------
# Singleton logger — import this everywhere
# ---------------------------------------------------------------------------
logger = _setup_logger()


def get_module_logger(module_name: str) -> logging.Logger:
    """
    Get a child logger for a specific module.
    This preserves the parent's handlers while adding module context.

    Usage:
        from backend.common.logger import get_module_logger
        log = get_module_logger("agents.risk_forecast")
        log.info("Risk score calculated: 78")
    """
    return logger.getChild(module_name)
