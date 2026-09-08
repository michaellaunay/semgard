"""Optional PDF extractor (requires pypdf).

Channels: page text (``body``), document metadata (``metadata``), annotations
and form fields (``hidden``).
"""

from __future__ import annotations

from pathlib import Path

from ..normalize import Segment
from .text import extract_text_sentences


def extract_pdf(path: str | Path) -> list[Segment]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("install PDF extraction support with: pip install 'semgard[pdf]'") from exc

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
    # AcroForm fields: some widgets expose values through /Annots, but
    # ``get_fields`` also covers fields defined at the form level.
    try:
        fields = reader.get_fields() or {}
    except Exception:  # pragma: no cover - malformed PDF or pypdf backend issue
        fields = {}
    seen_field_values: set[tuple[str, str]] = set()
    for name, field in fields.items():
        if not isinstance(field, dict):
            continue
        raw = field.get("/V") or field.get("/DV")
        if raw is None:
            continue
        value = str(raw).strip()
        key = (str(name), value)
        if value and key not in seen_field_values:
            seen_field_values.add(key)
            segs.append(
                Segment(
                    value,
                    0,
                    len(value),
                    channel="hidden",
                    kind="form_field",
                    source=f"{source}:field:{name}",
                )
            )

    meta = reader.metadata or {}
    for key, value in meta.items():
        value = str(value).strip()
        if value and len(value) > 3:
            segs.append(Segment(value, 0, len(value), channel="metadata", kind="meta", source=f"{source}:{key}"))
    return segs
