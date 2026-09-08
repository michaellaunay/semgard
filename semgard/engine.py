"""Pipeline orchestration: extraction → normalization → tagging → rules → report."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .extract import extract_file, extract_string
from .normalize import Segment, normalize_segments
from .parser import Expression
from .rules import ACTIONS, Finding, RuleSet
from .tagger import HeuristicTagger, Tagger

VERDICT_ORDER = {a: n for n, a in enumerate(("clean", *ACTIONS))}


@dataclass
class Report:
    source: str
    segments: list[Segment]
    expressions: list[Expression]
    findings: list[Finding]
    tagger: str
    ruleset_version: str
    lexicon_version: str

    @property
    def verdict(self) -> str:
        return max((f.action for f in self.findings), key=VERDICT_ORDER.__getitem__, default="clean")

    def segment_verdict(self, i: int, with_children: bool = False) -> str:
        """Return a segment verdict; with ``with_children``, inherit the worst child verdict."""
        idx = {i}
        if with_children:
            idx |= {k for k, s in enumerate(self.segments) if s.parent == i}
        return max((f.action for f in self.findings if idx & set(f.span_segments)), key=VERDICT_ORDER.__getitem__, default="clean")

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "verdict": self.verdict,
            "provenance": {"tagger": self.tagger, "ruleset": self.ruleset_version, "lexicon": self.lexicon_version},
            "segments": [
                {
                    "index": i,
                    "channel": s.channel,
                    "kind": s.kind,
                    "source": s.source,
                    "start": s.start,
                    "end": s.end,
                    "parent": s.parent,
                    "text": s.text,
                    "expression": str(e),
                    "verdict": self.segment_verdict(i),
                    "evidence": s.tags.get("evidence"),
                }
                for i, (s, e) in enumerate(zip(self.segments, self.expressions))
            ],
            "findings": [f.to_dict() for f in self.findings],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def quarantined_text(self, marker: str = "[SEMGARD:{verdict}:{rule}]") -> str:
        """Reconstruct text with every flagged segment replaced by a marker.

        Intended for the downstream layer (``<data>`` encapsulation, tool denial).
        Decoded shadow segments are not reinserted.
        """
        out: list[str] = []
        for i, seg in enumerate(self.segments):
            if seg.parent is not None or seg.channel != "body":
                continue
            v = self.segment_verdict(i, with_children=True)
            if v in ("quarantine", "block"):
                children = {i} | {k for k, s in enumerate(self.segments) if s.parent == i}
                rules = ",".join(sorted({f.rule_id for f in self.findings if children & set(f.span_segments)}))
                out.append(marker.format(verdict=v, rule=rules))
            else:
                out.append(seg.text)
        return "\n".join(out)


@dataclass
class Engine:
    tagger: Tagger = field(default_factory=HeuristicTagger)
    ruleset: RuleSet = field(default_factory=RuleSet.default)

    def _run(self, segments: list[Segment], source: str) -> Report:
        segments = normalize_segments(segments)
        expressions = [self.tagger.tag(s) for s in segments]
        findings = self.ruleset.apply(segments, expressions)
        inv = getattr(self.tagger, "inventory", None)
        return Report(
            source=source,
            segments=segments,
            expressions=expressions,
            findings=findings,
            tagger=type(self.tagger).__name__,
            ruleset_version=self.ruleset.version,
            lexicon_version=f"{inv.profile}@{inv.version}" if inv else "?",
        )

    def scan_text(self, text: str, fmt: str = "text", source: str = "<string>") -> Report:
        return self._run(extract_string(text, fmt=fmt, source=source), source)

    def scan_file(self, path: str | Path, fmt: str | None = None) -> Report:
        return self._run(extract_file(path, fmt=fmt), str(path))
