from __future__ import annotations

import sys

from .unified import ComponentRegistry


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "--":
        arguments.pop(0)
    try:
        result = ComponentRegistry().launch("pala", arguments or ["--list"], detach=False)
        return result.returncode
    except (OSError, RuntimeError, ValueError) as error:
        print(f"zoe pala: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
