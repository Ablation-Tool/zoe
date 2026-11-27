# Claude-Savant

Persistent, user-owned memory for Claude. Concept: point a single Claude memory slot at a GitHub Gist URL — the gist file holds your real memory content (up to ~1 MB per gist), edited in any text editor. One Savant slot at the current 40,223-char usage equals 6.7× the entire built-in 30-slot × 200-char cap.

This repository is **documentation + walkthrough**, not a buildable project — there is no source tree, build step, or test suite.

## Layout
```
README.md            # tagline + by-the-numbers framing
claude-savant.md     # full walkthrough (markdown)
claude-savant.pdf    # full walkthrough (PDF, identical content)
images/header.png    # repo header banner
images/by-the-numbers.png  # in-walkthrough capacity diagram
```

## Claude Code Notes
- Read `claude-savant.md` for the full step-by-step setup
- The Gist file holds the real content; Claude's memory slot just points at it (URL + a token used for writeback if you want bidirectional updates)
- This pattern works in `claude.ai` and Claude Code; the memory slot is a single line of text Claude resolves at conversation start
- Built with [Claude Code](https://claude.ai/code)
