# Changelog

## 0.1.0 — 2026-09-08

- Technical specification v0.1 and ADR-001 (MorphoRepr notation, closed profile, parameterized parser).
- `semgard` inventory (16 morphemes, ASCII) and parser compatible with the SAE profile from the v0.30 paper.
- Text / log / Markdown extraction (hidden channels) / optional PDF extraction, plus normalization (NFKC, zero-width, Base64/hex).
- v0 heuristic tagger and `directive_mood` classifier with a calibration set.
- YAML rule engine (`match`, `stream`, `lexical`), ten-rule default set, JSON report, and reconstructed text.
- `semgard scan | tag | lexicon` CLI and pytest regression suite.
