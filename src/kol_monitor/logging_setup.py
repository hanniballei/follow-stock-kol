from __future__ import annotations

import logging
from pathlib import Path

from rich.logging import RichHandler


def setup(level: str = "INFO", log_file: str | Path = "kol_monitor.log", rich_console: bool = True) -> None:
    """Configure console and file logging once."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    if rich_console:
        root.addHandler(RichHandler(rich_tracebacks=True, markup=False))
    else:
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        root.addHandler(stream)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
