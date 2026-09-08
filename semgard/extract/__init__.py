"""Pipeline step 1: format-specific extraction into segments.

Each extractor returns a list of ``Segment`` objects with offsets, channel
(``body``, ``hidden``, ``metadata``), and kind. The extractor is selected from
the file extension or explicitly.
"""

from __future__ import annotations

from pathlib import Path

from ..normalize import Segment
from .text import extract_lines, extract_markdown, extract_text_sentences

__all__ = ["extract_file", "extract_string", "extract_lines", "extract_markdown", "extract_text_sentences"]

_BY_EXT = {
    ".log": "log",
    ".txt": "text",
    ".md": "markdown",
    ".markdown": "markdown",
    ".pdf": "pdf",
}


def extract_string(text: str, fmt: str = "text", source: str = "<string>") -> list[Segment]:
    if fmt == "log":
        return extract_lines(text, source=source)
    if fmt == "markdown":
        return extract_markdown(text, source=source)
    if fmt == "field":
        return extract_text_sentences(text, source=source, kind="field")
    return extract_text_sentences(text, source=source)


def extract_file(path: str | Path, fmt: str | None = None) -> list[Segment]:
    path = Path(path)
    fmt = fmt or _BY_EXT.get(path.suffix.lower(), "text")
    if fmt == "pdf":
        from .pdf import extract_pdf

        return extract_pdf(path)
    return extract_string(path.read_text(encoding="utf-8", errors="replace"), fmt=fmt, source=path.name)
