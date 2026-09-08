"""Extracteurs texte, log et markdown."""

from __future__ import annotations

import re

from ..normalize import Segment

_SENT_RE = re.compile(r"[^.!?\n]+[.!?]*\s*")
_HTML_COMMENT_RE = re.compile(r"<!--(.*?)-->", re.S)
_HIDDEN_SPAN_RE = re.compile(
    r"<(?:span|div|p)[^>]*style=\"[^\"]*(?:display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0|color\s*:\s*(?:white|#fff(?:fff)?))[^\"]*\"[^>]*>(.*?)</(?:span|div|p)>",
    re.S | re.I,
)
_QUOTED_RE = re.compile(r"\"([^\"\n]{20,})\"|'([^'\n]{20,})'")
_ALT_TITLE_RE = re.compile(r"\b(?:alt|title)=\"([^\"]{8,})\"", re.I)


def extract_lines(text: str, source: str = "", kind: str = "line") -> list[Segment]:
    """Une ligne = un segment ; les chaînes entre guillemets (≥ 20 car.) deviennent des sous-segments.

    Dans un log, une instruction injectée vit presque toujours dans un champ cité
    (``comment="…"``) : la ligne entière est assertive, le champ ne l'est pas.
    """
    segs: list[Segment] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped:
            lead = len(line) - len(line.lstrip())
            start = pos + lead
            parent_index = len(segs)
            segs.append(Segment(stripped, start, start + len(stripped), kind=kind, source=source))
            for m in _QUOTED_RE.finditer(stripped):
                inner = m.group(1) or m.group(2)
                segs.append(Segment(inner, start + m.start() + 1, start + m.start() + 1 + len(inner), kind="quoted", source=source, parent=parent_index))
        pos += len(line)
    return segs


def extract_text_sentences(text: str, source: str = "", kind: str = "sentence") -> list[Segment]:
    segs: list[Segment] = []
    for m in _SENT_RE.finditer(text):
        s = m.group(0).strip()
        if s:
            lead = len(m.group(0)) - len(m.group(0).lstrip())
            segs.append(Segment(s, m.start() + lead, m.start() + lead + len(s), kind=kind, source=source))
    return segs


def extract_markdown(text: str, source: str = "") -> list[Segment]:
    """Corps en phrases + canaux cachés (commentaires HTML, spans invisibles, alt/title)."""
    hidden: list[Segment] = []
    masked = text
    for regex, kind in ((_HTML_COMMENT_RE, "comment"), (_HIDDEN_SPAN_RE, "hidden_span"), (_ALT_TITLE_RE, "attribute")):
        for m in regex.finditer(text):
            inner = m.group(1).strip()
            if inner:
                hidden.append(Segment(inner, m.start(1), m.start(1) + len(inner), channel="hidden", kind=kind, source=source))
        masked = regex.sub(lambda mm: " " * len(mm.group(0)), masked)
    body = extract_text_sentences(masked, source=source)
    return body + hidden
