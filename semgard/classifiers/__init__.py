"""Deterministic classifiers using the same conventions as ``morphorepr/classifiers``.

Each classifier exposes ``classify(text) -> dict`` with at least ``present``
(bool), ``score`` (float in [0,1]), and ``evidence`` (list). These are v1
heuristics that must be calibrated (``classifiers/calibration``).
"""

from .directive_mood import classify as directive_mood

__all__ = ["directive_mood"]
