"""Parameterized morpheme inventory.

This object is the interface SemGard expects from the MorphoRepr parser: a
parser does not hard-code its morphemes; it receives an ``Inventory``.
The ``semgard`` profile is loaded from ``lexicon/semgard_lexicon.json``; a
``sae`` profile (the inventory from Appendix A of the MorphoRepr paper) is
provided to verify that the parser remains compatible with the paper examples.

See docs/en/adr/ADR-001-morphorepr-notation.md.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Mapping

FREE_ROOT_RE = re.compile(r"^[a-z]{2,5}$")


@dataclass(frozen=True)
class Inventory:
    """Closed (or semi-open) morpheme inventory.

    ``prefixes`` maps each prefix to its class (``form``, ``addressee``,
    ``polarity``, ...). ``prefix_order`` defines the canonical order of prefix
    classes in a word, which keeps string regexes stable.
    """

    profile: str
    version: str
    prefixes: Mapping[str, str]
    roots: frozenset[str]
    infixes: frozenset[str]
    suffixes: frozenset[str]
    prefix_order: tuple[str, ...] = ()
    allow_free_roots: bool = False
    dual_role: frozenset[str] = field(default_factory=frozenset)
    meta: Mapping[str, object] = field(default_factory=dict)

    # -- predicates ---------------------------------------------------------
    def is_prefix(self, seg: str) -> bool:
        return seg in self.prefixes

    def is_infix(self, seg: str) -> bool:
        return seg in self.infixes

    def is_suffix(self, seg: str) -> bool:
        return seg in self.suffixes

    def is_reserved(self, seg: str) -> bool:
        return seg in self.prefixes or seg in self.infixes or seg in self.suffixes

    def is_root(self, seg: str) -> bool:
        if seg in self.roots:
            return True
        if self.allow_free_roots:
            return bool(FREE_ROOT_RE.match(seg)) and not self.is_reserved(seg)
        return False

    def prefix_class(self, seg: str) -> str | None:
        return self.prefixes.get(seg)

    # -- construction -------------------------------------------------------
    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "Inventory":
        prefixes: dict[str, str] = {}
        raw_prefixes = data.get("prefixes", {})
        for klass, members in raw_prefixes.items():  # type: ignore[union-attr]
            for tok in members:
                if tok in prefixes:
                    raise ValueError(f"duplicate prefix: {tok}")
                prefixes[tok] = klass
        roots = frozenset(data.get("roots", {}))  # type: ignore[arg-type]
        infixes = frozenset(data.get("infixes", {}))  # type: ignore[arg-type]
        suffixes = frozenset(data.get("suffixes", {}))  # type: ignore[arg-type]
        prefix_tokens = frozenset(prefixes)

        if prefix_tokens & infixes or prefix_tokens & suffixes or infixes & suffixes:
            collisions = sorted((prefix_tokens & infixes) | (prefix_tokens & suffixes) | (infixes & suffixes))
            raise ValueError(f"collision between affix classes: {', '.join(collisions)}")
        for tok in roots:
            if tok in infixes or tok in suffixes:
                raise ValueError(f"root collides with an affix: {tok}")

        prefix_order = tuple(data.get("prefix_order", ()))  # type: ignore[arg-type]
        if prefix_order:
            classes = set(prefixes.values())
            if set(prefix_order) != classes or len(prefix_order) != len(set(prefix_order)):
                raise ValueError(
                    "prefix_order must contain each prefix class exactly once "
                    f"(classes={sorted(classes)}, received={list(prefix_order)})"
                )

        dual = frozenset(t for t in roots if t in prefixes)
        return cls(
            profile=str(data.get("profile", "custom")),
            version=str(data.get("version", "0")),
            prefixes=prefixes,
            roots=roots,
            infixes=infixes,
            suffixes=suffixes,
            prefix_order=prefix_order,
            allow_free_roots=bool(data.get("allow_free_roots", False)),
            dual_role=dual,
            meta=dict(data),
        )

    @classmethod
    def from_json(cls, path: str | Path) -> "Inventory":
        with open(path, encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    @classmethod
    def semgard(cls) -> "Inventory":
        """Bundled SemGard profile (closed lexicon, ASCII)."""
        ref = resources.files("semgard").joinpath("lexicon/semgard_lexicon.json")
        with ref.open(encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    @classmethod
    def sae(cls) -> "Inventory":
        """SAE profile: inventory from Appendix A of the MorphoRepr v0.30 paper.

        Used only to verify that ``semgard.parser`` remains compatible with
        the paper forms (regression test).
        """
        return cls.from_dict(
            {
                "profile": "sae",
                "version": "0.30",
                "prefixes": {"polarity": ["mal", "ne", "pli", "plej", "duon"]},
                "roots": ["sci", "emo", "ag", "dir", "soc", "dat", "tem", "lok", "mal", "ne"],
                "infixes": ["ad", "int", "it", "ist", "ant", "at", "ig", "iĝ"],
                "suffixes": ["o", "a", "e", "i", "as", "is", "os", "us", "u"],
                "allow_free_roots": True,
            }
        )
