# Changelog

## 0.1.0 — 2026-09-08

- Spécification technique v0.1 et ADR-001 (notation MorphoRepr, profil fermé, parseur paramétré).
- Inventaire `semgard` (16 morphèmes, ASCII) et parseur compatible avec le profil SAE du papier v0.30.
- Extraction texte / log / Markdown (canaux cachés) / PDF (optionnel), normalisation (NFKC, zero-width, base64/hex).
- Étiqueteur heuristique v0 et classifieur `directive_mood` avec jeu de calibration.
- Moteur de règles YAML (`match`, `stream`, `lexical`), jeu par défaut de dix règles, rapport JSON, texte reconstitué.
- CLI `semgard scan | tag | lexicon` ; 56 tests.
