"""Unified `zoe clara` launcher forwarding straight to Zoe & Clara Dual-Peer chat."""

from __future__ import annotations

from .autonomy_view import configure_autonomy


def main(argv=None) -> int:
    configure_autonomy()
    from zoe_autonomy.zoe_clara import main as clara_main
    return clara_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
