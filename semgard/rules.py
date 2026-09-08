"""Pipeline step 6: rule engine.

A rule is a regex over morphemic chains (or over a stream of consecutive
segment chains, or normalized text), plus a coefficient threshold, severity,
and action. YAML format:

    rules:
      - id: override_rules
        match: "^(?:kash-|kod-)?vi-(?:mal-|ne-)?regul-\\S*-(?:u|us)$"   # on each term
        min_gamma: 0.6
        where: any            # any | body | hidden | decoded | metadata
        severity: high        # info | low | medium | high | critical
        action: quarantine    # log | mark | quarantine | block
      - id: persona_then_secret
        stream: "vi-rol-\\S*-us(?:\\s+\\S+){0,3}?\\s+\\S*sekr-\\S*-u"        # on the stream
        within: 4
      - id: marker
        lexical: "(?i)ignore (?:all|any|previous|prior|the above) instructions"  # on the text
        gamma: 0.5

Actions are ordered; a segment verdict is the maximum action.
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
CHANNELS = ("any", "body", "hidden", "decoded", "metadata")


@dataclass(frozen=True)
class Rule:
    id: str
    description: str = ""
    match: re.Pattern[str] | None = None
    stream: re.Pattern[str] | None = None
    lexical: re.Pattern[str] | None = None
    min_gamma: float = 0.5
    gamma: float = 0.5  # coefficient assigned by a lexical rule
    where: str = "any"
    within: int = 3
    severity: str = "medium"
    action: str = "mark"

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("empty rule identifier")
        if sum(x is not None for x in (self.match, self.stream, self.lexical)) != 1:
            raise ValueError(f"rule {self.id}: exactly one of match/stream/lexical is required")
        if self.action not in ACTIONS or self.severity not in SEVERITIES:
            raise ValueError(f"rule {self.id}: invalid action or severity")
        if self.where not in CHANNELS:
            raise ValueError(f"rule {self.id}: invalid channel {self.where!r}")
        if not 0.0 <= self.min_gamma <= 1.0 or not 0.0 <= self.gamma <= 1.0:
            raise ValueError(f"rule {self.id}: gamma/min_gamma must be within [0, 1]")
        if self.within < 1:
            raise ValueError(f"rule {self.id}: within must be >= 1")

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
        rules = [Rule.from_dict(r) for r in data.get("rules", [])]
        ids = [rule.id for rule in rules]
        if len(ids) != len(set(ids)):
            duplicates = sorted({rule_id for rule_id in ids if ids.count(rule_id) > 1})
            raise ValueError(f"duplicate rule identifiers: {', '.join(duplicates)}")
        return cls(rules, version=str(data.get("version", "1")))

    @classmethod
    def default(cls) -> "RuleSet":
        ref = resources.files("semgard").joinpath("lexicon/default_rules.yaml")
        with ref.open(encoding="utf-8") as fh:
            return cls.from_dict(yaml.safe_load(fh))

    # -- application --------------------------------------------------------
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
        """Apply a regex to streams kept separate by channel.

        Each segment is represented by its chains >= ``min_gamma``, joined with
        `` | ``. A ``where: any`` rule analyzes each channel independently, so
        it cannot create an artificial sequence between, for example, visible
        body text and metadata or a decoded segment.
        """
        assert rule.stream is not None
        separator = " \n "

        groups: dict[str, list[tuple[int, Expression]]] = {}
        for i, (seg, expr) in enumerate(zip(segments, expressions)):
            if self._in_scope(rule, seg):
                groups.setdefault(seg.channel, []).append((i, expr))

        for items in groups.values():
            tokens: list[str] = []
            owners: list[int] = []
            for owner, expr in items:
                chains = [t.chain for t in expr.terms if t.coefficient >= rule.min_gamma] or ["_"]
                tokens.append(" | ".join(chains))
                owners.append(owner)

            for start in range(len(tokens)):
                window = tokens[start : start + rule.within]
                text = separator.join(window)
                m = rule.stream.search(text)
                if not m:
                    continue

                # Cover only the segments actually crossed by the match,
                # not earlier segments merely present in the same window.
                first_rel = text[: m.start()].count(separator)
                last_rel = text[: m.end()].count(separator)
                span = tuple(owners[start + first_rel : start + last_rel + 1])
                gamma = max(
                    (t.coefficient for k in span for t in expressions[k].terms if t.coefficient >= rule.min_gamma),
                    default=rule.min_gamma,
                )
                yield Finding(rule.id, span[0], gamma, rule.severity, rule.action, m.group(0), span)
