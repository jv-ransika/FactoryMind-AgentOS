# AgentOS Library Beta Release (`v0.1.0-beta.2`)

## Release Focus
- Internal library consumers installing from private package index.
- Stable Core API compatibility contract for beta patch upgrades.
- Canonical SDK examples for proposal, project-selection, and keyword extraction.

## What Changed from Beta.1
- Added installable package release workflow for private index.
- Added install verification script with clean-venv smoke run.
- Added explicit stable vs experimental API boundary documentation.

## Consumer Entry Checklist
- Install package from private index.
- Run `examples/proposal_agent_app.py`.
- Configure runtime/auth/secrets per `docs/sdk-configuration-guide.md`.
- Use stable core API only for integration-critical code.
