# Security

## Trust model

Safety Stream is a local development and transparency tool. Read it with that in mind.

- **`/emit` is unauthenticated.** Anyone who can reach the server's port can inject events. Run the server on `localhost` and do not expose port 9999 to a network you do not control. There is no token, no allowlist, and none is planned: the tool is meant to run beside the process it watches, not as a public service.
- **The stream is broadcast in clear.** Every connected dashboard receives every event. Do not put secrets in decision strings or messages. Those fields are for short reasoning summaries, not data.
- **The dashboard is a window, not a guard.** The events are self-reported by the model. The tool shows what a model says it reasoned. It does not enforce anything, and a model that chose not to emit would simply leave the dashboard dark. Do not treat a green dashboard as a safety control.

## What this is not

It is not an access-control layer, a content filter, or an independent monitor. It does not sit in the request path and it cannot block anything. It is a viewer for self-reported reasoning, useful for understanding and demonstration.

## Reporting a vulnerability

If you find a security issue in the code (the server, the dashboard, or a client), open an issue. For anything sensitive, use the private vulnerability reporting on this repository, or the contact channel at [nuclide-research.com](https://nuclide-research.com). Please do not include live data or third-party targets in a report.
