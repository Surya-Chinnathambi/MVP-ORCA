#!/usr/bin/env python3
"""
Shared utilities for environment loading and console-safe output.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable

DEFAULT_RETRY_BASE_DELAY_S = 15.0
DEFAULT_MAX_RETRIES = 4
MAX_RETRY_DELAY_S = 120.0
IMAGE_ANALYSIS_TIMEOUT_S = 45.0


def standard_env_candidates(anchor: Path | None = None) -> list[Path]:
    """Return the standard .env lookup locations for dev and packaged runs."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
    else:
        exe_dir = None

    base_dir = anchor.parent if anchor else Path.cwd()
    candidates = [
        exe_dir / ".env" if exe_dir else None,
        base_dir / ".env",
        Path.cwd() / ".env",
    ]
    return [candidate for candidate in candidates if candidate is not None]


def load_env_file(anchor: Path | None = None, extra_candidates: Iterable[Path] | None = None) -> Path | None:
    """Load key=value pairs from the first available .env file into os.environ."""
    candidates = []
    if extra_candidates:
        candidates.extend(Path(candidate) for candidate in extra_candidates if candidate)
    candidates.extend(standard_env_candidates(anchor))

    for candidate in candidates:
        if not candidate.exists():
            continue
        with open(candidate, encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())
        return candidate
    return None


def configure_utf8_output():
    """Best-effort UTF-8 stdio configuration for Windows terminals."""
    if sys.platform != "win32":
        return
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
