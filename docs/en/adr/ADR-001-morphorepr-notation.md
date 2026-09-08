# ADR-001 — Adopt MorphoRepr as the tag notation, with a closed profile and a parameterized parser

[Version française](../../fr/adr/ADR-001-notation-morphorepr.md)

**Status**: accepted — 2026-09-08

## Context

For each text segment, SemGard needs to serialize a tuple of semantic labels (form, addressee, polarity, topic, causation, act) so that ordinary regular expressions can operate on it. MorphoRepr (Launay, 2026; v0.30) defines an agglutinative grammar `(prefix)* root (infix)* suffix` and a parser based on hyphen segmentation, but its inventory is hard-coded for the SAE profile, with the closed prefixes `mal-`, `ne-`, `pli-`, `plej-`, and `duon-`.

## Decision

1. SemGard tags are **MorphoRepr expressions** using a dedicated `semgard` profile.
2. The profile is **closed** (16 morphemes, no free roots) and **strict ASCII**.
3. Prefixes are divided into **ordered classes** (`form < addressee < polarity`); this is the only grammar extension and keeps regexes stable.
4. The parser is **parameterized by an `Inventory` object**. SemGard carries a compatible implementation in `semgard/parser.py`, tested against forms from the paper, and intends to replace it with `morphorepr.utils.morphorepr_parser` once that parser accepts an inventory (an upstream contribution).
5. Esperanto is only a **metalanguage**: no model receives Esperanto source text as input.

## Rejected alternatives

- *Verbose tuples* (`DIRECTIVE[addressee=AI, topic=rules]`): readable but irregular, less convenient for regexes, and do not reuse MorphoRepr. They remain planned as a bijective surface syntax (spec §2.5).
- *Encode the addressee as an additive term* (`0.83·mal-regul-u + 0.90·ai-o`): compatible with the current grammar, but per-term regex matching loses the addressee relationship.
- *Write an unrelated parser*: this would lose compatibility and weaken the “two channels, one notation” argument (spec §8).

## Consequences

- Two upstream contributions are useful to MorphoRepr: `Inventory` support in the parser and the `directive_mood` classifier (the measurable counterpart of suffix `-u`, absent from the current robust-property set).
- Every inventory change creates a new lexicon and corpus version.
- Agglutinative ordering remains an ergonomic hypothesis; the bag-of-morphemes ablation in spec §6 tests whether order provides functional value.
