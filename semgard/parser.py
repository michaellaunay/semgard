"""Parseur d'expressions MorphoRepr paramétré par un ``Inventory``.

Grammaire (Annexe A du papier MorphoRepr, étendue par les classes de préfixes) :

    expression ::= terme ('+' terme)*
    terme      ::= coefficient '·' mot
    mot        ::= (préfixe)* racine (infixe)* suffixe

Segmentation sur les tirets, puis classement des segments (note
d'implémentation de la règle A.2-8) : les préfixes sont consommés en tête tant
qu'il reste, plus loin, un segment racine possible — ce qui règle le double
rôle ``mal``/``ne``.

Cette implémentation est destinée à être remplacée par
``morphorepr.utils.morphorepr_parser`` lorsque celui-ci acceptera un
inventaire ; l'API (``parse_word``, ``parse_expression``) est conçue pour être
identique.
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

    def __str__(self) -> str:  # pragma: no cover - lisibilité
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
        """Coefficient maximal des termes dont la chaîne satisfait ``pattern``."""
        return max((t.coefficient for t in self.terms if pattern.search(t.chain)), default=0.0)


def parse_word(chain: str, inv: Inventory) -> Word:
    segs = chain.strip().split("-")
    if len(segs) < 2:
        raise ParseError(f"mot trop court (racine + suffixe requis) : {chain!r}")
    suffix = segs[-1]
    if not inv.is_suffix(suffix):
        raise ParseError(f"suffixe inconnu {suffix!r} dans {chain!r}")
    body = segs[:-1]

    # Préfixes : consommés tant qu'un segment racine existe plus loin.
    i = 0
    while i < len(body) - 1 and inv.is_prefix(body[i]) and any(inv.is_root(s) for s in body[i + 1 :]):
        i += 1
    prefixes = tuple(body[:i])
    root = body[i]
    if not inv.is_root(root):
        raise ParseError(f"racine inconnue {root!r} dans {chain!r}")
    infixes = tuple(body[i + 1 :])
    for inf in infixes:
        if not inv.is_infix(inf):
            raise ParseError(f"infixe inconnu {inf!r} dans {chain!r}")

    # Ordre canonique des classes de préfixes (profil semgard).
    if inv.prefix_order:
        order = {k: n for n, k in enumerate(inv.prefix_order)}
        ranks = [order.get(inv.prefix_class(p) or "", len(order)) for p in prefixes]
        if ranks != sorted(ranks):
            raise ParseError(f"ordre de préfixes non canonique dans {chain!r} (attendu {inv.prefix_order})")
    return Word(prefixes, root, infixes, suffix)


def parse_term(text: str, inv: Inventory) -> Term:
    m = TERM_RE.match(text)
    if not m:
        raise ParseError(f"terme mal formé : {text!r}")
    coef = float(m.group("coef").replace(",", "."))
    if not 0.01 <= coef <= 1.0:
        raise ParseError(f"coefficient hors [0.01 ; 1.00] : {coef}")
    return Term(round(coef, 2), parse_word(m.group("word"), inv))


def parse_expression(text: str, inv: Inventory) -> Expression:
    terms = tuple(parse_term(part, inv) for part in text.split("+") if part.strip())
    if not terms:
        raise ParseError("expression vide")
    return Expression(terms)


def make_word(inv: Inventory, root: str, *, prefixes: tuple[str, ...] = (), infixes: tuple[str, ...] = (), suffix: str) -> Word:
    """Construit et valide un mot (utilisé par l'étiqueteur)."""
    return parse_word("-".join((*prefixes, root, *infixes, suffix)), inv)
