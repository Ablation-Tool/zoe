"""Shared repository root resolution helper for GEM Spatial IR layers."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_zoe_root(zoe_root: str | Path | None = None) -> Path:
    """Resolve the Zoe monorepo root from explicit arg, ZOE_ROOT env, or package path."""
    # Prefer an explicit caller-supplied root path when provided.
    if zoe_root is not None:
        return Path(zoe_root).expanduser().resolve()
    # Fall back to the ZOE_ROOT environment override if configured.
    env_root = os.environ.get("ZOE_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    # Default to 4 levels up from guiai-lab/guiai/gem/_root.py -> monorepo root.
    return Path(__file__).resolve().parents[3]


__all__ = ["resolve_zoe_root"]
