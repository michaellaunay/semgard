"""Inventaire morphémique paramétrable.

Cet objet est l'interface que SemGard attend du parseur MorphoRepr : un
parseur ne connaît pas ses morphèmes en dur, il reçoit un ``Inventory``.
Le profil « semgard » est chargé depuis ``lexicon/semgard_lexicon.json`` ;
un profil « sae » (inventaire de l'Annexe A du papier MorphoRepr) est fourni
pour vérifier que le parseur reste compatible avec les exemples du papier.

Voir docs/fr/adr/ADR-001-notation-morphorepr.md.
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
    """Inventaire fermé (ou semi-ouvert) de morphèmes.

    ``prefixes`` associe chaque préfixe à sa classe (``form``, ``addressee``,
    ``polarity`` …). ``prefix_order`` fixe l'ordre canonique des classes de
    préfixes dans un mot, ce qui rend les regex sur chaînes stables.
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

    # -- prédicats ---------------------------------------------------------
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

    # -- construction ------------------------------------------------------
    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "Inventory":
        prefixes: dict[str, str] = {}
        raw_prefixes = data.get("prefixes", {})
        for klass, members in raw_prefixes.items():  # type: ignore[union-attr]
            for tok in members:
                if tok in prefixes:
                    raise ValueError(f"préfixe dupliqué : {tok}")
                prefixes[tok] = klass
        roots = frozenset(data.get("roots", {}))  # type: ignore[arg-type]
        infixes = frozenset(data.get("infixes", {}))  # type: ignore[arg-type]
        suffixes = frozenset(data.get("suffixes", {}))  # type: ignore[arg-type]
        for tok in roots:
            if tok in infixes or tok in suffixes:
                raise ValueError(f"racine en collision avec un affixe : {tok}")
        dual = frozenset(t for t in roots if t in prefixes)
        return cls(
            profile=str(data.get("profile", "custom")),
            version=str(data.get("version", "0")),
            prefixes=prefixes,
            roots=roots,
            infixes=infixes,
            suffixes=suffixes,
            prefix_order=tuple(data.get("prefix_order", ())),  # type: ignore[arg-type]
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
        """Profil SemGard embarqué (lexique fermé, ASCII)."""
        ref = resources.files("semgard").joinpath("lexicon/semgard_lexicon.json")
        with ref.open(encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    @classmethod
    def sae(cls) -> "Inventory":
        """Profil SAE : inventaire de l'Annexe A du papier MorphoRepr v0.30.

        Sert uniquement à vérifier que ``semgard.parser`` reste compatible
        avec les formes du papier (test de non-régression).
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
