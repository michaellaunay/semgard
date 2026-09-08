"""Classifieurs déterministes (mêmes conventions que ``morphorepr/classifiers``).

Chaque classifieur expose ``classify(text) -> dict`` avec au minimum
``present`` (bool), ``score`` (float ∈ [0,1]) et ``evidence`` (liste).
Ce sont des heuristiques v1 à calibrer (``classifiers/calibration``).
"""

from .directive_mood import classify as directive_mood

__all__ = ["directive_mood"]
