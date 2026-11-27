"""Launch the TOS GEM workbench: python3 -m tos_gem --repo /path/to/repo"""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(prog="tos_gem", description=__doc__)
    parser.add_argument("--repo", default=".", help="Git repository to audit (default: cwd)")
    parser.add_argument("--agent-command", default="auto",
                        help="AI CLI to embed. Default: auto-detect kimi, claude, or codex. "
                             "Use 'none' with --no-agent instead to disable.")
    parser.add_argument("--no-agent", action="store_true",
                        help="Launch without the embedded agent terminal")
    parser.add_argument("--workspace", default="", help="Working directory for the agent")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        parser.error(f"{repo} is not a git repository")

    from . import gui
    agent_command = "none" if args.no_agent else args.agent_command
    gui.run(repo, agent_command, args.workspace)


if __name__ == "__main__":
    main()
