"""Extracteur PDF (optionnel, dépend de pypdf).

Canaux : texte des pages (``body``), métadonnées du document (``metadata``),
annotations et champs de formulaire (``hidden``).
"""

from __future__ import annotations

from pathlib import Path

from ..normalize import Segment
from .text import extract_text_sentences


def extract_pdf(path: str | Path) -> list[Segment]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pip install 'semgard[pdf]' pour l'extraction PDF") from exc

    reader = PdfReader(str(path))
    source = Path(path).name
    segs: list[Segment] = []
    offset = 0
    for n, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        for seg in extract_text_sentences(text, source=f"{source}#p{n + 1}"):
            seg.start += offset
            seg.end += offset
            segs.append(seg)
        offset += len(text) + 1
        for annot in page.get("/Annots") or []:
            try:
                obj = annot.get_object()
                contents = str(obj.get("/Contents") or obj.get("/V") or "").strip()
            except Exception:  # pragma: no cover
                continue
            if contents:
                segs.append(Segment(contents, 0, len(contents), channel="hidden", kind="annotation", source=f"{source}#p{n + 1}"))
    meta = reader.metadata or {}
    for key, value in meta.items():
        value = str(value).strip()
        if value and len(value) > 3:
            segs.append(Segment(value, 0, len(value), channel="metadata", kind="meta", source=f"{source}:{key}"))
    return segs
