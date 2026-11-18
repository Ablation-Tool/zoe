from __future__ import annotations

from .autonomy_view import configure_autonomy


def main(argv=None):
    configure_autonomy()
    from zoe_autonomy.chat import main as chat_main

    return chat_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
