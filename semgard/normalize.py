"""Pipeline step 2: normalization and exposure of encoded content.

- NFKC plus removal of zero-width characters (visible text is preserved and
  original offsets remain attached to the segment);
- detection of Base64 / hexadecimal runs: decoded content becomes a *shadow*
  segment on the ``decoded`` channel (``kod-`` prefix during tagging).
"""

from __future__ import annotations

import base64
import binascii
import re
import unicodedata
from dataclasses import dataclass, field

ZERO_WIDTH = "".join(chr(c) for c in (0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0x2061, 0x2062, 0x2063, 0x2064, 0xFEFF, 0x00AD))
_ZW_RE = re.compile(f"[{re.escape(ZERO_WIDTH)}]")
_B64_RE = re.compile(r"(?<![A-Za-z0-9+/=])(?:[A-Za-z0-9+/]{4}){6,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?(?![A-Za-z0-9+/=])")
_HEX_RE = re.compile(r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}){12,}(?![0-9A-Fa-f])")
_PRINTABLE_RATIO = 0.9


@dataclass
class Segment:
    """Analysis unit: a line, sentence, field, or metadata item."""

    text: str
    start: int
    end: int
    channel: str = "body"  # body | hidden | decoded | metadata
    kind: str = "line"  # line | sentence | field | comment | meta
    source: str = ""  # file or field name
    zero_width_removed: int = 0
    parent: int | None = None  # source-segment index for shadow segments
    tags: dict[str, object] = field(default_factory=dict)


def strip_zero_width(text: str) -> tuple[str, int]:
    cleaned, n = _ZW_RE.subn("", text)
    return cleaned, n


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def _mostly_printable(s: str) -> bool:
    if not s:
        return False
    printable = sum(1 for ch in s if ch.isprintable() or ch in "\n\t")
    return printable / len(s) >= _PRINTABLE_RATIO


def decode_candidates(text: str) -> list[tuple[str, str, int, int]]:
    """Return (encoding, decoded text, start, end) for each decodable run."""
    found: list[tuple[str, str, int, int]] = []
    for m in _B64_RE.finditer(text):
        raw = m.group(0)
        try:
            decoded = base64.b64decode(raw + "=" * (-len(raw) % 4), validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        if _mostly_printable(decoded) and any(ch.isalpha() for ch in decoded):
            found.append(("base64", decoded, m.start(), m.end()))
    for m in _HEX_RE.finditer(text):
        try:
            decoded = bytes.fromhex(m.group(0)).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            continue
        if _mostly_printable(decoded) and any(ch.isalpha() for ch in decoded):
            found.append(("hex", decoded, m.start(), m.end()))
    return found


def normalize_segments(segments: list[Segment]) -> list[Segment]:
    """Normalize each segment and append decoded shadow segments."""
    out: list[Segment] = []
    for seg in segments:
        cleaned, n_zw = strip_zero_width(normalize_text(seg.text))
        seg.text = cleaned
        seg.zero_width_removed = n_zw
        if n_zw:
            seg.tags["zero_width"] = n_zw
        out.append(seg)
    for idx, seg in enumerate(list(out)):
        for enc, decoded, s, e in decode_candidates(seg.text):
            shadow = Segment(
                text=decoded,
                start=seg.start + s,
                end=seg.start + e,
                channel="decoded",
                kind=seg.kind,
                source=seg.source,
                parent=idx,
                tags={"encoding": enc},
            )
            out.append(shadow)
    return out
