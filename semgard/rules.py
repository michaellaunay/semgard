"""Étape 6 du pipeline : moteur de règles.

Une règle est une regex sur des chaînes morphémiques (ou sur le flux de
chaînes de segments consécutifs, ou sur le texte normalisé), un seuil de
coefficient, une sévérité et une action. Format YAML :

    rules:
      - id: override_rules
        match: "^(?:kash-|kod-)?vi-(?:mal-|ne-)?regul-\\S*-(?:u|us)$"   # sur chaque terme
        min_gamma: 0.6
        where: any            # any | body | hidden | decoded | metadata
        severity: high        # info | low | medium | high | critical
        action: quarantine    # log | mark | quarantine | block
      - id: persona_then_secret
        stream: "vi-rol-\\S*-us(?:\\s+\\S+){0,3}?\\s+\\S*sekr-\\S*-u"        # sur le flux
        within: 4
      - id: marker
        lexical: "(?i)ignore (?:all|any|previous|prior|the above) instructions"  # sur le texte
        gamma: 0.5

Les actions sont ordonnées ; le verdict d'un segment est l'action maximale.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Iterable

import yaml

from .normalize import Segment
from .parser import Expression

ACTIONS = ("log", "mark", "quarantine", "block")
SEVERITIES = ("info", "low", "medium", "high", "critical")


@dataclass(frozen=True)
class Rule:
    id: str
    description: str = ""
    match: re.Pattern[str] | None = None
    stream: re.Pattern[str] | None = None
    lexical: re.Pattern[str] | None = None
    min_gamma: float = 0.5
    gamma: float = 0.5  # coefficient attribué par une règle lexicale
    where: str = "any"
    within: int = 3
    severity: str = "medium"
    action: str = "mark"

    def __post_init__(self) -> None:
        if sum(x is not None for x in (self.match, self.stream, self.lexical)) != 1:
            raise ValueError(f"règle {self.id} : exactement un de match/stream/lexical requis")
        if self.action not in ACTIONS or self.severity not in SEVERITIES:
            raise ValueError(f"règle {self.id} : action ou sévérité invalide")

    @classmethod
    def from_dict(cls, d: dict) -> "Rule":
        return cls(
            id=str(d["id"]),
            description=str(d.get("description", "")),
            match=re.compile(d["match"]) if "match" in d else None,
            stream=re.compile(d["stream"]) if "stream" in d else None,
            lexical=re.compile(d["lexical"]) if "lexical" in d else None,
            min_gamma=float(d.get("min_gamma", 0.5)),
            gamma=float(d.get("gamma", 0.5)),
            where=str(d.get("where", "any")),
            within=int(d.get("within", 3)),
            severity=str(d.get("severity", "medium")),
            action=str(d.get("action", "mark")),
        )


@dataclass
class Finding:
    rule_id: str
    segment_index: int
    gamma: float
    severity: str
    action: str
    matched: str
    span_segments: tuple[int, ...] = ()

    def to_dict(self) -> dict:
        return self.__dict__ | {"span_segments": list(self.span_segments)}


@dataclass
class RuleSet:
    rules: list[Rule] = field(default_factory=list)
    version: str = "1"

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RuleSet":
        with open(path, encoding="utf-8") as fh:
            return cls.from_dict(yaml.safe_load(fh))

    @classmethod
    def from_dict(cls, data: dict) -> "RuleSet":
        return cls([Rule.from_dict(r) for r in data.get("rules", [])], version=str(data.get("version", "1")))

    @classmethod
    def default(cls) -> "RuleSet":
        ref = resources.files("semgard").joinpath("lexicon/default_rules.yaml")
        with ref.open(encoding="utf-8") as fh:
            return cls.from_dict(yaml.safe_load(fh))

    # -- application -------------------------------------------------------
    def apply(self, segments: list[Segment], expressions: list[Expression]) -> list[Finding]:
        findings: list[Finding] = []
        for rule in self.rules:
            if rule.match is not None:
                findings.extend(self._apply_term(rule, segments, expressions))
            elif rule.lexical is not None:
                findings.extend(self._apply_lexical(rule, segments))
            else:
                findings.extend(self._apply_stream(rule, segments, expressions))
        seen: set[tuple[str, tuple[int, ...]]] = set()
        unique: list[Finding] = []
        for f in findings:
            key = (f.rule_id, f.span_segments)
            if key not in seen:
                seen.add(key)
                unique.append(f)
        return unique

    @staticmethod
    def _in_scope(rule: Rule, seg: Segment) -> bool:
        return rule.where == "any" or rule.where == seg.channel

    def _apply_term(self, rule: Rule, segments: list[Segment], expressions: list[Expression]) -> Iterable[Finding]:
        assert rule.match is not None
        for i, (seg, expr) in enumerate(zip(segments, expressions)):
            if not self._in_scope(rule, seg):
                continue
            for term in expr.terms:
                if term.coefficient >= rule.min_gamma and rule.match.search(term.chain):
                    yield Finding(rule.id, i, term.coefficient, rule.severity, rule.action, term.chain, (i,))
                    break

    def _apply_lexical(self, rule: Rule, segments: list[Segment]) -> Iterable[Finding]:
        assert rule.lexical is not None
        for i, seg in enumerate(segments):
            if not self._in_scope(rule, seg):
                continue
            m = rule.lexical.search(seg.text)
            if m:
                yield Finding(rule.id, i, rule.gamma, rule.severity, rule.action, m.group(0), (i,))

    def _apply_stream(self, rule: Rule, segments: list[Segment], expressions: list[Expression]) -> Iterable[Finding]:
        """Regex sur le flux : chaque segment est représenté par ses chaînes ≥ min_gamma, jointes par ' | '."""
        assert rule.stream is not None
        # Le flux ne mélange pas les canaux : un segment ombre suit son parent.
        tokens: list[str] = []
        owners: list[int] = []
        for i, (seg, expr) in enumerate(zip(segments, expressions)):
            if not self._in_scope(rule, seg):
                continue
            chains = [t.chain for t in expr.terms if t.coefficient >= rule.min_gamma] or ["_"]
            tokens.append(" | ".join(chains))
            owners.append(i)
        # Fenêtre glissante de `within` segments.
        for start in range(len(tokens)):
            window = tokens[start : start + rule.within]
            text = " \n ".join(window)
            m = rule.stream.search(text)
            if m:
                # Segments effectivement couverts par le match.
                covered = text[: m.end()].count(" \n ") + 1
                span = tuple(owners[start : start + covered])
                gamma = max(
                    (t.coefficient for k in span for t in expressions[k].terms if t.coefficient >= rule.min_gamma),
                    default=rule.min_gamma,
                )
                yield Finding(rule.id, span[0], gamma, rule.severity, rule.action, m.group(0), span)
