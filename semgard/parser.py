"""MorphoRepr expression parser parameterized by an ``Inventory``.

Grammar (Appendix A of the MorphoRepr paper, extended with prefix classes):

    expression ::= term ('+' term)*
    term       ::= coefficient '·' word
    word       ::= (prefix)* root (infix)* suffix

Words are split on hyphens and the resulting segments are classified (an
implementation detail of rule A.2-8): leading prefixes are consumed while a
possible root remains later in the word, which resolves the dual role of
``mal``/``ne``.

This implementation is intended to be replaced by
``morphorepr.utils.morphorepr_parser`` once it accepts an inventory; the API
(``parse_word``, ``parse_expression``) is designed to remain identical.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .inventory import Inventory

TERM_RE = re.compile(r"^\s*(?P<coef>[01](?:[.,]\d{1,2})?)\s*[·*]\s*(?P<word>[a-zĝŝĉĥĵŭ]+(?:-[a-zĝŝĉĥĵŭ]+)*)\s*$")


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class Word:
    prefixes: tuple[str, ...]
    root: str
    infixes: tuple[str, ...]
    suffix: str

    @property
    def chain(self) -> str:
        return "-".join((*self.prefixes, self.root, *self.infixes, self.suffix))

    def prefix_classes(self, inv: Inventory) -> tuple[str, ...]:
        return tuple(inv.prefix_class(p) or "?" for p in self.prefixes)

    def __str__(self) -> str:  # pragma: no cover - readability
        return self.chain


@dataclass(frozen=True)
class Term:
    coefficient: float
    word: Word

    @property
    def chain(self) -> str:
        return self.word.chain

    def __str__(self) -> str:
        return f"{self.coefficient:.2f}·{self.word.chain}"


@dataclass(frozen=True)
class Expression:
    terms: tuple[Term, ...] = field(default_factory=tuple)

    def __str__(self) -> str:
        return " + ".join(str(t) for t in self.terms)

    @property
    def chains(self) -> tuple[str, ...]:
        return tuple(t.chain for t in self.terms)

    def max_coefficient(self, pattern: re.Pattern[str]) -> float:
        """Maximum coefficient among terms whose chain matches ``pattern``."""
        return max((t.coefficient for t in self.terms if pattern.search(t.chain)), default=0.0)


def parse_word(chain: str, inv: Inventory) -> Word:
    segs = chain.strip().split("-")
    if len(segs) < 2:
        raise ParseError(f"word too short (root + suffix required): {chain!r}")
    suffix = segs[-1]
    if not inv.is_suffix(suffix):
        raise ParseError(f"unknown suffix {suffix!r} in {chain!r}")
    body = segs[:-1]

    # Prefixes: consume them while a root segment remains later in the word.
    i = 0
    while i < len(body) - 1 and inv.is_prefix(body[i]) and any(inv.is_root(s) for s in body[i + 1 :]):
        i += 1
    prefixes = tuple(body[:i])
    root = body[i]
    if not inv.is_root(root):
        raise ParseError(f"unknown root {root!r} in {chain!r}")
    infixes = tuple(body[i + 1 :])
    for inf in infixes:
        if not inv.is_infix(inf):
            raise ParseError(f"unknown infix {inf!r} in {chain!r}")

    # Canonical order of prefix classes (semgard profile).
    if inv.prefix_order:
        order = {k: n for n, k in enumerate(inv.prefix_order)}
        ranks = [order.get(inv.prefix_class(p) or "", len(order)) for p in prefixes]
        if ranks != sorted(ranks):
            raise ParseError(f"non-canonical prefix order in {chain!r} (expected {inv.prefix_order})")
    return Word(prefixes, root, infixes, suffix)


def parse_term(text: str, inv: Inventory) -> Term:
    m = TERM_RE.match(text)
    if not m:
        raise ParseError(f"malformed term: {text!r}")
    coef = float(m.group("coef").replace(",", "."))
    if not 0.01 <= coef <= 1.0:
        raise ParseError(f"coefficient outside [0.01, 1.00]: {coef}")
    return Term(round(coef, 2), parse_word(m.group("word"), inv))


def parse_expression(text: str, inv: Inventory) -> Expression:
    if not text or not text.strip():
        raise ParseError("empty expression")

    parts = text.split("+")
    if any(not part.strip() for part in parts):
        raise ParseError(f"malformed expression (empty term around '+'): {text!r}")

    terms = tuple(parse_term(part, inv) for part in parts)
    coefficients = tuple(term.coefficient for term in terms)
    if coefficients != tuple(sorted(coefficients, reverse=True)):
        raise ParseError("terms are not ordered by decreasing coefficient")
    return Expression(terms)


def make_word(inv: Inventory, root: str, *, prefixes: tuple[str, ...] = (), infixes: tuple[str, ...] = (), suffix: str) -> Word:
    """Build and validate a word (used by the tagger)."""
    return parse_word("-".join((*prefixes, root, *infixes, suffix)), inv)
