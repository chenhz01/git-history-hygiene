# Changelog

## v0.1.1 — 2026-10-12
- Documentation layer completed: README (Problem / How it works / Quickstart / why-not-X anchored on git-history-audit, hotfix-tag-check, archivist / Minimal Fallback / Trade-offs / Limits / FAQ), ALIGNMENT.md 16-item audit.
- Self-test re-verified green, no code changes needed this round: `python self_test.py` → `SUMMARY: PASS 60/60`.

## v0.1.0 — 2026-10-11
- Initial implementation: numstat log parser with `core.quotePath` octet/escape decoding, churn hotspots, merge density, files-per-commit median/p90, generic-subject and mega-commit detection, binary-blob tracking, 0–100 hygiene score, three input modes (`--repo` / `--log-file` / `--stdin`), JSON output, exit 2 on bad input.
- Self-test suite (functional / error / extreme-edge tiers).
