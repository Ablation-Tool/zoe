# Claude-4.7

Research notes and live captures on the **sentinel-driven template extraction** prompting pattern for Claude 4.7. The repository is documentation + recorded sessions, not a buildable code project.

## Language
Markdown (research notes) + WebM (screencast recordings)

## Layout
```
captures/      # text captures from a UserPromptSubmit hook
screencasts/   # WebM recordings of live Claude 4.7 sessions
README.md      # the methodology — sentinel-driven %%FILL%% templates
```

## Claude Code Notes
- README is the canonical reference for the methodology — read it first
- `captures/` are auto-generated text dumps from a Claude Code hook; treat as evidence, not source
- `screencasts/` go in `screencasts/`, captures stay text-only — when cross-referencing a recording from a capture, link via `../screencasts/<file>.webm`
- This repo is one of NuClide's research/methodology artifacts, not a tool — no `go build` or `cargo build` step
- Built with [Claude Code](https://claude.ai/code)
